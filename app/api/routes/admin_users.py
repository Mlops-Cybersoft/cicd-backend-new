import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.dependencies import AdminUser, DatabaseDependency
from app.models import AuditLog, Department, User, UserRole
from app.schemas import (
    AdminPasswordReset,
    AdminUserCreate,
    AdminUserListResponse,
    AdminUserRead,
    AdminUserUpdate,
)
from app.security import hash_password


router = APIRouter(prefix="/admin/users", tags=["Admin - Users"])


def _get_user_or_404(database: DatabaseDependency, user_id: uuid.UUID) -> User:
    user = database.scalar(
        select(User)
        .options(joinedload(User.department))
        .where(User.id == user_id)
    )
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
    return user


def _resolve_department(
    database: DatabaseDependency,
    role: str,
    department_id: uuid.UUID | None,
) -> Department | None:
    if role == UserRole.ADMIN.value:
        return None
    if department_id is None:
        raise HTTPException(
            status_code=422,
            detail="Tài khoản quản lý hoặc nhân viên phải thuộc một phòng ban.",
        )
    department = database.get(Department, department_id)
    if not department:
        raise HTTPException(status_code=422, detail="Phòng ban không tồn tại.")
    return department


def _commit_or_email_conflict(database: DatabaseDependency) -> None:
    try:
        database.commit()
    except IntegrityError as exc:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email này đã được sử dụng.",
        ) from exc


@router.get("", response_model=AdminUserListResponse)
def list_users(
    database: DatabaseDependency,
    _: AdminUser,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    role: str | None = None,
    department_id: uuid.UUID | None = None,
    is_active: bool | None = None,
) -> AdminUserListResponse:
    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    filters = []

    if search and search.strip():
        term = f"%{search.strip()}%"
        filters.append(or_(User.full_name.ilike(term), User.email.ilike(term)))
    if role:
        if role not in {item.value for item in UserRole}:
            raise HTTPException(status_code=422, detail="Vai trò không hợp lệ.")
        filters.append(User.role == role)
    if department_id:
        filters.append(User.department_id == department_id)
    if is_active is not None:
        filters.append(User.is_active == is_active)

    total = database.scalar(select(func.count(User.id)).where(*filters)) or 0
    users = list(
        database.scalars(
            select(User)
            .options(joinedload(User.department))
            .where(*filters)
            .order_by(User.created_at.desc(), User.full_name.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return AdminUserListResponse(
        items=[AdminUserRead.model_validate(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=AdminUserRead, status_code=201)
def create_user(
    payload: AdminUserCreate,
    database: DatabaseDependency,
    admin: AdminUser,
) -> User:
    email = payload.email.lower()
    if database.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email này đã được sử dụng.")

    department = _resolve_department(database, payload.role, payload.department_id)
    user = User(
        id=uuid.uuid4(),
        email=email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=payload.role,
        department_id=department.id if department else None,
        is_active=True,
    )
    database.add(user)
    database.add(
        AuditLog(
            user_id=admin.id,
            action="user.create",
            resource_type="user",
            resource_id=user.id,
            details={
                "email": user.email,
                "role": user.role,
                "department_id": str(user.department_id) if user.department_id else None,
            },
        )
    )
    _commit_or_email_conflict(database)
    return _get_user_or_404(database, user.id)


@router.patch("/{user_id}", response_model=AdminUserRead)
def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    database: DatabaseDependency,
    admin: AdminUser,
) -> User:
    user = _get_user_or_404(database, user_id)
    before = {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "department_id": str(user.department_id) if user.department_id else None,
        "is_active": user.is_active,
    }

    if user.id == admin.id:
        if payload.is_active is False:
            raise HTTPException(
                status_code=422, detail="Bạn không thể tự khóa tài khoản của mình."
            )
        if payload.role and payload.role != UserRole.ADMIN.value:
            raise HTTPException(
                status_code=422, detail="Bạn không thể tự gỡ quyền admin của mình."
            )

    next_role = payload.role or user.role
    if "department_id" in payload.model_fields_set:
        next_department_id = payload.department_id
    else:
        next_department_id = user.department_id
    department = _resolve_department(database, next_role, next_department_id)

    if payload.email is not None:
        normalized_email = payload.email.lower()
        existing_id = database.scalar(
            select(User.id).where(
                User.email == normalized_email,
                User.id != user.id,
            )
        )
        if existing_id:
            raise HTTPException(status_code=409, detail="Email này đã được sử dụng.")
        user.email = normalized_email
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.role is not None:
        user.role = payload.role
    user.department_id = department.id if department else None
    if payload.is_active is not None:
        user.is_active = payload.is_active

    after = {
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "department_id": str(user.department_id) if user.department_id else None,
        "is_active": user.is_active,
    }
    database.add(
        AuditLog(
            user_id=admin.id,
            action="user.update",
            resource_type="user",
            resource_id=user.id,
            details={"before": before, "after": after},
        )
    )
    _commit_or_email_conflict(database)
    return _get_user_or_404(database, user.id)


@router.post("/{user_id}/reset-password", status_code=204)
def reset_password(
    user_id: uuid.UUID,
    payload: AdminPasswordReset,
    database: DatabaseDependency,
    admin: AdminUser,
) -> None:
    user = _get_user_or_404(database, user_id)
    user.hashed_password = hash_password(payload.new_password)
    database.add(
        AuditLog(
            user_id=admin.id,
            action="user.password_reset",
            resource_type="user",
            resource_id=user.id,
            details={"email": user.email},
        )
    )
    database.commit()
