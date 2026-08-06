from fastapi import APIRouter

from app.api.routes import admin_users, auth, chat, dashboard, departments, documents


api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin_users.router)
api_router.include_router(dashboard.router)
api_router.include_router(departments.router)
api_router.include_router(documents.router)
api_router.include_router(chat.router)
