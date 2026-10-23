import re
from typing import List, Dict

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

    @classmethod
    def segment_text(cls, raw_text: str, document_title: str = "Document") -> List[Dict[str, str]]:
        """
        Segments raw document text into logical topic sections.
        Returns a list of dicts: [{"title": "...", "content": "...", "order_index": 0}]
        """
        cleaned = raw_text.strip()
        lines = cleaned.split("\n")
        
        sections: List[Dict[str, str]] = []
        current_title = "Introduction / Overview"
        current_paragraphs: List[str] = []
        order = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check if this line looks like a heading
            is_heading = False
            heading_title = stripped

            if cls.HEADING_REGEX.match(stripped):
                is_heading = True
                # Clean markdown hashes if present
                heading_title = re.sub(r"^#{1,4}\s*", "", stripped).strip()
            elif len(stripped) < 60 and stripped.isupper() and len(stripped.split()) <= 6:
                is_heading = True
                heading_title = stripped.title()

            if is_heading:
                # If we have accumulated text for previous section
                if current_paragraphs:
                    content_str = "\n\n".join(current_paragraphs).strip()
                    if len(content_str) > 60:
                        sections.append({
                            "title": current_title,
                            "content": content_str,
                            "order_index": order
                        })
                        order += 1
                        current_paragraphs = []
                current_title = heading_title
            else:
                current_paragraphs.append(stripped)

        # Append final section
        if current_paragraphs:
            content_str = "\n\n".join(current_paragraphs).strip()
            if content_str:
                sections.append({
                    "title": current_title,
                    "content": content_str,
                    "order_index": order
                })

        # Fallback if no headings matched or only 1 big section was generated
        if len(sections) <= 1:
            sections = cls._fallback_chunking(cleaned, document_title)

        return sections

    @classmethod
    def _fallback_chunking(cls, text: str, document_title: str) -> List[Dict[str, str]]:
        """Fallback chunker by logical paragraph groups if no headings found."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return [{"title": f"{document_title} - Overview", "content": text, "order_index": 0}]

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
                    "title": f"Part {chunk_idx}: Key Concepts",
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
                    "title": f"Part {chunk_idx}: Additional Concepts" if chunk_idx > 1 else f"{document_title} - Main Topic",
                    "content": "\n\n".join(curr_chunk),
                    "order_index": chunk_idx - 1
                })

        return chunks

segmenter_service = SegmenterService()
