import re
from typing import List, Dict, Optional

class SegmenterService:
    # Common academic heading patterns:
    # 1. Markdown headings: # Chapter 1, ## Section
    # 2. Module / Chapter / Lesson / Unit headers: Chapter 1: Introduction, Module 2 - Biology
    # 3. Roman numerals or numbering: I. Introduction, 1.0 Overview, A. Definitions
    HEADING_REGEX = re.compile(
        r"^(?:"
        r"#{1,4}\s+(.+)|"  # Markdown headings
        r"(?:(?:Chapter|Module|Lesson|Unit|Part|Section|Topic)\s+[0-9IVXLCDMivxlcdm]+[:\.\-–—\s]+[^\n]+)|"  # Chapter 1: ...
        r"(?:[0-9]{1,2}\.[0-9]{1,2}(?:\.[0-9]{1,2})?\s+[A-Z][^\n]+)|"  # 1.1 Topic Name
        r"(?:[IVXLCDM]+\.\s+[A-Z][^\n]+)|"  # I. Roman Title
        r"(?:[A-Z\s]{4,40}:)"  # ALL CAPS HEADER:
        r")$",
        re.MULTILINE
    )
    # Course codes and reference numbers ("IT2602", "CS101-A") look like ALL CAPS headings but aren't.
    CODE_LIKE = re.compile(r"^[A-Z]{1,6}[\s\-]?\d[\w\-]*$")
    BULLET_PREFIX = re.compile(r"^(?:[•\-\*o]\s|\d+[\.\)]\s|[a-z][\.\)]\s)")

    MAX_TOPICS = 12
    MIN_SECTION_WORDS = 15

    @classmethod
    def _is_title_line(cls, line: str, prev_line: Optional[str], next_line: Optional[str]) -> bool:
        """A short Title-style line standing between sentences, e.g. 'Domain Name System'."""
        words = line.split()
        if not 2 <= len(words) <= 10 or len(line) > 90:
            return False
        if not line[0].isupper() or line.endswith((".", ",", ";", ":", "!", "?")):
            return False
        if cls.BULLET_PREFIX.match(line):
            return False
        prev_closed = prev_line is None or prev_line.endswith((".", "!", "?", ":"))
        next_starts_sentence = next_line is not None and (next_line[0].isupper() or next_line[0].isdigit())
        return prev_closed and next_starts_sentence

    @classmethod
    def _heading_title(cls, line: str, prev_line: Optional[str], next_line: Optional[str]) -> Optional[str]:
        if cls.CODE_LIKE.match(line):
            return None
        if cls.HEADING_REGEX.match(line):
            return re.sub(r"^#{1,4}\s*", "", line).strip().rstrip(":")
        if len(line) < 60 and line.isupper() and len(line.split()) <= 8 and sum(c.isalpha() for c in line) >= 4:
            return line.title()
        if cls._is_title_line(line, prev_line, next_line):
            return line
        return None

    @classmethod
    def segment_text(cls, raw_text: str, document_title: str = "Document") -> List[Dict[str, str]]:
        """
        Segments raw document text into logical topic sections.
        Returns a list of dicts: [{"title": "...", "content": "...", "order_index": 0}]
        """
        cleaned = raw_text.strip()
        non_empty = [line.strip() for line in cleaned.split("\n") if line.strip()]

        sections: List[Dict[str, str]] = []
        current_title = "Introduction / Overview"
        current_paragraphs: List[str] = []

        for i, stripped in enumerate(non_empty):
            prev_line = non_empty[i - 1] if i > 0 else None
            next_line = non_empty[i + 1] if i + 1 < len(non_empty) else None
            heading = cls._heading_title(stripped, prev_line, next_line)

            if heading:
                if current_paragraphs:
                    sections.append({"title": current_title, "content": "\n".join(current_paragraphs)})
                    current_paragraphs = []
                current_title = heading
            else:
                current_paragraphs.append(stripped)

        if current_paragraphs:
            sections.append({"title": current_title, "content": "\n".join(current_paragraphs)})

        sections = cls._merge_small_sections(sections)

        # Fallback if no headings matched or only 1 big section was generated
        if len(sections) <= 1:
            return cls._fallback_chunking(cleaned, document_title)

        return [
            {"title": s["title"], "content": s["content"], "order_index": i}
            for i, s in enumerate(sections)
        ]

    @classmethod
    def _merge_small_sections(cls, sections: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Folds near-empty sections into a neighbour, then merges the smallest until the cap is met."""
        def words(s: Dict[str, str]) -> int:
            return len(s["content"].split())

        def merge_into_neighbour(idx: int) -> None:
            if idx == 0:
                target, source = 0, 1
            elif idx == len(sections) - 1 or words(sections[idx - 1]) <= words(sections[idx + 1]):
                target, source = idx - 1, idx
            else:
                target, source = idx, idx + 1
            sections[target] = {
                "title": sections[target]["title"],
                "content": sections[target]["content"] + "\n\n" + sections[source]["content"],
            }
            del sections[source]

        sections = list(sections)
        while len(sections) > 1:
            small = [i for i, s in enumerate(sections) if words(s) < cls.MIN_SECTION_WORDS]
            if small:
                merge_into_neighbour(small[0])
            elif len(sections) > cls.MAX_TOPICS:
                merge_into_neighbour(min(range(len(sections)), key=lambda i: words(sections[i])))
            else:
                break
        return sections

    @classmethod
    def _fallback_chunking(cls, text: str, document_title: str) -> List[Dict[str, str]]:
        """Fallback chunker by logical paragraph groups if no headings found."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return [{"title": f"{document_title} - Overview", "content": text, "order_index": 0}]

        def chunk_title(index: int, chunk: List[str]) -> str:
            opening = " ".join(chunk[0].split()[:6]).rstrip(".,;:")
            return f"Part {index}: {opening}…"

        chunks: List[Dict[str, str]] = []
        curr_chunk: List[str] = []
        curr_words = 0
        chunk_idx = 1
        target_words_per_chunk = 450

        for p in paragraphs:
            word_count = len(p.split())
            curr_chunk.append(p)
            curr_words += word_count

            if curr_words >= target_words_per_chunk:
                chunks.append({
                    "title": chunk_title(chunk_idx, curr_chunk),
                    "content": "\n\n".join(curr_chunk),
                    "order_index": chunk_idx - 1
                })
                chunk_idx += 1
                curr_chunk = []
                curr_words = 0

        if curr_chunk:
            if chunks and curr_words < 100:
                # Append to last chunk if very short
                chunks[-1]["content"] += "\n\n" + "\n\n".join(curr_chunk)
            else:
                chunks.append({
                    "title": chunk_title(chunk_idx, curr_chunk) if chunk_idx > 1 else f"{document_title} - Main Topic",
                    "content": "\n\n".join(curr_chunk),
                    "order_index": chunk_idx - 1
                })

        return chunks

segmenter_service = SegmenterService()
