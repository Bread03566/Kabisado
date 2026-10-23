import io
import re
from collections import Counter
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from fastapi import HTTPException, status
from typing import List

PAGE_NUMBER_PATTERN = re.compile(r"^(?:page\s*)?\d{1,4}(?:\s*(?:of|/)\s*\d{1,4})?$", re.IGNORECASE)

class ParserService:
    @staticmethod
    def parse_pdf(file_bytes: bytes, filename: str = "document.pdf") -> str:
        """Extract text from PDF using PyMuPDF."""
        try:
            doc = fitz.open(stream=file_bytes, filetype="pdf")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Couldn't open your PDF, friend! It may be corrupted or password-protected: {str(e)}"
            )

        pages = [doc[page_num].get_text("text") for page_num in range(len(doc))]
        full_text = ParserService.clean_pdf_pages(pages)

        if not full_text or len(full_text) < 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hmm, your PDF looks blank or like a scanned image! Kabi can't find any text to read. Please check that the text is selectable."
            )

        return full_text

    @staticmethod
    def clean_pdf_pages(pages: List[str]) -> str:
        """
        Joins PDF pages into study text, dropping page furniture: headers and footers
        repeated on most pages (course codes, handout names, copyright lines) and page
        numbers. Also repairs U+FFFD glyphs that PyMuPDF emits for unmapped characters,
        which are usually apostrophes inside words and bullets elsewhere.
        """
        page_lines = [[line.strip() for line in page.splitlines()] for page in pages]
        repeated = set()
        if len(pages) >= 3:
            counts = Counter(line for lines in page_lines for line in set(lines) if line)
            threshold = max(2, len(pages) // 2)
            repeated = {line for line, n in counts.items() if n >= threshold and len(line) <= 80}

        cleaned_pages = []
        for lines in page_lines:
            kept = []
            for line in lines:
                if line in repeated or PAGE_NUMBER_PATTERN.match(line):
                    continue
                line = re.sub(r"(?<=\w)�(?=\w)", "'", line).replace("�", "•")
                if line == "•":
                    continue
                kept.append(line)
            page_text = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
            if page_text:
                cleaned_pages.append(page_text)
        return "\n\n".join(cleaned_pages).strip()

    @staticmethod
    def parse_docx(file_bytes: bytes, filename: str = "document.docx") -> str:
        """Extract text from Word document (.docx) using python-docx."""
        try:
            stream = io.BytesIO(file_bytes)
            doc = DocxDocument(stream)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Couldn't read the Word DOCX file: {str(e)}"
            )

        text_parts = []
        for p in doc.paragraphs:
            text = p.text.strip()
            if text:
                text_parts.append(text)

        # Also extract table text
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    text_parts.append(row_text)

        full_text = "\n\n".join(text_parts).strip()

        if not full_text or len(full_text) < 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No text could be extracted from your DOCX file! Maybe it's all screenshots, or empty?"
            )

        return full_text

    @staticmethod
    def parse_plain_text(text: str) -> str:
        """Clean and validate pasted plain text."""
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if len(cleaned) < 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="That's way too short, friend! Paste at least a few sentences so we have something to study."
            )
        return cleaned

parser_service = ParserService()
