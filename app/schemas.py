import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class DepartmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    color: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: str
    department: DepartmentRead | None = None


class AdminUserRead(UserPublic):
    is_active: bool
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserRead]
    total: int
    page: int
    page_size: int


class AdminUserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "manager", "employee"] = "employee"
    department_id: uuid.UUID | None = None


class AdminUserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    role: Literal["admin", "manager", "employee"] | None = None
    department_id: uuid.UUID | None = None
    is_active: bool | None = None


class AdminPasswordReset(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    document_number: str | None
    document_type: str
    security_level: str
    visibility: str
    status: str
    status_message: str | None
    original_filename: str
    content_type: str
    file_size: int
    version: int
    issued_at: date | None
    received_at: date | None
    due_at: date | None
    page_count: int | None
    chunk_count: int
    created_at: datetime
    updated_at: datetime
    department: DepartmentRead
    owner: UserPublic


class DocumentListResponse(BaseModel):
    items: list[DocumentRead]
    total: int
    page: int
    page_size: int


class DownloadUrlResponse(BaseModel):
    url: str
    expires_in: int


class DashboardDepartmentStat(BaseModel):
    department_id: uuid.UUID
    code: str
    name: str
    color: str
    document_count: int
    ready_count: int


class DashboardSummary(BaseModel):
    total_documents: int
    ready_documents: int
    processing_documents: int
    total_chunks: int
    department_stats: list[DashboardDepartmentStat]
    recent_documents: list[DocumentRead]


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    session_id: uuid.UUID | None = None
    top_k: int | None = Field(default=None, ge=1, le=15)


class Citation(BaseModel):
    document_id: uuid.UUID
    title: str
    document_number: str | None
    page_number: int | None
    chunk_index: int
    excerpt: str
    distance: float


class ChatResponse(BaseModel):
    session_id: uuid.UUID
    answer: str
    citations: list[Citation]


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
