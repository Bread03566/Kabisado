import os
import json
import re
import asyncio
import logging
from collections import Counter
from typing import List, Dict, Any, Optional, Tuple
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
from app.config import settings

logger = logging.getLogger(__name__)

# Words that are never a useful flashcard term or a meaningful keyword on their own.
STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "of", "to", "in", "on", "at", "by", "for", "with",
    "from", "as", "is", "are", "was", "were", "be", "been", "being", "it", "its", "this", "that",
    "these", "those", "there", "here", "he", "she", "they", "we", "you", "i", "his", "her", "their",
    "our", "your", "my", "him", "them", "us", "which", "who", "whom", "what", "when", "where", "why",
    "how", "also", "not", "no", "so", "such", "can", "could", "may", "might", "will", "would",
    "should", "must", "has", "have", "had", "do", "does", "did", "into", "than", "then", "each",
    "other", "some", "any", "all", "most", "more", "many", "much", "very", "only", "both", "even",
    "although", "however", "while", "because", "about", "between", "after", "before", "during",
    "under", "over", "through", "one", "two", "chapter", "module", "lesson", "section", "part",
    "page", "unit", "topic", "example", "examples", "figure", "table",
    # Common Filipino function words, so keyword search also works on Tagalog questions
    "ano", "ang", "mga", "bakit", "paano", "sino", "saan", "kailan", "ng", "sa", "na",
}

DEFINITION_PATTERN = re.compile(
    r"^(?P<term>[A-Z][\w'’\-/() ]{1,60}?)\s+"
    # Plain "is/was" only counts when followed by an article ("X is a ..."), so
    # descriptions like "Discrimination was widespread" aren't treated as definitions.
    r"(?:(?:is defined as|refers to|is called|is known as|means)\s+|(?:is|are|was|were)\s+(?=(?:a|an|the|one)\s))"
    r"(?P<definition>.{15,220})$"
)
COLON_DEFINITION_PATTERN = re.compile(r"^(?P<term>[A-Z][\w'’\-/() ]{1,60}):\s+(?P<definition>.{15,220})$")
YEAR_PATTERN = re.compile(r"\b(1[0-9]{3}|20[0-9]{2})\b")
PROPER_PHRASE_PATTERN = re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+(?:(?:de|del|y|of|the)\s+)?[A-Z][a-zA-Z]+)*)")


def _is_heading_line(line: str) -> bool:
    return 0 < len(line.split()) <= 10 and not line.endswith((".", "!", "?", ",", ";"))


def _normalize(text: str) -> str:
    """Joins hard-wrapped lines inside paragraphs, keeping short heading-like lines on their own."""
    paragraphs: List[str] = []
    for block in re.split(r"\n\s*\n", text):
        current: List[str] = []
        for line in (l.strip() for l in block.splitlines()):
            if not line:
                continue
            if _is_heading_line(line):
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
                paragraphs.append(line)
            else:
                current.append(line)
        if current:
            paragraphs.append(" ".join(current))
    return "\n\n".join(re.sub(r"\s+", " ", p) for p in paragraphs)


def _sentences(text: str) -> List[str]:
    sentences = []
    for paragraph in _normalize(text).split("\n\n"):
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(])", paragraph):
            s = s.strip()
            if 30 <= len(s) <= 320 and s[-1] in ".!?":
                sentences.append(s)
    return sentences


def _clean_term(term: str) -> Optional[str]:
    term = re.sub(r"^(?:The|A|An)\s+", "", term.strip(" -:"))
    words = term.split()
    if not words or len(words) > 6:
        return None
    if words[0].lower() in STOPWORDS or term.lower() in STOPWORDS:
        return None
    return term[0].upper() + term[1:]


def _extract_definitions(text: str) -> List[Tuple[str, str]]:
    """Finds 'X is/refers to Y.' and 'X: Y' statements, skipping pronoun subjects like 'He is...'."""
    found: List[Tuple[str, str]] = []
    seen = set()
    candidates = _sentences(text) + [line.strip() for line in text.splitlines()]
    for candidate in candidates:
        match = COLON_DEFINITION_PATTERN.match(candidate) or DEFINITION_PATTERN.match(candidate)
        if not match:
            continue
        term = _clean_term(match.group("term"))
        if not term or term.lower() in seen:
            continue
        definition = match.group("definition").strip()
        definition = definition[0].upper() + definition[1:]
        if not definition.endswith((".", "!", "?")):
            definition += "."
        seen.add(term.lower())
        found.append((term, definition))
    return found


