from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.schemas import HealthResponse
from app.seed import seed_database


@asynccontextmanager
async def lifespan(_: FastAPI):
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=connection)

    if settings.seed_demo_data:
        with SessionLocal() as database:
            seed_database(database)
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "API quản lý công văn và hỏi đáp trên kho tài liệu có phân quyền phòng ban."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
def health() -> HealthResponse:
    return HealthResponse(status="healthy", service=settings.app_name, version="0.1.0")
