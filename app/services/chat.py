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

    async def _prepare_chat_context(self, chat: Chat, user_id: uuid.UUID, content: str):
        # 3. Classify incoming query
        classification = await gemini_service.classify_query(content)
        logger.info(f"Query Classification: '{content}' -> classified as '{classification}'")

        contexts = []
        if classification == "normal chat":
            logger.info("Chit-chat detected. Bypassing RAG vector retrieval.")
        else:
            retrieval_query = content
            if classification == "follow-up question":
                prev_turns = []
                for msg in chat.messages[:-1]:
                    prev_turns.append({
                        "role": "user" if msg.role == MessageRole.user else "model",
                        "content": msg.content
                    })
                try:
                    retrieval_query = await gemini_service.reformulate_query(prev_turns, content)
                    logger.info(f"Follow-up query '{content}' reformulated to standalone query: '{retrieval_query}'")
                except Exception as e:
                    logger.error(f"Query reformulation failed: {e}")
                    retrieval_query = content
                    for msg in reversed(chat.messages[:-1]):
                        if msg.role == MessageRole.user:
                            retrieval_query = msg.content
                            break

            try:
                contexts = await rag_service.retrieve_context(user_id=user_id, query=retrieval_query)
            except Exception as e:
                logger.error(f"RAG retrieval failed, falling back to standard prompt: {e}")

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

        # Retrieve recent history and format via PromptBuilder
        messages = chat.messages
        recent_messages = messages[-CONTEXT_WINDOW_LIMIT:]

        raw_history = []
        for msg in recent_messages:
            raw_history.append({
                "role": "user" if msg.role == MessageRole.user else "model",
                "content": msg.content
            })

        formatted_history = prompt_builder.format_history_for_gemini(
            history=raw_history,
            contexts=contexts if classification != "normal chat" else None
        )

        system_prompt = prompt_builder.build_system_prompt(chat.system_prompt, history_summary)
        return formatted_history, system_prompt, contexts

    async def send_message(
        self,
        db: AsyncSession,
        chat_id: uuid.UUID,
        user_id: uuid.UUID,
        content: str
    ) -> Dict[str, Any]:
        """
        Process a new message turn (non-streaming). Saves user input, performs RAG retrieval,
        optimizes context memory, sends to Gemini, and saves the assistant response.
        """
        # 1. Fetch chat and validate ownership
        chat = await self.get_chat_detail(db, chat_id, user_id)

        # 2. Store the user's clean message (keeps DB representation pristine)
        user_message = Message(
            chat_id=chat_id,
            role=MessageRole.user,
            content=content
        )
        db.add(user_message)
        chat.message_count += 1
        
        await db.flush()

        # 3. Prepare Chat Context
        formatted_history, system_prompt, contexts = await self._prepare_chat_context(chat, user_id, content)

        # 5. Generate AI response from Gemini
        try:
            ai_response = await gemini_service.generate_response(
                history=formatted_history,
                system_prompt=system_prompt
            )
        except Exception as e:
            logger.error(f"Failed to generate LLM response: {e}")
            raise RuntimeError(f"Chat completion failed: {str(e)}")

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
            content=ai_response["content"],
            prompt_tokens=ai_response["prompt_tokens"],
            completion_tokens=ai_response["completion_tokens"],
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
        Submits user prompt, retrieves historical database contexts, triggers RAG vector search,
        builds context augmented prompts, and streams Gemini tokens back using SSE format.
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

        # 3. Prepare Chat Context
        formatted_history, system_prompt, contexts = await self._prepare_chat_context(chat, user_id, content)

        # 5. Initialize stream generation from Gemini API
        response_stream = gemini_service.generate_stream_response(
            history=formatted_history,
            system_prompt=system_prompt
        )

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
