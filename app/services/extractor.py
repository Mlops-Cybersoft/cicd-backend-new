from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


@dataclass(slots=True)
class ExtractedPage:
    text: str
    page_number: int | None


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def extract_text(data: bytes, filename: str) -> list[ExtractedPage]:
    extension = Path(filename).suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Định dạng chưa được hỗ trợ. Chỉ chấp nhận PDF, DOCX và TXT.")

    if extension == ".pdf":
        reader = PdfReader(BytesIO(data))
        return [
            ExtractedPage(text=(page.extract_text() or "").strip(), page_number=index)
            for index, page in enumerate(reader.pages, start=1)
        ]

    if extension == ".docx":
        document = DocxDocument(BytesIO(data))
        text = "\n".join(
            paragraph.text.strip()
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        )
        return [ExtractedPage(text=text, page_number=None)]

    text = data.decode("utf-8-sig", errors="replace").strip()
    return [ExtractedPage(text=text, page_number=None)]