def _key_sentences(text: str, count: int) -> List[str]:
    """Classic extractive ranking: sentences full of the text's most frequent words, kept in reading order."""
    sentences = _sentences(text)
    words = [w for w in re.findall(r"[a-zA-Z]{3,}", text.lower()) if w not in STOPWORDS]
    freq = Counter(words)
    if not sentences or not freq:
        return sentences[:count]

    def score(s: str) -> float:
        tokens = [w for w in re.findall(r"[a-zA-Z]{3,}", s.lower()) if w not in STOPWORDS]
        return sum(freq[t] for t in tokens) / (len(tokens) + 4) if tokens else 0

    ranked = sorted(range(len(sentences)), key=lambda i: score(sentences[i]), reverse=True)[:count]
    return [sentences[i] for i in sorted(ranked)]


def _answer_candidates(text: str) -> Dict[str, List[str]]:
    """Years and proper-noun phrases that make good fill-in-the-blank answers and distractors."""
    years = list(dict.fromkeys(YEAR_PATTERN.findall(text)))
    phrases = []
    for s in _sentences(text):
        # Skip the sentence's first word, which is capitalized regardless of meaning
        for m in PROPER_PHRASE_PATTERN.finditer(s, pos=s.find(" ") + 1):
            phrase = m.group(1).strip()
            if len(phrase) > 3 and phrase.split()[0].lower() not in STOPWORDS:
                phrases.append(phrase)
    return {"year": years, "phrase": list(dict.fromkeys(phrases))}


