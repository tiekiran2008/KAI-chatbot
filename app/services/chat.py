import uuid
import logging
import asyncio
import json
from typing import List, Dict, Any, Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.chat import Chat, Message, MessageRole
from app.services.gemini import gemini_service
from app.services.rag import rag_service
from app.services.prompt_builder import prompt_builder
from app.graph import graph as graph_module
from app.config import settings

logger = logging.getLogger(__name__)

# Max messages to keep in active context window (sliding window)
CONTEXT_WINDOW_LIMIT = 12

class ChatService:
    """
    Service for managing Chats, Messages, and RAG/LLM context state.
    """
    async def create_chat(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        system_prompt: Optional[str] = None
    ) -> Chat:
        """Create a new chat session."""
        chat = Chat(
            user_id=user_id,
            system_prompt=system_prompt,
            title="New Chat"
        )
        db.add(chat)
        await db.flush()
        return chat

    async def get_user_chats(self, db: AsyncSession, user_id: uuid.UUID) -> List[Chat]:
        """Retrieve all chats for a given user, ordered by most recent activity."""
        result = await db.execute(
            select(Chat)
            .filter(Chat.user_id == user_id)
            .order_by(Chat.updated_at.desc())
        )
        chats = list(result.scalars().all())
        
        chat_ids = [c.id for c in chats]
        last_messages = {}
        if chat_ids:
            # We fetch the latest message for each chat. We can group by chat_id and get the one with the latest created_at.
            # Using Postgres DISTINCT ON is safest and fastest.
            msg_result = await db.execute(
                select(Message)
                .filter(Message.chat_id.in_(chat_ids))
                .distinct(Message.chat_id)
                .order_by(Message.chat_id, Message.created_at.desc())
            )
            for msg in msg_result.scalars().all():
                snippet = msg.content.strip()
                last_messages[msg.chat_id] = snippet[:100] + ("..." if len(snippet) > 100 else "")

        for chat in chats:
            chat.last_message = last_messages.get(chat.id)

        return chats

    async def get_chat_detail(
        self,
        db: AsyncSession,
        chat_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> Chat:
        """Retrieve a specific chat with all its messages loaded."""
        result = await db.execute(
            select(Chat)
            .filter(Chat.id == chat_id, Chat.user_id == user_id)
        )
        chat = result.scalars().first()
        if not chat:
            raise ValueError("Chat session not found.")
        return chat

    async def delete_chat(
        self,
        db: AsyncSession,
        chat_id: uuid.UUID,
        user_id: uuid.UUID
    ) -> None:
        """Delete a chat session and all cascading messages."""
        chat = await self.get_chat_detail(db, chat_id, user_id)
        await db.delete(chat)

    async def _build_history_and_summary(self, chat: Chat):
        # 4. Compile long-term memory summary if history is large
        history_summary = None
        if len(chat.messages) > CONTEXT_WINDOW_LIMIT:
            old_messages = chat.messages[:-CONTEXT_WINDOW_LIMIT]
            old_history = []
            for msg in old_messages:
                old_history.append({
                    "role": "user" if msg.role == MessageRole.user else "model",
                    "content": msg.content
                })
            logger.info(f"Summarizing {len(old_messages)} old messages to preserve long-term context...")
            history_summary = await gemini_service.summarize_history(old_history)

        messages = chat.messages
        recent_messages = messages[-CONTEXT_WINDOW_LIMIT:]

        raw_history = []
        for msg in recent_messages:
            raw_history.append({
                "role": "user" if msg.role == MessageRole.user else "model",
                "content": msg.content
            })
            
        return raw_history, history_summary

    async def send_message(
        self,
        db: AsyncSession,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str
    ) -> Dict[str, Any]:
        """
        Process a new message turn (non-streaming). Saves user input, orchestrates via LangGraph,
        and saves the assistant response.
        """
        # 1. Fetch chat and validate ownership
        chat = await self.get_chat_detail(db, chat_id, user_id)

        # 2. Store the user's clean message
        user_message = Message(
            chat_id=chat_id,
            role=MessageRole.user,
            content=content
        )
        db.add(user_message)
        chat.message_count += 1
        await db.flush()

        # 3. Setup Graph State
        raw_history, history_summary = await self._build_history_and_summary(chat)
        
        initial_state = {
            "user_id": str(user_id),
            "user_message": content,
            "chat_id": str(chat_id),
            "history": raw_history,
            "system_prompt": chat.system_prompt,
            "history_summary": history_summary,
            "is_streaming": False
        }
        
        # 4. Invoke LangGraph with thread_id for checkpointing
        graph_config = {"configurable": {"thread_id": str(chat_id)}}
        try:
            final_state = await graph_module.graph_app.ainvoke(initial_state, config=graph_config)
        except Exception as exc:
            # Handle HITL interrupt — graph paused awaiting human approval
            exc_name = type(exc).__name__
            if "NodeInterrupt" in exc_name or "GraphInterrupt" in exc_name:
                interrupt_data = exc.args[0] if exc.args else {}
                logger.info(f"[HITL] Graph interrupted for chat {chat_id}: {interrupt_data}")
                return {
                    "hitl_pending": True,
                    "chat_id": str(chat_id),
                    "pending_action": interrupt_data.get("pending_action", ""),
                    "pending_action_type": interrupt_data.get("pending_action_type", "unknown"),
                    "message": interrupt_data.get("message", "Action requires your approval."),
                    "actions": interrupt_data.get("actions", ["approve", "edit", "reject"])
                }
            raise

        ai_response_content = final_state.get("final_response", "")
        final_tokens = final_state.get("final_tokens", {"prompt_tokens": 0, "completion_tokens": 0})
        contexts = final_state.get("contexts", [])

        citations = []
        for ctx in contexts:
            citations.append({
                "filename": ctx["metadata"].get("filename", "Unknown Document"),
                "page_numbers": ctx["metadata"].get("page_numbers", "Unknown Page"),
                "score": ctx.get("score", 0.0),
                "text": ctx.get("text", "")
            })

        # 6. Store the assistant's message response
        assistant_message = Message(
            chat_id=chat_id,
            role=MessageRole.assistant,
            content=ai_response_content,
            prompt_tokens=final_tokens["prompt_tokens"],
            completion_tokens=final_tokens["completion_tokens"],
            citations=citations if citations else None
        )
        db.add(assistant_message)
        chat.message_count += 1
        
        # 7. Auto-generate a smart title on the first message of this chat
        if chat.title in ("New Chat", None, ""):
            try:
                chat.title = await gemini_service.generate_chat_title(content)
                logger.info(f"Generated title for chat {chat_id}: '{chat.title}'")
            except Exception as title_err:
                logger.warning(f"Title generation failed, keeping default: {title_err}")

        chat.updated_at = chat.updated_at
        await db.flush()

        return {
            "chat_id": chat_id,
            "user_message": user_message,
            "assistant_message": assistant_message
        }

    async def send_message_stream(
        self,
        db: AsyncSession,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str
    ) -> AsyncGenerator[str, None]:
        """
        Submits user prompt, triggers LangGraph orchestration, and streams tokens back using SSE.
        """
        # 1. Fetch chat and validate ownership
        chat = await self.get_chat_detail(db, chat_id, user_id)

        # 2. Store user message immediately
        user_message = Message(
            chat_id=chat_id,
            role=MessageRole.user,
            content=content
        )
        db.add(user_message)
        chat.message_count += 1
        await db.commit()

        # 3. Setup Graph State
        raw_history, history_summary = await self._build_history_and_summary(chat)
        
        initial_state = {
            "user_id": str(user_id),
            "user_message": content,
            "chat_id": str(chat_id),
            "history": raw_history,
            "system_prompt": chat.system_prompt,
            "history_summary": history_summary,
            "is_streaming": True
        }

        # 4. Invoke LangGraph with thread_id for checkpointing
        graph_config = {"configurable": {"thread_id": str(chat_id)}}
        try:
            final_state = await graph_module.graph_app.ainvoke(initial_state, config=graph_config)
        except Exception as exc:
            exc_name = type(exc).__name__
            if "NodeInterrupt" in exc_name or "GraphInterrupt" in exc_name:
                interrupt_data = exc.args[0] if exc.args else {}
                logger.info(f"[HITL] Streaming graph interrupted for chat {chat_id}.")
                # Yield a structured HITL event so the frontend can render approval UI
                hitl_payload = {
                    "hitl_pending": True,
                    "chat_id": str(chat_id),
                    "pending_action": interrupt_data.get("pending_action", ""),
                    "pending_action_type": interrupt_data.get("pending_action_type", "unknown"),
                    "message": interrupt_data.get("message", "Action requires your approval."),
                    "actions": interrupt_data.get("actions", ["approve", "edit", "reject"])
                }
                yield f"data: {json.dumps(hitl_payload)}\n\n"
                return
            raise

        response_stream = final_state.get("response_stream")
        contexts = final_state.get("contexts", [])
        
        if not response_stream:
            raise RuntimeError("LangGraph execution failed to return a response_stream")

        accumulated_content = ""
        try:
            async for token in response_stream:
                accumulated_content += token
                yield f"data: {json.dumps({'token': token})}\n\n"
                
        except asyncio.CancelledError:
            logger.info(f"Streaming cancelled by user. Saving partial generation ({len(accumulated_content)} chars).")
            raise
            
        finally:
            # 6. Persist assistant response
            if accumulated_content.strip():
                citations = []
                for ctx in contexts:
                    citations.append({
                        "filename": ctx["metadata"].get("filename", "Unknown Document"),
                        "page_numbers": ctx["metadata"].get("page_numbers", "Unknown Page"),
                        "score": ctx.get("score", 0.0),
                        "text": ctx.get("text", "")
                    })

                assistant_message = Message(
                    chat_id=chat_id,
                    role=MessageRole.assistant,
                    content=accumulated_content,
                    citations=citations if citations else None
                )
                db.add(assistant_message)
                chat.message_count += 1
                
                # Auto-generate a smart title on the first message of this chat
                new_title = None
                if chat.title in ("New Chat", None, ""):
                    try:
                        new_title = await gemini_service.generate_chat_title(content)
                        chat.title = new_title
                        logger.info(f"Generated title for chat {chat_id}: '{chat.title}'")
                    except Exception as title_err:
                        logger.warning(f"Title generation failed, keeping default: {title_err}")
                
                await db.commit()
                
                # Yield final done event — include new_title so sidebar updates immediately
                final_payload = {
                    "done": True,
                    "message_id": str(assistant_message.id),
                    "content": accumulated_content,
                    "citations": citations,
                    "new_title": new_title  # None when title was already set
                }
                yield f"data: {json.dumps(final_payload)}\n\n"

    async def rename_chat(
        self,
        db: AsyncSession,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        new_title: str
    ) -> Chat:
        """Rename an existing chat session's title."""
        chat = await self.get_chat_detail(db, chat_id, user_id)
        chat.title = new_title.strip()
        await db.flush()
        return chat

# Instantiate as a singleton
chat_service = ChatService()
