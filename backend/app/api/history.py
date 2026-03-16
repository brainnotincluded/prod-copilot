"""Chat history API — list, search, and manage conversations."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import require_auth
from app.db.models import ChatConversation, ChatMessage, User
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# Schemas
class MessageOut(BaseModel):
    id: int
    role: str
    content: Optional[str]
    result_data: Optional[dict] = None
    created_at: str


class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    preview: Optional[str] = None  # first user message


class ConversationDetail(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    messages: list[MessageOut]


class CreateConversationRequest(BaseModel):
    title: str = Field(default="New conversation", max_length=255)


class SaveMessageRequest(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: Optional[str] = None
    result_data: Optional[dict] = None


# Endpoints

@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(
    search: Optional[str] = Query(None, description="Search in titles and messages"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """List user's conversations, newest first. Optional search."""
    stmt = (
        select(ChatConversation)
        .where(ChatConversation.user_id == user.id)
        .order_by(ChatConversation.updated_at.desc())
    )

    if search:
        search_term = f"%{search}%"
        # Search in conversation title or message content
        stmt = stmt.where(
            or_(
                ChatConversation.title.ilike(search_term),
                ChatConversation.id.in_(
                    select(ChatMessage.conversation_id)
                    .where(ChatMessage.content.ilike(search_term))
                    .distinct()
                ),
            )
        )

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    out = []
    for conv in conversations:
        # Get message count and preview
        count_result = await db.execute(
            select(func.count(ChatMessage.id)).where(ChatMessage.conversation_id == conv.id)
        )
        msg_count = count_result.scalar() or 0

        preview_result = await db.execute(
            select(ChatMessage.content)
            .where(ChatMessage.conversation_id == conv.id, ChatMessage.role == "user")
            .order_by(ChatMessage.created_at)
            .limit(1)
        )
        preview = preview_result.scalar()

        out.append(ConversationOut(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at.isoformat(),
            updated_at=conv.updated_at.isoformat(),
            message_count=msg_count,
            preview=preview[:100] if preview else None,
        ))

    return out


@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation."""
    conv = ChatConversation(user_id=user.id, title=body.title)
    db.add(conv)
    await db.flush()
    await db.commit()
    await db.refresh(conv)

    return ConversationOut(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        message_count=0,
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: int,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Get a conversation with all messages."""
    result = await db.execute(
        select(ChatConversation)
        .where(ChatConversation.id == conversation_id, ChatConversation.user_id == user.id)
        .options(selectinload(ChatConversation.messages))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at.isoformat(),
        updated_at=conv.updated_at.isoformat(),
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                result_data=m.result_data,
                created_at=m.created_at.isoformat(),
            )
            for m in conv.messages
        ],
    )


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut, status_code=201)
async def add_message(
    conversation_id: int,
    body: SaveMessageRequest,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Add a message to a conversation."""
    # Verify ownership
    result = await db.execute(
        select(ChatConversation)
        .where(ChatConversation.id == conversation_id, ChatConversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg = ChatMessage(
        conversation_id=conversation_id,
        role=body.role,
        content=body.content,
        result_data=body.result_data,
    )
    db.add(msg)

    # Auto-title from first user message
    if conv.title == "New conversation" and body.role == "user" and body.content:
        conv.title = body.content[:80]

    await db.flush()
    await db.commit()
    await db.refresh(msg)

    return MessageOut(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        result_data=msg.result_data,
        created_at=msg.created_at.isoformat(),
    )


@router.delete("/conversations/{conversation_id}", status_code=200)
async def delete_conversation(
    conversation_id: int,
    user: User = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    result = await db.execute(
        select(ChatConversation)
        .where(ChatConversation.id == conversation_id, ChatConversation.user_id == user.id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.delete(conv)
    await db.commit()
    return {"message": "Conversation deleted"}
