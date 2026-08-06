import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select, text
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import User, UserRole
from app.security import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_prefix}/auth/login")
DatabaseDependency = Annotated[Session, Depends(get_db)]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    database: DatabaseDependency,
) -> User:
    subject = decode_access_token(token)
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn.",
        )

    try:
        user_id = uuid.UUID(subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ.",
        ) from exc

    user = database.scalar(
        select(User).options(joinedload(User.department)).where(User.id == user_id)
    )
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại hoặc đã bị vô hiệu hóa.",
        )

    database.execute(
        text("SELECT set_config('app.current_user_id', :value, true)"),
        {"value": str(user.id)},
    )
    database.execute(
        text("SELECT set_config('app.current_department_id', :value, true)"),
        {"value": str(user.department_id or "")},
    )
    database.execute(
        text("SELECT set_config('app.current_user_role', :value, true)"),
        {"value": user.role},
    )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(current_user: CurrentUser) -> User:
    if current_user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Bạn không có quyền quản trị.")
    return current_user


AdminUser = Annotated[User, Depends(require_admin)]
