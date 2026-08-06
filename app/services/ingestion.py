import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import delete, select

from app.config import settings
from app.database import SessionLocal
from app.models import Document, DocumentChunk, DocumentStatus
from app.services.embeddings import get_embeddings, validate_vector
from app.services.extractor import extract_text
from app.services.storage import get_storage


def process_document(document_id: uuid.UUID) -> None:
    database = SessionLocal()
    try:
        document = database.scalar(select(Document).where(Document.id == document_id))
        if not document:
            return

        document.status = DocumentStatus.PROCESSING.value
        document.status_message = "Đang trích xuất và lập chỉ mục nội dung."
        database.commit()

        data = get_storage().download_bytes(document.s3_key)
        pages = extract_text(data, document.original_filename)
        pages_with_text = [page for page in pages if page.text.strip()]

        if not pages_with_text:
            document.status = DocumentStatus.NO_TEXT.value
            document.status_message = (
                "Không trích xuất được text. MVP hiện chưa hỗ trợ tài liệu scan/OCR."
            )
            document.page_count = len(pages)
            database.commit()
            return

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        chunk_payloads: list[tuple[str, int | None, int]] = []
        chunk_index = 0
        for page in pages_with_text:
            for chunk_text in splitter.split_text(page.text):
                if chunk_text.strip():
                    chunk_payloads.append(
                        (chunk_text.strip(), page.page_number, chunk_index)
                    )
                    chunk_index += 1

        embeddings = get_embeddings().embed_documents(
            [payload[0] for payload in chunk_payloads]
        )
        database.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )

        for (content, page_number, index), embedding in zip(
            chunk_payloads, embeddings, strict=True
        ):
            database.add(
                DocumentChunk(
                    document_id=document.id,
                    department_id=document.department_id,
                    chunk_index=index,
                    page_number=page_number,
                    content=content,
                    token_count=max(1, len(content) // 4),
                    embedding=validate_vector(embedding),
                    attributes={"source": document.original_filename},
                )
            )

        document.page_count = len(pages)
        document.chunk_count = len(chunk_payloads)
        document.status = DocumentStatus.READY.value
        document.status_message = "Tài liệu đã sẵn sàng để hỏi đáp."
        database.commit()
    except Exception as exc:
        database.rollback()
        document = database.scalar(select(Document).where(Document.id == document_id))
        if document:
            document.status = DocumentStatus.FAILED.value
            document.status_message = str(exc)[:1000]
            database.commit()
    finally:
        database.close()
