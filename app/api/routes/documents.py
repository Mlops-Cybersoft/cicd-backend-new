import hashlib
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.access import can_manage_document, document_access_filter
from app.config import settings
from app.dependencies import CurrentUser, DatabaseDependency
from app.models import (
    AuditLog,
    Department,
    Document,
    DocumentStatus,
    DocumentVisibility,
    User,
    UserRole,
)
from app.schemas import DocumentListResponse, DocumentRead, DownloadUrlResponse
from app.services.extractor import SUPPORTED_EXTENSIONS
from app.services.ingestion import process_document
from app.services.storage import get_storage


router = APIRouter(prefix="/documents", tags=["Documents"])


def _get_accessible_document(
    database: DatabaseDependency,
    current_user: CurrentUser,
    document_id: uuid.UUID,
) -> Document:
    result = database.execute(
        select(Document)
        .options(
            joinedload(Document.department),
            joinedload(Document.owner).joinedload(User.department),
            joinedload(Document.permissions),
        )
        .where(Document.id == document_id, document_access_filter(current_user))
    )
    document = result.unique().scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài liệu.")
    return document


@router.get("", response_model=DocumentListResponse)
def list_documents(
    database: DatabaseDependency,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    status: str | None = None,
    department_id: uuid.UUID | None = None,
) -> DocumentListResponse:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    filters = [document_access_filter(current_user)]
    if search:
        filters.append(
            Document.title.ilike(f"%{search.strip()}%")
            | Document.document_number.ilike(f"%{search.strip()}%")
        )
    if status:
        filters.append(Document.status == status)
    if department_id:
        filters.append(Document.department_id == department_id)

    total = database.scalar(select(func.count(Document.id)).where(*filters)) or 0
    items = list(
        database.scalars(
            select(Document)
            .options(
                joinedload(Document.department),
                joinedload(Document.owner).joinedload(User.department),
            )
            .where(*filters)
            .order_by(Document.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return DocumentListResponse(
        items=[DocumentRead.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=DocumentRead, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    database: DatabaseDependency,
    current_user: CurrentUser,
    file: UploadFile = File(...),
    title: str = Form(...),
    document_number: str | None = Form(None),
    document_type: str = Form("other"),
    security_level: str = Form("internal"),
    visibility: str = Form(DocumentVisibility.DEPARTMENT.value),
    department_id: uuid.UUID | None = Form(None),
    issued_at: date | None = Form(None),
    received_at: date | None = Form(None),
    due_at: date | None = Form(None),
) -> Document:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Chỉ hỗ trợ PDF có text, DOCX và TXT. MVP chưa hỗ trợ OCR.",
        )

    content = await file.read()
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"Tệp vượt quá giới hạn {settings.max_upload_size_mb} MB.",
        )
    if not content:
        raise HTTPException(status_code=400, detail="Tệp tải lên rỗng.")

    target_department_id = department_id or current_user.department_id
    if not target_department_id:
        raise HTTPException(status_code=400, detail="Cần chọn phòng ban.")
    if (
        current_user.role != UserRole.ADMIN.value
        and target_department_id != current_user.department_id
    ):
        raise HTTPException(
            status_code=403, detail="Bạn chỉ có thể tải tài liệu lên phòng ban của mình."
        )
    if not database.get(Department, target_department_id):
        raise HTTPException(status_code=400, detail="Phòng ban không hợp lệ.")

    if visibility not in {item.value for item in DocumentVisibility}:
        raise HTTPException(status_code=400, detail="Phạm vi tài liệu không hợp lệ.")
    if not title.strip():
        raise HTTPException(status_code=400, detail="Tiêu đề tài liệu không được để trống.")

    document_id = uuid.uuid4()
    safe_filename = Path(file.filename or f"document{extension}").name
    s3_key = (
        f"departments/{target_department_id}/documents/{document_id}/"
        f"versions/1/{uuid.uuid4()}{extension}"
    )
    get_storage().upload_bytes(
        s3_key,
        content,
        file.content_type or "application/octet-stream",
    )

    document = Document(
        id=document_id,
        department_id=target_department_id,
        owner_id=current_user.id,
        title=title.strip(),
        document_number=document_number.strip() if document_number else None,
        document_type=document_type,
        security_level=security_level,
        visibility=visibility,
        status=DocumentStatus.UPLOADED.value,
        status_message="Tệp đã được lưu, đang chờ xử lý.",
        original_filename=safe_filename,
        content_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        checksum=hashlib.sha256(content).hexdigest(),
        s3_bucket=settings.s3_bucket,
        s3_key=s3_key,
        issued_at=issued_at,
        received_at=received_at,
        due_at=due_at,
    )
    database.add(document)
    database.add(
        AuditLog(
            user_id=current_user.id,
            action="document.upload",
            resource_type="document",
            resource_id=document.id,
            details={"filename": safe_filename, "department_id": str(target_department_id)},
        )
    )
    database.commit()

    document = database.scalar(
        select(Document)
        .options(
            joinedload(Document.department),
            joinedload(Document.owner).joinedload(User.department),
        )
        .where(Document.id == document.id)
    )
    background_tasks.add_task(process_document, document.id)
    return document


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(
    document_id: uuid.UUID,
    database: DatabaseDependency,
    current_user: CurrentUser,
) -> Document:
    return _get_accessible_document(database, current_user, document_id)


@router.get("/{document_id}/download", response_model=DownloadUrlResponse)
def download_document(
    document_id: uuid.UUID,
    database: DatabaseDependency,
    current_user: CurrentUser,
) -> DownloadUrlResponse:
    document = _get_accessible_document(database, current_user, document_id)
    database.add(
        AuditLog(
            user_id=current_user.id,
            action="document.download",
            resource_type="document",
            resource_id=document.id,
        )
    )
    database.commit()
    return DownloadUrlResponse(
        url=get_storage().create_download_url(
            document.s3_key, document.original_filename
        ),
        expires_in=settings.s3_presigned_expiry_seconds,
    )


@router.post("/{document_id}/reprocess", response_model=DocumentRead, status_code=202)
def reprocess_document(
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    database: DatabaseDependency,
    current_user: CurrentUser,
) -> Document:
    document = _get_accessible_document(database, current_user, document_id)
    if not can_manage_document(current_user, document):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xử lý lại.")
    document.status = DocumentStatus.UPLOADED.value
    document.status_message = "Đang chờ xử lý lại."
    database.commit()
    background_tasks.add_task(process_document, document.id)
    return document


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: uuid.UUID,
    database: DatabaseDependency,
    current_user: CurrentUser,
) -> None:
    document = _get_accessible_document(database, current_user, document_id)
    if not can_manage_document(current_user, document):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa tài liệu.")
    get_storage().delete(document.s3_key)
    database.delete(document)
    database.commit()
