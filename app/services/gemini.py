import os
import logging
import asyncio
from google import genai
from google.genai import types
from typing import List, Dict, Any, Optional, AsyncGenerator

from app.config import settings

logger = logging.getLogger(__name__)


class GeminiService:
    """
    Service wrapper for Google's Gemini API using the google-genai SDK.
    Uses genai.Client with client.aio for all async operations.
    """

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        # Load model name from env — falls back to gemini-2.5-flash
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        logger.info(f"Loaded Gemini Model: {self.model_name}")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
            logger.info(f"GeminiService: client initialized with model={self.model_name}")
        else:
            self.client = None
            logger.warning("GEMINI_API_KEY is not set. LLM features will fail until configured.")

    # ------------------------------------------------------------------
    # Internal helper: convert list[dict] → list[types.Content]
    # ------------------------------------------------------------------
    @staticmethod
    def _to_contents(history: List[Dict[str, str]]) -> List[types.Content]:
        """Convert role/content dicts to types.Content objects expected by the SDK."""
        contents = []
        for msg in history:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part(text=msg["content"])]
                )
            )
        return contents

    # ------------------------------------------------------------------
    # classify_query
    # ------------------------------------------------------------------
    async def classify_query(self, query: str) -> str:
        """
        Classifies the incoming user query into exactly one of three categories:
        - 'normal chat'
        - 'RAG question'
        - 'follow-up question'
        Uses Gemini with strict system instruction parameters.
        """
        if not self.client:
            return "RAG question"  # Safe default fallback

        config = types.GenerateContentConfig(
            system_instruction=(
                "You are an expert conversational router. Classify the user query into exactly one of these categories:\n"
                "- normal chat (general greetings, small talk, pleasantries, or feedback like 'hello', 'how are you', 'thank you')\n"
                "- RAG question (questions specifically asking for information, facts, summaries, or analyses that are likely located inside files or documents, such as 'what does the contract say', 'summarize my uploaded document')\n"
                "- follow-up question (continuation prompts, short directives, corrections, or follow-ups referencing prior conversation states, such as 'can you elaborate', 'explain that further', 'why?', 'tell me more')\n\n"
                "Your response must consist of exactly the category name, all lowercase. Do not generate anything else. No preamble, no punctuation, no markdown."
            ),
            max_output_tokens=10,
            temperature=0.0,
        )

        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=[query],
                    config=config,
                ),
                timeout=5.0,
            )
            result = response.text.strip().lower()
            if "normal chat" in result:
                return "normal chat"
            elif "follow-up question" in result:
                return "follow-up question"
            else:
                return "RAG question"
        except Exception as e:
            logger.warning(f"Query classification failed, defaulting to RAG: {e}")
            return "RAG question"

    # ------------------------------------------------------------------
    # generate_response  (non-streaming)
    # ------------------------------------------------------------------
    async def generate_response(
        self,
        history: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_output_tokens: Optional[int] = 2048,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """
        Generate asynchronous response from Gemini with multi-turn history.
        Returns dict with keys: content, prompt_tokens, completion_tokens.
        """
        if not self.client:
            raise ValueError("Gemini API key is not configured. Please set GEMINI_API_KEY.")

        if not history:
            raise ValueError("History cannot be empty.")

        contents = self._to_contents(history)

        config = types.GenerateContentConfig(
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            system_instruction=system_prompt if system_prompt else None,
        )

        retries = 0
        backoff = 1.0
        max_retries = 3

        while retries < max_retries:
            try:
                response = await asyncio.wait_for(
                    self.client.aio.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                        config=config,
                    ),
                    timeout=30.0,
                )

                # Token counts
                prompt_tokens = len(str(contents).split())
                completion_tokens = len(response.text.split()) if response.text else 0

                try:
                    if hasattr(response, "usage_metadata") and response.usage_metadata:
                        prompt_tokens = response.usage_metadata.prompt_token_count or prompt_tokens
                        completion_tokens = response.usage_metadata.candidates_token_count or completion_tokens
                except Exception:
                    pass

                return {
                    "content": response.text,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }

            except Exception as e:
                retries += 1
                if retries >= max_retries:
                    logger.error(f"Failed to communicate with Gemini API after {max_retries} attempts: {e}")
                    raise RuntimeError(f"AI orchestration failure (max retries reached): {str(e)}")

                logger.warning(
                    f"Gemini API connection error on attempt {retries}/{max_retries}. "
                    f"Retrying in {backoff} seconds... Error details: {str(e)}"
                )
                await asyncio.sleep(backoff)
                backoff *= 2.0

    # ------------------------------------------------------------------
    # generate_stream_response  (SSE streaming)
    # ------------------------------------------------------------------
    async def generate_stream_response(
        self,
        history: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        max_output_tokens: Optional[int] = 2048,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Generates asynchronous token-by-token stream from Gemini API.
        Yields text tokens as they become available.
        """
        if not self.client:
            raise ValueError("Gemini API key is not configured. Please set GEMINI_API_KEY.")

        if not history:
            raise ValueError("History cannot be empty.")

        contents = self._to_contents(history)

        config = types.GenerateContentConfig(
            max_output_tokens=max_output_tokens,
            temperature=temperature,
            system_instruction=system_prompt if system_prompt else None,
        )

        retries = 0
        backoff = 1.0
        max_retries = 3

        # generate_content_stream() returns a coroutine in this version of google-genai —
        # it must be awaited to obtain the async iterator, then iterated with async for.
        # Retry the whole stream on transient errors (e.g. network blips).
        while retries < max_retries:
            try:
                response_stream = await self.client.aio.models.generate_content_stream(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
                async for chunk in response_stream:
                    if chunk.text:
                        yield chunk.text
                return  # Stream completed successfully — exit retry loop
            except Exception as e:
                retries += 1
                if retries >= max_retries:
                    logger.error(f"Failed to stream from Gemini after {max_retries} attempts: {e}")
                    raise RuntimeError(f"AI streaming orchestration failed (max retries reached): {str(e)}")

                logger.warning(
                    f"Gemini streaming error on attempt {retries}/{max_retries}. "
                    f"Retrying in {backoff} seconds... Error details: {str(e)}"
                )
                await asyncio.sleep(backoff)
                backoff *= 2.0

    # ------------------------------------------------------------------
    # reformulate_query
    # ------------------------------------------------------------------
    async def reformulate_query(self, history: List[Dict[str, str]], current_query: str) -> str:
        """
        Given the conversation history and a follow-up query, uses Gemini to reformulate
        it into a standalone, search-optimized query containing all relevant context.
        """
        if not self.client or not history:
            return current_query

        formatted_turns = []
        for msg in history:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            formatted_turns.append(f"{role_label}: {msg['content']}")

        history_text = "\n".join(formatted_turns)

        prompt = (
            "You are an expert search query reformulator with deep context understanding.\n"
            "Analyze the conversation history and the latest follow-up query from the User.\n"
            "Your task is to rewrite the follow-up query into a single, standalone search query that contains all necessary context "
            "(such as subject nouns, filenames, agreements, preferences, and topic details) from the prior history.\n\n"
            "Strict Guidelines:\n"
            "1. Do NOT answer the query. Just output the reformulated search query.\n"
            "2. If the query is already standalone or doesn't need context from history, output it exactly as-is.\n"
            "3. Make the query highly search-optimized (clear nouns instead of pronouns like 'it', 'they', 'that').\n"
            "4. Do not include any explanations, greetings, or preamble. Return ONLY the final reformulated query.\n\n"
            f"=== CONVERSATION HISTORY ===\n{history_text}\n\n"
            f"=== FOLLOW-UP QUERY ===\n{current_query}\n\n"
            "Standalone Query:"
        )

        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=[prompt],
                ),
                timeout=5.0,
            )
            reformulated = response.text.strip()
            if reformulated.startswith('"') and reformulated.endswith('"'):
                reformulated = reformulated[1:-1]
            return reformulated if reformulated else current_query
        except Exception as e:
            logger.warning(f"Query reformulation failed, falling back to original query: {e}")
            return current_query

    # ------------------------------------------------------------------
    # summarize_history
    # ------------------------------------------------------------------
    async def summarize_history(self, history_turns: List[Dict[str, str]]) -> str:
        """
        Generates a structured, high-context Conversational Memory Card of historical turns.
        """
        if not self.client or not history_turns:
            return ""

        formatted_turns = []
        for msg in history_turns:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            formatted_turns.append(f"{role_label}: {msg['content']}")

        history_text = "\n".join(formatted_turns)

        prompt = (
            "You are an elite conversational memory compiler.\n"
            "Compile the following chat history into a highly dense, structured 'Conversational Memory Card'. "
            "Focus on preserving key user preferences, files discussed, active tasks, agreed decisions, names, and explicit constraints.\n\n"
            f"=== CHAT HISTORY ===\n{history_text}\n\n"
            "Response must be formatted exactly as follows. Use short, high-density phrases:\n"
            "Memory Card:\n"
            "- Topic/Goal: [Core conversational focus]\n"
            "- User Preferences: [Explicit interests, preferred tone, constraints, etc.]\n"
            "- Key Files/Entities: [Any filenames, documents, names or codes mentioned]\n"
            "- Major Decisions/Agreements: [Key conclusions or consensus reached]"
        )

        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=[prompt],
                ),
                timeout=10.0,
            )
            return response.text.strip()
        except Exception as e:
            logger.warning(f"History summarization failed: {e}")
            return ""

    # ------------------------------------------------------------------
    # generate_chat_title
    # ------------------------------------------------------------------
    async def generate_chat_title(self, first_message: str) -> str:
        """
        Generates a concise, meaningful chat title (4–7 words, max 60 chars)
        from the user's first message. Uses a strict prompt to avoid markdown,
        punctuation, or filler phrases. Falls back to local truncation on failure.
        """
        import re

        def _local_fallback(text: str) -> str:
            """Strip markdown/punctuation and truncate cleanly to ~50 chars."""
            # Remove markdown bold/italic/code markers
            text = re.sub(r'[*_`#>\[\]()]+', '', text)
            # Remove URLs
            text = re.sub(r'https?://\S+', '', text)
            # Collapse whitespace
            text = ' '.join(text.split())
            # Capitalize first letter
            text = text.strip().capitalize()
            if len(text) > 50:
                # Truncate at last word boundary before 50 chars
                text = text[:50].rsplit(' ', 1)[0].rstrip('.,;:!?') + '…'
            return text or "New Chat"

        if not self.client:
            return _local_fallback(first_message)

        config = types.GenerateContentConfig(
            system_instruction=(
                "You are a chat title generator. Your job is to create a short, clear, meaningful title "
                "for a conversation based on the user's first message.\n\n"
                "Rules:\n"
                "1. Output ONLY the title — no quotes, no punctuation at the end, no markdown, no explanations.\n"
                "2. Use 3 to 7 words maximum.\n"
                "3. The title must be in Title Case (capitalize main words).\n"
                "4. Remove filler words like 'please', 'can you', 'I want to', 'help me'.\n"
                "5. Focus on the core topic or action.\n"
                "6. Maximum 60 characters.\n"
                "7. Never start with 'How to' unless it is the core concept.\n\n"
                "Examples:\n"
                "User: 'What is ATM?' → Title: What Is ATM\n"
                "User: 'Explain machine learning in simple terms' → Title: Machine Learning Explained\n"
                "User: 'How to build a chatbot using FastAPI?' → Title: Build Chatbot with FastAPI\n"
                "User: 'What is quantum computing and how does it work?' → Title: Quantum Computing Overview\n"
                "User: 'Tell me about the history of Python programming language' → Title: History of Python Language\n"
            ),
            max_output_tokens=20,
            temperature=0.2,
        )

        try:
            response = await asyncio.wait_for(
                self.client.aio.models.generate_content(
                    model=self.model_name,
                    contents=[first_message],
                    config=config,
                ),
                timeout=5.0,
            )
            raw = response.text.strip() if response.text else ""
            # Strip any accidental quotes or trailing punctuation
            raw = re.sub(r'^["\']+|["\']+$', '', raw).strip().rstrip('.,;:!?')
            # Enforce 60 char hard cap
            if len(raw) > 60:
                raw = raw[:60].rsplit(' ', 1)[0].rstrip('.,;:!?') + '…'
            return raw if raw else _local_fallback(first_message)
        except Exception as e:
            logger.warning(f"Chat title generation failed, using local fallback: {e}")
            return _local_fallback(first_message)


# Instantiate as a singleton
gemini_service = GeminiService()
