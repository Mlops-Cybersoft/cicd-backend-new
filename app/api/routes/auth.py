from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.dependencies import CurrentUser, DatabaseDependency
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserPublic
from app.security import create_access_token, verify_password


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, database: DatabaseDependency) -> TokenResponse:
    user = database.scalar(
        select(User)
        .options(joinedload(User.department))
        .where(User.email == payload.email.lower())
    )
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không chính xác.",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Tài khoản đã bị vô hiệu hóa.")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        user=UserPublic.model_validate(user),
    )


@router.get("/me", response_model=UserPublic)
def me(current_user: CurrentUser) -> User:
    return current_user
