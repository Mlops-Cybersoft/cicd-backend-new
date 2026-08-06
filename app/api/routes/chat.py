import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.config import settings
from app.dependencies import CurrentUser, DatabaseDependency
from app.models import AuditLog, ChatMessage, ChatSession
from app.schemas import ChatRequest, ChatResponse
from app.services.rag import answer_question, build_citations, retrieve_chunks


router = APIRouter(prefix="/chat", tags=["Knowledge assistant"])


@router.post("/ask", response_model=ChatResponse)
def ask_question(
    payload: ChatRequest,
    database: DatabaseDependency,
    current_user: CurrentUser,
) -> ChatResponse:
    session: ChatSession | None = None
    if payload.session_id:
        session = database.scalar(
            select(ChatSession).where(
                ChatSession.id == payload.session_id,
                ChatSession.user_id == current_user.id,
            )
        )
        if not session:
            raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện.")
    else:
        session = ChatSession(
            user_id=current_user.id,
            title=payload.question[:80],
        )
        database.add(session)
        database.flush()

    database.add(
        ChatMessage(
            session_id=session.id,
            role="user",
            content=payload.question,
        )
    )

    rows = retrieve_chunks(
        database,
        current_user,
        payload.question,
        payload.top_k or settings.rag_top_k,
    )
    citations = build_citations(rows)
    answer = answer_question(payload.question, rows)

    database.add(
        ChatMessage(
            session_id=session.id,
            role="assistant",
            content=answer,
            citations=[citation.model_dump(mode="json") for citation in citations],
        )
    )
    database.add(
        AuditLog(
            user_id=current_user.id,
            action="knowledge.ask",
            resource_type="chat_session",
            resource_id=session.id,
            details={"citation_count": len(citations)},
        )
    )
    database.commit()
    return ChatResponse(session_id=session.id, answer=answer, citations=citations)
