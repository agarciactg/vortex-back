from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai import ChatRequest, ChatResponse, HistoryOut, MessageOut
from app.services import ai_service

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with AI assistant",
    description=(
        "Send a message to the AI assistant. "
        "The assistant can manage tickets in natural language: "
        "consult, create, change status, comment and reassign. "
        "Pass `conversation_id` to continue an existing conversation."
    ),
)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        reply, conversation_id, actions = await ai_service.chat(
            db=db,
            current_user=current_user,
            message=body.message,
            conversation_id=body.conversation_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"El asistente no está disponible: {str(exc)}",
        )

    return ChatResponse(
        reply=reply,
        conversation_id=conversation_id,
        actions=actions,
    )


@router.get(
    "/history",
    response_model=HistoryOut,
    summary="Conversation history",
    description="Returns the messages of a conversation of the authenticated user.",
)
async def get_history(
    conversation_id: str = Query(..., description="ID of the conversation"),
    skip:  int = Query(default=0,  ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items, total = await ai_service.get_history(
        db=db,
        user_id=current_user.id,
        conversation_id=conversation_id,
        skip=skip,
        limit=limit,
    )

    if total == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversación no encontrada.",
        )

    return HistoryOut(
        items=[MessageOut.model_validate(m) for m in items],
        total=total,
        conversation_id=conversation_id,
    )
