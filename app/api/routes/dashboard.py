from fastapi import APIRouter
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.access import document_access_filter
from app.dependencies import CurrentUser, DatabaseDependency
from app.models import Department, Document, DocumentChunk, DocumentStatus, User
from app.schemas import (
    DashboardDepartmentStat,
    DashboardSummary,
    DocumentRead,
)


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    database: DatabaseDependency,
    current_user: CurrentUser,
) -> DashboardSummary:
    access_filter = document_access_filter(current_user)
    total_documents = database.scalar(
        select(func.count(Document.id)).where(access_filter)
    ) or 0
    ready_documents = database.scalar(
        select(func.count(Document.id)).where(
            access_filter, Document.status == DocumentStatus.READY.value
        )
    ) or 0
    processing_documents = database.scalar(
        select(func.count(Document.id)).where(
            access_filter,
            Document.status.in_(
                [DocumentStatus.UPLOADED.value, DocumentStatus.PROCESSING.value]
            ),
        )
    ) or 0
    total_chunks = database.scalar(
        select(func.count(DocumentChunk.id))
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(access_filter)
    ) or 0

    department_rows = database.execute(
        select(
            Department.id,
            Department.code,
            Department.name,
            Department.color,
            func.count(Document.id),
            func.count(Document.id).filter(Document.status == DocumentStatus.READY.value),
        )
        .join(Document, Document.department_id == Department.id)
        .where(access_filter)
        .group_by(Department.id)
        .order_by(Department.name)
    ).all()

    recent_documents = list(
        database.scalars(
            select(Document)
            .options(
                joinedload(Document.department),
                joinedload(Document.owner).joinedload(User.department),
            )
            .where(access_filter)
            .order_by(Document.created_at.desc())
            .limit(5)
        ).all()
    )

    return DashboardSummary(
        total_documents=total_documents,
        ready_documents=ready_documents,
        processing_documents=processing_documents,
        total_chunks=total_chunks,
        department_stats=[
            DashboardDepartmentStat(
                department_id=row[0],
                code=row[1],
                name=row[2],
                color=row[3],
                document_count=row[4],
                ready_count=row[5],
            )
            for row in department_rows
        ],
        recent_documents=[
            DocumentRead.model_validate(document) for document in recent_documents
        ],
    )
