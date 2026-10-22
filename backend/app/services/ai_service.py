import os
import json
import re
import logging
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
        self.client = None
        if self.api_key and self.api_key.strip() and not self.api_key.startswith("demo_"):
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.client = None

    def is_api_configured(self) -> bool:
        return self.client is not None

    async def _call_gemini_json(self, system_prompt: str, user_prompt: str, retry_count: int = 1) -> Any:
        """
        Calls Gemini requesting JSON. Validates JSON and retries once if malformed.
        """
        if not self.client:
            raise RuntimeError("Gemini API key is not configured.")

        contents = user_prompt
        content_text = ""

        for attempt in range(retry_count + 1):
            try:
                response = await self.client.aio.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                )

                content_text = response.text or ""

                # Clean and parse JSON
                parsed_json = self._extract_and_parse_json(content_text)
                return parsed_json

            except (json.JSONDecodeError, ValueError) as err:
                logger.warning(f"Gemini JSON parsing failed on attempt {attempt + 1}: {err}")
                if attempt < retry_count:
                    contents = (
                        f"{user_prompt}\n\nYour previous response was not valid JSON:\n"
                        f"{content_text}\n\nRespond ONLY with a valid JSON object or array. "
                        "Do not include markdown code blocks or explanations."
                    )
                else:
                    raise ValueError(f"AI response was not valid JSON after retry: {err}")
            except Exception as e:
                logger.error(f"Gemini API call error: {e}")
                raise e

    def _extract_and_parse_json(self, text: str) -> Any:
        """Extracts JSON from text, stripping markdown ```json ``` blocks if present."""
        cleaned = text.strip()
        # Remove markdown code fences
        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if match:
            cleaned = match.group(1).strip()
        return json.loads(cleaned)

    # ==================== SUMMARIZER ====================
    async def generate_summary(
        self,
        document_title: str,
        text_content: str,
        length: str = "standard"  # "brief" | "standard" | "detailed"
    ) -> Dict[str, Any]:
        """
        Generates a summary of the given length and a list of key terms with definitions.
        Rules:
        - Grounded only in uploaded text. Do not invent facts.
        - Structured JSON output: { "summary": "...", "key_terms": [{"term": "...", "definition": "..."}] }
        """
        if not self.is_api_configured():
            return self._fallback_summary(document_title, text_content, length)

        length_instructions = {
            "brief": "Provide a high-impact, concise summary in 2 to 3 punchy paragraphs focusing only on core takeaways.",
            "standard": "Provide a balanced, comprehensive summary in 4 to 6 structured paragraphs covering the major concepts and connections.",
            "detailed": "Provide a deep-dive, thorough summary breaking down all essential sub-topics, principles, mechanisms, and examples found in the text."
        }

        system_prompt = (
            "You are Kabisado, an expert AI study buddy for Filipino students. "
            "Tagline: 'Aral ngayon, pasa bukas.' "
            "Tone: You are friendly, relatable, slightly witty, but when explaining academic material, your explanations are strictly accurate, crystal-clear, and serious. "
            "CRITICAL RULE: Base your summary and key terms strictly on the provided text. Do NOT invent facts or hallucinate external information. "
            "Always respond in valid, strict JSON with this exact schema:\n"
            "{\n"
            '  "summary": "Formatted markdown text of the summary...",\n'
            '  "key_terms": [\n'
            '    {"term": "Term name", "definition": "Clear concise definition from the text"}\n'
            "  ]\n"
            "}"
        )

        user_prompt = (
            f"Document Title: {document_title}\n"
            f"Requested Length: {length.upper()}\n"
            f"Instruction: {length_instructions.get(length, length_instructions['standard'])}\n"
            f"Extract 5 to 10 of the most important key terms and definitions.\n\n"
            f"--- SOURCE TEXT ---\n{text_content[:25000]}"
        )

        try:
            result = await self._call_gemini_json(system_prompt, user_prompt)
            if not isinstance(result, dict) or "summary" not in result or "key_terms" not in result:
                raise ValueError("JSON missing required summary or key_terms keys")
            return result
        except Exception as e:
            logger.warning(f"Gemini API failed or errored ({e}), using grounded fallback engine.")
            return self._fallback_summary(document_title, text_content, length)

    # ==================== FLASHCARDS ====================
    async def generate_flashcards(
        self,
        document_title: str,
        topic_title: str,
        topic_content: str,
        topic_id: Optional[int] = None,
        count: int = 8,
        card_type: str = "mixed"  # "term", "qa", or "mixed"
    ) -> List[Dict[str, Any]]:
        """
        Generates flashcards tagged by topic.
        Flashcard JSON: [ { "front": "...", "back": "...", "topic_id": "...", "card_type": "term" | "qa" } ]
        """
        if not self.is_api_configured():
            return self._fallback_flashcards(topic_title, topic_content, topic_id, count, card_type)

        system_prompt = (
            "You are Kabisado, an AI study assistant. Generate high-yield, memory-enhancing flashcards for a student. "
            "Rules:\n"
            "1. Ground cards ONLY on the provided text. Never invent facts.\n"
            "2. Make the 'front' clear and prompt-oriented (either a concept/term or a targeted question).\n"
            "3. Make the 'back' concise, clear, and easy to memorize.\n"
            "4. Return strict JSON array of flashcard objects matching this exact structure:\n"
            "[\n"
            '  {\n'
            f'    "topic_id": {json.dumps(topic_id)},\n'
            '    "front": "Question or Term",\n'
            '    "back": "Answer or Definition",\n'
            '    "card_type": "term" or "qa"\n'
            '  }\n'
            "]"
        )

        user_prompt = (
            f"Topic: {topic_title}\n"
            f"Target Card Count: {count}\n"
            f"Card Style: {card_type}\n\n"
            f"--- TEXT CONTENT ---\n{topic_content[:15000]}"
        )

        try:
            cards = await self._call_gemini_json(system_prompt, user_prompt)
            if not isinstance(cards, list):
                if isinstance(cards, dict) and "flashcards" in cards:
                    cards = cards["flashcards"]
                else:
                    raise ValueError("Flashcard response is not a list")

            cleaned_cards = []
            for c in cards:
                if "front" in c and "back" in c:
                    cleaned_cards.append({
                        "front": str(c["front"]).strip(),
                        "back": str(c["back"]).strip(),
                        "topic_id": topic_id,
                        "card_type": c.get("card_type", "term")
                    })
            return cleaned_cards if cleaned_cards else self._fallback_flashcards(topic_title, topic_content, topic_id, count, card_type)
        except Exception as e:
            logger.warning(f"Gemini flashcard generation error ({e}), using grounded fallback.")
            return self._fallback_flashcards(topic_title, topic_content, topic_id, count, card_type)

    # ==================== QUIZ GENERATOR ====================
    async def generate_quiz_questions(
        self,
        document_title: str,
        topic_title: str,
        topic_content: str,
        topic_id: Optional[int] = None,
        count: int = 5,
        difficulty: str = "medium"  # "easy", "medium", "hard", "mixed"
    ) -> List[Dict[str, Any]]:
        """
        Generates multiple-choice quiz questions.
        Question JSON:
        [
          {
            "question": "",
            "choices": ["A", "B", "C", "D"],
            "correct_index": 0,
            "explanation": "",
            "difficulty": "medium",
            "topic_id": ""
          }
        ]
        """
        if not self.is_api_configured():
            return self._fallback_quiz(topic_title, topic_content, topic_id, count, difficulty)

        system_prompt = (
            "You are Kabisado, an expert exam maker for college and high school students. "
            "Generate rigorous multiple-choice questions grounded STRICTLY in the provided text.\n"
            "Rules:\n"
            "1. Exactly 4 choices per question.\n"
            "2. One unequivocally correct answer; 3 plausible distractors (misconceptions or related terms from the text).\n"
            "3. Grounded explanation that explains why the correct answer is right and why distractors are wrong.\n"
            "4. Return strict JSON array matching this schema:\n"
            "[\n"
            '  {\n'
            '    "question": "Clear question text?",\n'
            '    "choices": ["Option 1", "Option 2", "Option 3", "Option 4"],\n'
            '    "correct_index": 0,\n'
            '    "explanation": "Clear explanation referencing the text...",\n'
            f'    "difficulty": "{difficulty if difficulty != "mixed" else "medium"}",\n'
            f'    "topic_id": {json.dumps(topic_id)}\n'
            '  }\n'
            "]"
        )

        user_prompt = (
            f"Topic: {topic_title}\n"
            f"Number of Questions: {count}\n"
            f"Difficulty Level: {difficulty}\n\n"
            f"--- TEXT CONTENT ---\n{topic_content[:15000]}"
        )

        try:
            questions = await self._call_gemini_json(system_prompt, user_prompt)
            if not isinstance(questions, list):
                if isinstance(questions, dict) and "questions" in questions:
                    questions = questions["questions"]
                else:
                    raise ValueError("Questions response is not a list")

            cleaned_questions = []
            for q in questions:
                if "question" in q and "choices" in q and len(q["choices"]) == 4:
                    c_idx = int(q.get("correct_index", 0))
                    if c_idx < 0 or c_idx > 3:
                        c_idx = 0
                    diff = q.get("difficulty", difficulty)
                    if diff not in ["easy", "medium", "hard"]:
                        diff = "medium"
                    cleaned_questions.append({
                        "question": str(q["question"]).strip(),
                        "choices": [str(c).strip() for c in q["choices"]],
                        "correct_index": c_idx,
                        "explanation": str(q.get("explanation", "Batay sa module content.")).strip(),
                        "difficulty": diff,
                        "topic_id": topic_id
                    })
            return cleaned_questions if cleaned_questions else self._fallback_quiz(topic_title, topic_content, topic_id, count, difficulty)
        except Exception as e:
            logger.warning(f"Gemini quiz generation error ({e}), using grounded fallback.")
            return self._fallback_quiz(topic_title, topic_content, topic_id, count, difficulty)

    # ==================== DETERMINISTIC GROUNDED FALLBACKS ====================
    # These ensure functionality even when offline or before the student sets GEMINI_API_KEY.

    def _fallback_summary(self, title: str, text: str, length: str) -> Dict[str, Any]:
        """Extracts key sentences and terms directly from text."""
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 25]
        paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 40]

        target_paras = 2 if length == "brief" else (4 if length == "standard" else 6)
        selected_text = "\n\n".join(paras[:target_paras]) if paras else text[:800]

        summary_body = (
            f"### Buod para sa: {title}\n\n"
            f"{selected_text}\n\n"
            f"> *Paalala ni Kabi: Ang buod na ito ay batay mismo sa mga pangunahing bahagi ng iyong in-upload na module.*"
        )

        # Extract terms using heuristic "Term is/are/refers to" or colon pattern
        key_terms = []
        term_patterns = re.findall(r'([A-Z][a-zA-Z\s]{2,30})\s*(?:is|are|refers to|means|—|-|:)\s*([^\.\n]{15,140}\.)', text)
        for term, definition in term_patterns[:8]:
            cleaned_term = term.strip(" -:")
            if len(cleaned_term.split()) <= 4 and cleaned_term.lower() not in ["chapter", "module", "the", "this"]:
                key_terms.append({
                    "term": cleaned_term,
                    "definition": definition.strip()
                })

        if not key_terms:
            # Fallback default key terms
            key_terms = [
                {"term": "Pangunahing Konsepto", "definition": f"Ang pangunahing aralin na tinatalakay sa {title}."},
                {"term": "Mahalagang Teorya", "definition": "Mga prinsipyo at batayang inilahad sa dokumento."}
            ]

        return {
            "summary": summary_body,
            "key_terms": key_terms
        }

    def _fallback_flashcards(self, topic_title: str, text: str, topic_id: Optional[int], count: int, card_type: str) -> List[Dict[str, Any]]:
        cards = []
        term_patterns = re.findall(r'([A-Z][a-zA-Z\s]{2,30})\s*(?:is|are|refers to|means|—|-|:)\s*([^\.\n]{15,140}\.)', text)
        for term, definition in term_patterns:
            cleaned_term = term.strip(" -:")
            if len(cleaned_term.split()) <= 4 and cleaned_term.lower() not in ["chapter", "module", "lesson"]:
                cards.append({
                    "front": f"Ano ang kahulugan ng {cleaned_term}?",
                    "back": definition.strip(),
                    "topic_id": topic_id,
                    "card_type": "term"
                })
            if len(cards) >= count:
                break

        # If not enough, create QA cards from key sentences
        if len(cards) < count:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if 35 < len(s.strip()) < 180]
            for i, s in enumerate(sentences):
                cards.append({
                    "front": f"Ano ang ipinapahayag ng sumusunod na punto sa {topic_title}?",
                    "back": s,
                    "topic_id": topic_id,
                    "card_type": "qa"
                })
                if len(cards) >= count:
                    break

        if not cards:
            cards = [{
                "front": f"Ano ang pangunahing layunin ng araling ito ({topic_title})?",
                "back": text[:150] + "...",
                "topic_id": topic_id,
                "card_type": "qa"
            }]

        return cards[:count]

    def _fallback_quiz(self, topic_title: str, text: str, topic_id: Optional[int], count: int, difficulty: str) -> List[Dict[str, Any]]:
        questions = []
        term_patterns = re.findall(r'([A-Z][a-zA-Z\s]{2,30})\s*(?:is|are|refers to|means|—|-|:)\s*([^\.\n]{15,140}\.)', text)
        terms = [t[0].strip(" -:") for t in term_patterns if len(t[0].strip(" -:").split()) <= 4]
        
        for i, (term, definition) in enumerate(term_patterns):
            cleaned_term = term.strip(" -:")
            if len(cleaned_term.split()) > 4:
                continue

            distractors = [t for t in terms if t != cleaned_term][:3]
            while len(distractors) < 3:
                distractors.append(f"Maling Konsepto #{len(distractors) + 1}")

            choices = [cleaned_term] + distractors
            # Keep index 0 as correct, or rotate
            correct_idx = i % 4
            choices[0], choices[correct_idx] = choices[correct_idx], choices[0]

            questions.append({
                "question": f"Alin sa mga sumusunod ang tumutukoy sa: \"{definition.strip()}\"?",
                "choices": choices,
                "correct_index": correct_idx,
                "explanation": f"Ayon sa module: Ang {cleaned_term} ay {definition.strip()}",
                "difficulty": difficulty if difficulty != "mixed" else ("easy" if i % 2 == 0 else "medium"),
                "topic_id": topic_id
            })

            if len(questions) >= count:
                break

        # Fallback question if none found
        if not questions:
            questions.append({
                "question": f"Tungkol saan ang pangunahing aralin sa {topic_title}?",
                "choices": [
                    f"Pag-unawa sa mga konsepto ng {topic_title}",
                    "Kasaysayan ng Sinaunang Daigdig",
                    "Teorya ng Quantum Gravity",
                    "Wala sa mga nabanggit"
                ],
                "correct_index": 0,
                "explanation": f"Batay sa dokumento, ang araling ito ay nakapokus sa {topic_title}.",
                "difficulty": "easy",
                "topic_id": topic_id
            })

        return questions[:count]

    # ==================== EXPLAINER CHAT (ASK KABISADO) ====================
    async def answer_document_question(
        self,
        document_title: str,
        topics: List[Dict[str, Any]],
        question: str,
        explain_like_new: bool = False,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Explains confusing parts of a document.
        Rules:
        - Grounded only in uploaded content. Do not invent facts.
        - Cite the specific section/topic it came from.
        - If the answer isn't in the material, say so clearly instead of guessing.
        - Includes 'explain like I'm new to this' toggle.
        Returns:
        {
          "answer": "...",
          "citation": "Kabanata X...",
          "found_in_document": true/false
        }
        """
        if not self.is_api_configured():
            return self._fallback_chat(document_title, topics, question, explain_like_new)

        context_blocks = []
        for t in topics:
            context_blocks.append(f"--- BAHAGI / TOPIC: {t.get('title', 'Aralin')} ---\n{t.get('content', '')[:6000]}")
        combined_context = "\n\n".join(context_blocks)

        system_prompt = (
            "You are Kabisado, an expert AI tutor for students. "
            "Tagline: 'Aral ngayon, pasa bukas.' "
            "Tone: You are friendly, relatable, slightly dramatic like a study buddy, but your academic explanations are 100% accurate, clear, and grounded. "
            "CRITICAL RULES:\n"
            "1. STRICT GROUNDING: Answer the question using ONLY the provided document content. DO NOT invent facts, assume unmentioned details, or bring in external knowledge.\n"
            "2. CITATION: Explicitly cite the specific section or topic where the information was found (e.g., 'Batay sa Kabanata 2: Ang Pag-usbong ng Kilusang Propaganda').\n"
            "3. HONESTY / NOT IN MATERIAL: If the answer is NOT present or cannot be inferred directly from the provided text, clearly and politely declare that the information is not in the uploaded material. Refuse to guess (e.g. 'Paumanhin lodi, pero wala sa in-upload mong module ang tungkol dito. Ayokong manghula baka ma-tres ka sa exam!'). In this case, set 'found_in_document' to false.\n"
            f"4. 'EXPLAIN LIKE I'M NEW' MODE: {'ON - Simplify difficult terminology using intuitive everyday Filipino real-world analogies (e.g., comparing parts of a cell to barangay officials, or algorithms to a recipe) while keeping facts intact.' if explain_like_new else 'OFF - Provide a direct, standard, rigorous academic explanation.'}\n"
            "5. OUTPUT FORMAT: Respond strictly in valid JSON matching this schema:\n"
            "{\n"
            '  "answer": "Clear explanation in friendly markdown...",\n'
            '  "citation": "Section or topic title (or null if not found)",\n'
            '  "found_in_document": true or false\n'
            "}"
        )

        user_prompt = (
            f"Document Title: {document_title}\n"
            f"Student Question: {question}\n\n"
            f"--- MODULE CONTEXT ---\n{combined_context[:30000]}"
        )

        try:
            res = await self._call_gemini_json(system_prompt, user_prompt)
            if isinstance(res, dict) and "answer" in res:
                return res
            return self._fallback_chat(document_title, topics, question, explain_like_new)
        except Exception as e:
            logger.warning(f"Gemini chat error ({e}), falling back to local grounded search.")
            return self._fallback_chat(document_title, topics, question, explain_like_new)

    def _fallback_chat(
        self,
        document_title: str,
        topics: List[Dict[str, Any]],
        question: str,
        explain_like_new: bool
    ) -> Dict[str, Any]:
        """Grounded keyword search across document topics when offline."""
        q_lower = question.lower()
        keywords = [w for w in re.findall(r'\b\w{3,}\b', q_lower) if w not in [
            "ano", "ang", "mga", "bakit", "paano", "sino", "saan", "kailan", "what", "is", "the", "are", "how", "why"
        ]]

        matched_topic = None
        matched_sentences = []

        for t in topics:
            content = t.get("content", "")
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', content) if len(s.strip()) > 20]
            for s in sentences:
                s_lower = s.lower()
                matches = sum(1 for kw in keywords if kw in s_lower)
                if matches > 0:
                    matched_sentences.append((matches, s, t.get("title", "Aralin")))

        if matched_sentences:
            matched_sentences.sort(key=lambda x: x[0], reverse=True)
            best_match = matched_sentences[0]
            best_topic = best_match[2]
            best_snippet = " ".join([m[1] for m in matched_sentences[:2]])

            prefix = "Ito ang simpleng paliwanag para mas madaling ma-gets:\n\n" if explain_like_new else ""
            ans_text = (
                f"{prefix}Ayon sa iyong module:\n\n"
                f"> {best_snippet}\n\n"
                f"*Pinagkunan: {best_topic}*"
            )
            return {
                "answer": ans_text,
                "citation": best_topic,
                "found_in_document": True
            }
        else:
            return {
                "answer": (
                    f"Pasensya na, lodi! Hinanap ko sa buong module na \"{document_title}\", "
                    f"pero parang wala roon ang impormasyon tungkol sa iyong tanong. "
                    f"Ayaw ni Kabi mag-imbento ng sagot baka magkamali ka pa sa exam! "
                    f"Pakisubukan magtanong tungkol sa mismong mga paksa sa module."
                ),
                "citation": None,
                "found_in_document": False
            }

ai_service = AIService()

