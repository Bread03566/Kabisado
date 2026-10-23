import io
import fitz  # PyMuPDF
from docx import Document as DocxDocument
from fastapi import HTTPException, status
from typing import Tuple

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

        extracted_text_list = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text and text.strip():
                extracted_text_list.append(text.strip())

        full_text = "\n\n".join(extracted_text_list).strip()

        if not full_text or len(full_text) < 30:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Hmm, your PDF looks blank or like a scanned image! Kabi can't find any text to read. Please check that the text is selectable."
            )

        return full_text

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
