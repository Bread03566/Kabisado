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
from app.services import consent, retrieval
from app.services.segmenter_service import segmenter_service

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
        if (settings.GEMINI_ENABLED and self.api_key and self.api_key.strip()
                and not self.api_key.startswith("demo_")):
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini client: {e}")
                self.client = None

    def is_api_configured(self) -> bool:
        # Checked on every call, not just at startup, so the switch holds even if a client exists.
        return bool(settings.GEMINI_ENABLED) and self.client is not None

    def may_use_gemini(self, user_id: Optional[int]) -> bool:
        """Engine choice for one student: Gemini only if it is configured AND this student has consented."""
        return self.is_api_configured() and consent.authorize(user_id)

    async def _call_gemini_json(self, system_prompt: str, user_prompt: str, retry_count: int = 1,
                                user_id: Optional[int] = None, feature: str = "ai") -> Any:
        """
        Calls Gemini requesting JSON, trying each configured model in turn when one is
        overloaded, too slow, or keeps returning malformed JSON.
        """
        if not self.is_api_configured():
            raise RuntimeError("Gemini is disabled or not configured.")

        last_error: Optional[Exception] = None
        for model in settings.gemini_models:
            try:
                return await self._call_model_json(model, system_prompt, user_prompt, retry_count, user_id, feature)
            except (asyncio.TimeoutError, genai_errors.APIError, ValueError) as err:
                logger.warning(f"Gemini model {model} failed ({type(err).__name__}: {str(err)[:200]}); trying next option.")
                last_error = err
        raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")

    async def _call_model_json(self, model: str, system_prompt: str, user_prompt: str, retry_count: int,
                               user_id: Optional[int] = None, feature: str = "ai") -> Any:
        """Calls one model, validating the JSON and retrying once if malformed."""
        contents = user_prompt
        content_text = ""

        for attempt in range(retry_count + 1):
            # Consent is re-read from the database before EVERY request, including retries and fallback models.
            if not consent.reserve_gemini_call(user_id, feature):
                raise PermissionError("Gemini is not permitted for this student right now.")
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
        length: str = "standard",  # "brief" | "standard" | "detailed"
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generates a summary of the given length and a list of key terms with definitions.
        Rules:
        - Grounded only in uploaded text. Do not invent facts.
        - Structured JSON output: { "summary": "...", "key_terms": [{"term": "...", "definition": "..."}] }
        """
        if not self.may_use_gemini(user_id):
            return self._fallback_summary(document_title, text_content, length)

        length_instructions = {
            "brief": "Keep it short: 2 to 3 sections with 2 to 3 bullets each, covering only the core takeaways.",
            "standard": "Use 3 to 5 sections with 3 to 4 bullets each, covering the major concepts and how they connect.",
            "detailed": "Use 5 to 7 sections with 3 to 6 bullets each, covering every essential sub-topic, mechanism, and example in the text."
        }

        system_prompt = (
            "You are Kabisado, an expert AI study buddy for Filipino students. "
            "Tone: You are friendly, relatable, slightly witty, but when explaining academic material, your explanations are strictly accurate, crystal-clear, and serious. "
            "Start the summary with the content itself: no greeting, slogan, or introduction of yourself. "
            "LANGUAGE: Always write the summary and key terms in English, even if the source text is in another language. "
            "CRITICAL RULE: Base your summary and key terms strictly on the provided text. Do NOT invent facts or hallucinate external information. "
            "Ignore page headers, footers, page numbers, and copyright lines. "
            "SUMMARY FORMAT (markdown, the app turns it into study cards, so follow it exactly):\n"
            "- Start with ONE short paragraph (1 to 2 sentences, no heading) stating the big idea of the whole lesson.\n"
            "- Then one '## ' heading per major concept, in the order the text teaches them. Headings are short (2 to 6 words).\n"
            "- Under each heading, '- ' bullet points only (no paragraphs): one fact or idea per bullet, at most 30 words. Put the most important word or phrase in **bold**.\n"
            "- Optionally end a section with one line '> Exam tip: ...' naming something likely to be tested (a date, a distinction, a common mix-up).\n"
            "Always respond in valid, strict JSON with this exact schema:\n"
            "{\n"
            '  "summary": "Markdown following the SUMMARY FORMAT...",\n'
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
            result = await self._call_gemini_json(system_prompt, user_prompt, user_id=user_id, feature="summary")
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
        card_type: str = "mixed",  # "term", "qa", or "mixed"
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates flashcards tagged by topic.
        Flashcard JSON: [ { "front": "...", "back": "...", "topic_id": "...", "card_type": "term" | "qa" } ]
        """
        if not self.may_use_gemini(user_id):
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
            cards = await self._call_gemini_json(system_prompt, user_prompt, user_id=user_id, feature="flashcards")
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
    TYPE_SCHEMAS = {
        "multiple_choice": (
            '{"type": "multiple_choice", "style": "definition|situational", "question": "...?", '
            '"choices": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "..."}  '
            "(exactly 4 choices, one unambiguously correct, 3 plausible distractors from the same text)"
        ),
        "true_false": (
            '{"type": "true_false", "style": "definition|situational", "question": "A statement to judge.", '
            '"answer": true, "explanation": "..."}  '
            "(a single clear statement, not a question; false statements change one key fact from the text)"
        ),
        "identification": (
            '{"type": "identification", "style": "definition|situational", "question": "...?", '
            '"answer": "short answer", "accepted_answers": ["other acceptable spellings"], "explanation": "..."}  '
            "(the answer is a term, name, number, or date of 1 to 5 words that the student types)"
        ),
        "matching": (
            '{"type": "matching", "style": "definition|situational", "question": "Match each term to its description.", '
            '"pairs": [{"term": "...", "definition": "..."}], "explanation": "..."}  '
            "(4 pairs with distinct terms; definitions short enough to read at a glance)"
        ),
    }
    STYLE_RULES = {
        "definition": "Every question is DEFINITION style: it checks recall of a term, fact, or definition straight from the text.",
        "situational": (
            "Every question is SITUATIONAL style: it opens with a short realistic scenario (1 to 3 sentences, everyday "
            "or workplace) and asks the student to apply a concept from the text. For matching, pair short scenarios "
            "with the concept each one illustrates."
        ),
        "mixed": "Mix DEFINITION questions (recall) and SITUATIONAL questions (a short scenario that applies a concept), about half each.",
    }

    async def generate_quiz_questions(
        self,
        document_title: str,
        topic_title: str,
        topic_content: str,
        topic_id: Optional[int] = None,
        count: int = 5,
        difficulty: str = "medium",  # "easy", "medium", "hard", "mixed"
        question_types: Optional[List[str]] = None,  # one entry per question, e.g. ["identification", "matching"]
        style: str = "mixed",  # "definition", "situational", "mixed"
        question_styles: Optional[List[str]] = None,  # one entry per question; overrides `style` when given
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generates quiz questions of the requested types and style. Every returned dict has:
        question, choices, correct_index, explanation, difficulty, topic_id, question_type, style, answer_data.
        """
        question_types = question_types or ["multiple_choice"] * count
        if not question_styles:
            # "mixed" alternates, so a short quiz still gets both kinds
            question_styles = [
                ("situational" if i % 2 == 0 else "definition") if style == "mixed" else style
                for i in range(len(question_types))
            ]
        if not self.may_use_gemini(user_id):
            return self._fallback_quiz(topic_title, topic_content, topic_id, count, difficulty, question_types)

        # Small models drift toward recall questions when asked for "a mix", so each slot names its style
        wanted = "\n".join(f"{i + 1}. {t}, {s}" for i, (t, s) in enumerate(zip(question_types, question_styles)))
        styles_used = set(question_styles)
        style_rule = self.STYLE_RULES["mixed"] if len(styles_used) > 1 else self.STYLE_RULES[next(iter(styles_used))]
        schemas = "\n".join(f"- {self.TYPE_SCHEMAS[t]}" for t in dict.fromkeys(question_types))
        system_prompt = (
            "You are Kabisado, an expert exam maker for college and high school students. "
            "Write quiz questions grounded STRICTLY in the provided text: never test facts the text does not state.\n"
            "Rules:\n"
            f"1. {style_rule} DEFINITION style checks recall of a term or fact. SITUATIONAL style must open with a short realistic scenario (1 to 3 sentences) and ask the student to apply a concept; set \"style\" on every item.\n"
            "2. Each explanation says why the answer is right, citing the text, and for multiple choice why the others are wrong.\n"
            "3. Write everything in English, even if the source text is in another language.\n"
            f"4. Difficulty: {difficulty if difficulty != 'mixed' else 'a mix of easy, medium, and hard'}.\n"
            "5. Return a strict JSON array. Each item uses the shape for its type:\n"
            f"{schemas}"
        )
        user_prompt = (
            f"Topic: {topic_title}\n"
            f"Write exactly these questions, in this order (type, style):\n{wanted}\n\n"
            f"--- TEXT CONTENT ---\n{topic_content[:15000]}"
        )

        try:
            raw = await self._call_gemini_json(system_prompt, user_prompt, user_id=user_id, feature="quiz")
            if isinstance(raw, dict):
                raw = raw.get("questions", [])
            if not isinstance(raw, list):
                raise ValueError("Questions response is not a list")

            cleaned = [
                q for q in (self._clean_ai_question(item, difficulty, style, topic_id) for item in raw)
                if q and q["question_type"] in question_types
            ]
            # Keep the requested mix: fill each slot with a question of that type, preferring the asked-for style
            picked: List[Dict[str, Any]] = []
            for wanted_type, wanted_style in zip(question_types, question_styles):
                same_type = [q for q in cleaned if q["question_type"] == wanted_type]
                match = next((q for q in same_type if q["style"] == wanted_style), same_type[0] if same_type else None)
                if match:
                    cleaned.remove(match)
                    picked.append(match)
            return picked or self._fallback_quiz(topic_title, topic_content, topic_id, count, difficulty, question_types)
        except Exception as e:
            logger.warning(f"Gemini quiz generation error ({e}), using grounded fallback.")
            return self._fallback_quiz(topic_title, topic_content, topic_id, count, difficulty, question_types)

    @staticmethod
    def _clean_ai_question(q: Any, difficulty: str, style: str, topic_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """Validates one AI-written question against its type; returns None if it is unusable."""
        if not isinstance(q, dict) or not str(q.get("question", "")).strip():
            return None
        qtype = q.get("type", "multiple_choice")
        diff = q.get("difficulty") if q.get("difficulty") in ("easy", "medium", "hard") else (difficulty if difficulty != "mixed" else "medium")
        q_style = q.get("style") if q.get("style") in ("definition", "situational") else (style if style != "mixed" else "definition")
        result = {
            "question": str(q["question"]).strip(),
            "explanation": str(q.get("explanation") or "Based on the module content.").strip(),
            "difficulty": diff,
            "topic_id": topic_id,
            "question_type": qtype,
            "style": q_style,
            "choices": [],
            "correct_index": 0,
            "answer_data": None,
        }

        if qtype == "multiple_choice":
            choices = q.get("choices")
            if not isinstance(choices, list) or len(choices) != 4:
                return None
            try:
                idx = int(q.get("correct_index", 0))
            except (TypeError, ValueError):
                return None
            if not 0 <= idx <= 3:
                return None
            result.update(choices=[str(c).strip() for c in choices], correct_index=idx)
        elif qtype == "true_false":
            answer = q.get("answer")
            if isinstance(answer, str):
                answer = {"true": True, "false": False}.get(answer.strip().lower())
            if not isinstance(answer, bool):
                return None
            result.update(choices=["True", "False"], correct_index=0 if answer else 1)
        elif qtype == "identification":
            answer = str(q.get("answer") or "").strip()
            if not answer or len(answer) > 80:
                return None
            alternates = [str(a).strip() for a in (q.get("accepted_answers") or []) if str(a).strip()][:5]
            result["answer_data"] = {"answer": answer, "accepted_answers": alternates}
        elif qtype == "matching":
            pairs = []
            seen = set()
            for p in q.get("pairs") or []:
                if isinstance(p, dict) and p.get("term") and p.get("definition") and str(p["term"]).lower() not in seen:
                    seen.add(str(p["term"]).lower())
                    pairs.append({"term": str(p["term"]).strip(), "definition": str(p["definition"]).strip()})
            if not 3 <= len(pairs) <= 6:
                return None
            result["answer_data"] = {"pairs": pairs}
        else:
            return None
        return result

    # ==================== DETERMINISTIC GROUNDED FALLBACKS ====================
    # These keep the app useful offline or before the student sets GEMINI_API_KEY.

    def _fallback_summary(self, title: str, text: str, length: str) -> Dict[str, Any]:
        """
        Extractive summary in the same shape the AI writes: a one-line big idea, then one
        section per topic with that topic's most representative sentences as bullets.
        """
        max_sections, bullets_per_section = {"brief": (4, 2), "standard": (6, 3), "detailed": (12, 5)}.get(length, (6, 3))

        overview = _key_sentences(text, 1)
        parts = [overview[0] if overview else f"Key points from {title}."]
        for topic in segmenter_service.segment_text(text, document_title=title)[:max_sections]:
            bullets = _key_sentences(topic["content"], bullets_per_section)
            if not bullets:
                continue
            parts.append(f"## {topic['title']}")
            parts.append("\n".join(f"- {YEAR_PATTERN.sub(r'**\1**', b)}" for b in bullets))
            years = list(dict.fromkeys(y for b in bullets for y in YEAR_PATTERN.findall(b)))
            if years:
                parts.append(f"> Exam tip: Expect a question on **{', '.join(years)}**. Know what happened then.")

        if len(parts) == 1:
            parts.append(_normalize(text)[:800])
        summary_body = "\n\n".join(parts)
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

    def _fallback_quiz(
        self,
        topic_title: str,
        text: str,
        topic_id: Optional[int],
        count: int,
        difficulty: str,
        question_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Offline questions of each type, built from the text's own definitions and from
        fill-in-the-blank sentences (years and names). Situational questions need the AI to
        write scenarios, so offline questions are always definition style.
        """
        types = question_types or ["multiple_choice"] * count
        definitions = list(_extract_definitions(text))
        terms = [t for t, _ in definitions]
        candidates = _answer_candidates(text)
        clozes = []
        for sentence in _key_sentences(text, max(12, count * 4)):
            cloze = _make_cloze(sentence, candidates)
            if cloze:
                clozes.append((sentence, cloze))

        questions: List[Dict[str, Any]] = []

        def make(qtype: str, question: str, explanation: str, **fields) -> Dict[str, Any]:
            n = len(questions)
            return {
                "question": question,
                "explanation": explanation,
                "difficulty": difficulty if difficulty != "mixed" else ("easy" if n % 2 == 0 else "medium"),
                "topic_id": topic_id,
                "question_type": qtype,
                "style": "definition",
                "choices": fields.get("choices", []),
                "correct_index": fields.get("correct_index", 0),
                "answer_data": fields.get("answer_data"),
            }

        def distractors_for(cloze: Dict[str, Any], sentence: str) -> List[str]:
            return [c for c in candidates[cloze["kind"]] if c != cloze["answer"] and c not in sentence]

        def multiple_choice() -> Optional[Dict[str, Any]]:
            correct_idx = len(questions) % 4
            if definitions and len(terms) >= 4:
                term, definition = definitions.pop(0)
                choices = [t for t in terms if t != term][:3]
                choices.insert(correct_idx, term)
                return make("multiple_choice", f"Which term matches this description: \"{definition}\"",
                            f"According to the module, {term}: {definition}", choices=choices, correct_index=correct_idx)
            while clozes:
                sentence, cloze = clozes.pop(0)
                pool = distractors_for(cloze, sentence)
                if len(pool) >= 3:
                    choices = pool[:3]
                    choices.insert(correct_idx, cloze["answer"])
                    return make("multiple_choice", f"Fill in the blank: {cloze['prompt']}",
                                f"The module states: \"{sentence}\"", choices=choices, correct_index=correct_idx)
            return None

        def true_false() -> Optional[Dict[str, Any]]:
            while clozes:
                sentence, cloze = clozes.pop(0)
                pool = distractors_for(cloze, sentence)
                make_false = len(questions) % 2 == 1 and pool
                statement = cloze["prompt"].replace("_____", pool[0] if make_false else cloze["answer"], 1)
                return make("true_false", statement, f"The module states: \"{sentence}\"",
                            choices=["True", "False"], correct_index=1 if make_false else 0)
            return None

        def identification() -> Optional[Dict[str, Any]]:
            if definitions:
                term, definition = definitions.pop(0)
                return make("identification", f"What term is described here? \"{definition}\"",
                            f"According to the module, {term}: {definition}", answer_data={"answer": term, "accepted_answers": []})
            if clozes:
                sentence, cloze = clozes.pop(0)
                return make("identification", f"Fill in the blank: {cloze['prompt']}", f"The module states: \"{sentence}\"",
                            answer_data={"answer": cloze["answer"], "accepted_answers": []})
            return None

        def matching() -> Optional[Dict[str, Any]]:
            if len(definitions) >= 3:
                pairs = [{"term": t, "definition": d} for t, d in definitions[:4]]
                del definitions[:4]
                return make("matching", "Match each term to its description.",
                            "Each description is taken from the module's own definitions.", answer_data={"pairs": pairs})
            pairs, used = [], set()
            for sentence, cloze in list(clozes):
                if cloze["answer"] not in used:
                    used.add(cloze["answer"])
                    pairs.append({"term": cloze["answer"], "definition": cloze["prompt"]})
                    clozes.remove((sentence, cloze))
                if len(pairs) == 4:
                    break
            if len(pairs) >= 3:
                return make("matching", "Match each answer to the sentence it completes.",
                            "Each sentence comes straight from the module.", answer_data={"pairs": pairs})
            return None

        makers = {"multiple_choice": multiple_choice, "true_false": true_false, "identification": identification, "matching": matching}
        for qtype in types:
            question = makers.get(qtype, multiple_choice)() or (multiple_choice() if qtype != "multiple_choice" else None)
            if question:
                questions.append(question)
        return questions

    # ==================== EXPLAINER CHAT (ASK KABISADO) ====================
    async def answer_document_question(
        self,
        document_title: str,
        topics: List[Dict[str, Any]],
        question: str,
        explain_like_new: bool = False,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_id: Optional[int] = None,
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
        if not self.may_use_gemini(user_id):
            return self._fallback_chat(document_title, topics, question, explain_like_new, conversation_history)

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
            res = await self._call_gemini_json(system_prompt, user_prompt, user_id=user_id, feature="chat")
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
        explain_like_new: bool,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Grounded answer from the student's own material when Gemini is not used: ranked passages, or an honest 'not found'."""
        ranked = retrieval.rank(retrieval.build_chunks(topics), question, history=conversation_history)
        if ranked:
            best_score, best = ranked[0]
            passages = [best.text]
            if len(ranked) > 1 and ranked[1][0] >= 0.75 * best_score and ranked[1][1].text != best.text:
                passages.append(ranked[1][1].text)  # a second passage only when it is nearly as relevant
            prefix = "Here's a simple explanation to make it easier to understand:\n\n" if explain_like_new else ""
            quoted = "\n\n".join(f"> {p}" for p in passages)
            return {
                "answer": f"{prefix}According to your module:\n\n{quoted}\n\n*Source: {best.citation}*",
                "citation": best.citation,
                "found_in_document": True,
            }
        return {
            "answer": (
                f"Sorry, friend! I searched the whole module \"{document_title}\", "
                f"but it doesn't seem to have information about your question. "
                f"Kabi doesn't want to make up an answer and have you get it wrong on the exam! "
                f"Try asking about the topics covered in the module."
            ),
            "citation": None,
            "found_in_document": False,
        }

ai_service = AIService()
