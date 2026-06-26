import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.schemas.chat import (
    ChatCreate,
    ChatRead,
    ChatDetail,
    SendMessageRequest,
    SendMessageResponse,
    ChatRename,
)
from app.services.chat import chat_service

router = APIRouter()

@router.post("/", response_model=ChatRead, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_in: ChatCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new chat thread/session.
    """
    return await chat_service.create_chat(
        db=db,
        user_id=current_user.id,
        system_prompt=chat_in.system_prompt
    )

@router.get("/", response_model=List[ChatRead])
async def list_chats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all chat sessions belonging to the authenticated user.
    """
    return await chat_service.get_user_chats(db=db, user_id=current_user.id)

@router.get("/{chat_id}", response_model=ChatDetail)
async def get_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve full historical detail of a specific chat session.
    """
    try:
        return await chat_service.get_chat_detail(
            db=db,
            chat_id=chat_id,
            user_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(
    chat_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Permanently delete a chat session and all its messages.
    """
    try:
        await chat_service.delete_chat(
            db=db,
            chat_id=chat_id,
            user_id=current_user.id
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.post("/{chat_id}/message", response_model=SendMessageResponse)
async def send_message(
    chat_id: uuid.UUID,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message within an existing chat. Triggers LLM completion and returns the response.
    """
    try:
        return await chat_service.send_message(
            db=db,
            chat_id=chat_id,
            user_id=current_user.id,
            content=request.message
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

from fastapi.responses import StreamingResponse

@router.post("/{chat_id}/stream")
async def send_message_stream(
    chat_id: uuid.UUID,
    request: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message within an existing chat and stream response tokens back in real-time
    using Server-Sent Events (SSE). Supports stop generation.
    """
    try:
        generator = chat_service.send_message_stream(
            db=db,
            chat_id=chat_id,
            user_id=current_user.id,
            content=request.message
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Critical for NGINX/reverse-proxies buffering prevention
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{chat_id}", response_model=ChatRead)
async def rename_chat(
    chat_id: uuid.UUID,
    request: ChatRename,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Rename an existing chat session title.
    """
    try:
        chat = await chat_service.rename_chat(
            db=db,
            chat_id=chat_id,
            user_id=current_user.id,
            new_title=request.title
        )
        # We commit explicitly since PATCH changes persistent relational state
        await db.commit()
        return chat
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