def _make_cloze(sentence: str, candidates: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:
    year = YEAR_PATTERN.search(sentence)
    if year:
        return {"kind": "year", "answer": year.group(1), "prompt": sentence.replace(year.group(1), "_____", 1)}
    for phrase in sorted(candidates["phrase"], key=len, reverse=True):
        if phrase in sentence and not sentence.startswith(phrase):
            return {"kind": "phrase", "answer": phrase, "prompt": sentence.replace(phrase, "_____", 1)}
    return None


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
        Calls Gemini requesting JSON, trying each configured model in turn when one is
        overloaded, too slow, or keeps returning malformed JSON.
        """
        if not self.client:
            raise RuntimeError("Gemini API key is not configured.")

        last_error: Optional[Exception] = None
        for model in settings.gemini_models:
            try:
                return await self._call_model_json(model, system_prompt, user_prompt, retry_count)
            except (asyncio.TimeoutError, genai_errors.APIError, ValueError) as err:
                logger.warning(f"Gemini model {model} failed ({type(err).__name__}: {str(err)[:200]}); trying next option.")
                last_error = err
        raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")

    async def _call_model_json(self, model: str, system_prompt: str, user_prompt: str, retry_count: int) -> Any:
        """Calls one model, validating the JSON and retrying once if malformed."""
        contents = user_prompt
        content_text = ""

        for attempt in range(retry_count + 1):
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        temperature=0.2,
                        response_mime_type="application/json",
                    ),
                ),
                timeout=settings.GEMINI_TIMEOUT_SECONDS,
            )
            content_text = response.text or ""
            try:
                return self._extract_and_parse_json(content_text)
            except (json.JSONDecodeError, ValueError) as err:
                logger.warning(f"Gemini JSON parsing failed on attempt {attempt + 1}: {err}")
                contents = (
                    f"{user_prompt}\n\nYour previous response was not valid JSON:\n"
                    f"{content_text}\n\nRespond ONLY with a valid JSON object or array. "
                    "Do not include markdown code blocks or explanations."
                )
        raise ValueError(f"AI response was not valid JSON after retry: {content_text[:200]}")

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
            "Tone: You are friendly, relatable, slightly witty, but when explaining academic material, your explanations are strictly accurate, crystal-clear, and serious. "
            "Start the summary with the content itself: no greeting, slogan, or introduction of yourself. "
            "LANGUAGE: Always write the summary and key terms in English, even if the source text is in another language. "
            "CRITICAL RULE: Base your summary and key terms strictly on the provided text. Do NOT invent facts or hallucinate external information. "
            "Ignore page headers, footers, page numbers, and copyright lines. "
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
            result["key_terms"] = [
                {"term": str(k["term"]), "definition": str(k["definition"])}
                for k in result["key_terms"]
                if isinstance(k, dict) and k.get("term") and k.get("definition")
            ]
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
            "4. Write every card in English, even if the source text is in another language.\n"
            "5. Return strict JSON array of flashcard objects matching this exact structure:\n"
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
                if isinstance(c, dict) and "front" in c and "back" in c:
                    cleaned_cards.append({
                        "front": str(c["front"]).strip(),
                        "back": str(c["back"]).strip(),
                        "topic_id": topic_id,
                        "card_type": c.get("card_type") if c.get("card_type") in ("term", "qa") else "term"
                    })
            return cleaned_cards[:count] if cleaned_cards else self._fallback_flashcards(topic_title, topic_content, topic_id, count, card_type)
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
            "4. Write every question, choice, and explanation in English, even if the source text is in another language.\n"
            "5. Return strict JSON array matching this schema:\n"
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
                if isinstance(q, dict) and "question" in q and isinstance(q.get("choices"), list) and len(q["choices"]) == 4:
                    try:
                        c_idx = int(q.get("correct_index", 0))
                    except (TypeError, ValueError):
                        continue
                    if c_idx < 0 or c_idx > 3:
                        continue
                    diff = q.get("difficulty", difficulty)
                    if diff not in ["easy", "medium", "hard"]:
                        diff = "medium"
                    cleaned_questions.append({
                        "question": str(q["question"]).strip(),
                        "choices": [str(c).strip() for c in q["choices"]],
                        "correct_index": c_idx,
                        "explanation": str(q.get("explanation", "Based on the module content.")).strip(),
                        "difficulty": diff,
                        "topic_id": topic_id
                    })
            return cleaned_questions[:count] if cleaned_questions else self._fallback_quiz(topic_title, topic_content, topic_id, count, difficulty)
        except Exception as e:
            logger.warning(f"Gemini quiz generation error ({e}), using grounded fallback.")
            return self._fallback_quiz(topic_title, topic_content, topic_id, count, difficulty)

    # ==================== DETERMINISTIC GROUNDED FALLBACKS ====================
    # These keep the app useful offline or before the student sets GEMINI_API_KEY.

    def _fallback_summary(self, title: str, text: str, length: str) -> Dict[str, Any]:
        """Extractive summary: the text's most representative sentences, as bullet points."""
        point_count = {"brief": 4, "standard": 8, "detailed": 14}.get(length, 8)
        points = _key_sentences(text, point_count)
        if points:
            body = "\n".join(f"- {p}" for p in points)
        else:
            body = _normalize(text)[:800]

        summary_body = (
            f"### Key points from {title}\n\n"
            f"{body}\n\n"
            f"> *Note from Kabi: these points are taken directly from your module. "
            f"Connect an AI key for a written summary.*"
        )
        key_terms = [{"term": t, "definition": d} for t, d in _extract_definitions(text)[:10]]
        return {"summary": summary_body, "key_terms": key_terms}

    def _fallback_flashcards(self, topic_title: str, text: str, topic_id: Optional[int], count: int, card_type: str) -> List[Dict[str, Any]]:
        cards: List[Dict[str, Any]] = []
        if card_type in ("term", "mixed"):
            for term, definition in _extract_definitions(text):
                cards.append({"front": f"What is {term}?", "back": definition, "topic_id": topic_id, "card_type": "term"})
                if len(cards) >= count:
                    return cards

        candidates = _answer_candidates(text)
        for sentence in _key_sentences(text, count * 3):
            if len(cards) >= count:
                break
            cloze = _make_cloze(sentence, candidates)
            if cloze:
                cards.append({
                    "front": f"Fill in the blank: {cloze['prompt']}",
                    "back": f"{cloze['answer']}. {sentence}",
                    "topic_id": topic_id,
                    "card_type": "qa"
                })
        return cards[:count]

    def _fallback_quiz(self, topic_title: str, text: str, topic_id: Optional[int], count: int, difficulty: str) -> List[Dict[str, Any]]:
        questions: List[Dict[str, Any]] = []

        def level(i: int) -> str:
            return difficulty if difficulty != "mixed" else ("easy" if i % 2 == 0 else "medium")

        def add(question: str, answer: str, distractors: List[str], explanation: str) -> None:
            if len(distractors) < 3:
                return
            correct_idx = len(questions) % 4
            choices = distractors[:3]
            choices.insert(correct_idx, answer)
            questions.append({
                "question": question,
                "choices": choices,
                "correct_index": correct_idx,
                "explanation": explanation,
                "difficulty": level(len(questions)),
                "topic_id": topic_id
            })

        definitions = _extract_definitions(text)
        terms = [t for t, _ in definitions]
        for term, definition in definitions:
            if len(questions) >= count:
                return questions
            others = [t for t in terms if t != term]
            add(
                f"Which term matches this description: \"{definition}\"",
                term,
                others,
                f"According to the module, {term}: {definition}"
            )

        candidates = _answer_candidates(text)
        for sentence in _key_sentences(text, count * 4):
            if len(questions) >= count:
                break
            cloze = _make_cloze(sentence, candidates)
            if not cloze:
                continue
            pool = [c for c in candidates[cloze["kind"]] if c != cloze["answer"] and c not in sentence]
            add(
                f"Fill in the blank: {cloze['prompt']}",
                cloze["answer"],
                pool,
                f"The module states: \"{sentence}\""
            )
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
          "citation": "Chapter X...",
          "found_in_document": true/false
        }
        """
        if not self.is_api_configured():
            return self._fallback_chat(document_title, topics, question, explain_like_new)

        context_blocks = []
        for t in topics:
            context_blocks.append(f"--- SECTION / TOPIC: {t.get('title', 'Lesson')} ---\n{t.get('content', '')[:6000]}")
        combined_context = "\n\n".join(context_blocks)

        system_prompt = (
            "You are Kabisado, an expert AI tutor for students. "
            "Tone: You are friendly, relatable, slightly dramatic like a study buddy, but your academic explanations are 100% accurate, clear, and grounded. "
            "Get straight to the answer: don't open with a greeting, a slogan, or the student's question repeated back. "
            "CRITICAL RULES:\n"
            "1. STRICT GROUNDING: Answer the question using ONLY the provided document content. DO NOT invent facts, assume unmentioned details, or bring in external knowledge.\n"
            "2. CITATION: Explicitly cite the specific section or topic where the information was found (e.g., 'Based on Chapter 2: The Rise of the Propaganda Movement').\n"
            "3. HONESTY / NOT IN MATERIAL: If the answer is NOT present or cannot be inferred directly from the provided text, clearly and politely declare that the information is not in the uploaded material. Refuse to guess (e.g. 'Sorry, friend, but your uploaded module doesn't cover this. I'd rather not guess and risk you getting it wrong on the exam!'). In this case, set 'found_in_document' to false.\n"
            f"4. 'EXPLAIN LIKE I'M NEW' MODE: {'ON - Simplify difficult terminology using intuitive everyday real-world analogies (e.g., comparing parts of a cell to barangay officials, or algorithms to a recipe) while keeping facts intact.' if explain_like_new else 'OFF - Provide a direct, standard, rigorous academic explanation.'}\n"
            "5. LANGUAGE: Always answer in English, even if the module or the question is in another language.\n"
            "6. CONVERSATION: Use the recent conversation only to understand follow-up questions (e.g. what 'it' refers to). The module is still the only source of facts.\n"
            "7. OUTPUT FORMAT: Respond strictly in valid JSON matching this schema:\n"
            "{\n"
            '  "answer": "Clear explanation in friendly markdown...",\n'
            '  "citation": "Section or topic title (or null if not found)",\n'
            '  "found_in_document": true or false\n'
            "}"
        )

        history_lines = []
        for turn in (conversation_history or [])[-6:]:
            role = "Student" if turn.get("role") == "user" else "Kabisado"
            content = str(turn.get("content", "")).strip()
            if content:
                history_lines.append(f"{role}: {content[:1000]}")
        history_block = ("--- RECENT CONVERSATION ---\n" + "\n".join(history_lines) + "\n\n") if history_lines else ""

        user_prompt = (
            f"Document Title: {document_title}\n"
            f"{history_block}"
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
        keywords = [w for w in re.findall(r"\b\w{3,}\b", question.lower()) if w not in STOPWORDS]

        matched_sentences = []
        for t in topics:
            for s in _sentences(t.get("content", "")):
                s_lower = s.lower()
                matches = sum(1 for kw in keywords if kw in s_lower)
                if matches > 0:
                    matched_sentences.append((matches, s, t.get("title", "Lesson")))

        if matched_sentences:
            matched_sentences.sort(key=lambda x: x[0], reverse=True)
            best_topic = matched_sentences[0][2]
            best_snippet = " ".join(m[1] for m in matched_sentences[:2])

            prefix = "Here's a simple explanation to make it easier to understand:\n\n" if explain_like_new else ""
            ans_text = (
                f"{prefix}According to your module:\n\n"
                f"> {best_snippet}\n\n"
                f"*Source: {best_topic}*"
            )
            return {
                "answer": ans_text,
                "citation": best_topic,
                "found_in_document": True
            }
        return {
            "answer": (
                f"Sorry, friend! I searched the whole module \"{document_title}\", "
                f"but it doesn't seem to have information about your question. "
                f"Kabi doesn't want to make up an answer and have you get it wrong on the exam! "
                f"Try asking about the topics covered in the module."
            ),
            "citation": None,
            "found_in_document": False
        }

ai_service = AIService()
