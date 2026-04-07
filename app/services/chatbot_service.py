from typing import AsyncIterator, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.output_parsers import StrOutputParser

from app.core.config import settings
from app.services.session_store import Session


class ChatbotService:
    """
    Context-aware chatbot with full conversation memory.

    Each session maintains its own message history, which is passed
    to the LLM on every turn so the model can reference earlier parts
    of the conversation.

    Flow per turn:
    1. Load session → get message history
    2. Append new user message to history
    3. Build prompt: [SystemMessage] + [all previous messages]
    4. Call OpenAI → get reply
    5. Append AI reply to history
    6. Return reply
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.7,          # slightly creative for natural conversation
            openai_api_key=settings.OPENAI_API_KEY,
        )

    def _build_messages(self, session: Session) -> list:
        """Convert stored message dicts to LangChain message objects."""
        lc_messages = [SystemMessage(content=session.system_prompt)]
        for msg in session.messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))
        return lc_messages

    async def chat(self, session: Session, user_message: str) -> dict:
        """
        Send a message and get a full response.
        Automatically updates session history.
        """
        # Add user message to history
        session.add_message("user", user_message)

        # Build full message history for the LLM
        messages = self._build_messages(session)

        # Call OpenAI
        response = await self.llm.ainvoke(messages)
        reply = response.content.strip()

        # Save assistant reply to history
        session.add_message("assistant", reply)

        return {
            "session_id":    session.session_id,
            "user_message":  user_message,
            "reply":         reply,
            "message_count": len(session.messages),
            "model":         settings.OPENAI_MODEL,
        }

    async def chat_stream(
        self, session: Session, user_message: str
    ) -> AsyncIterator[str]:
        """
        Streaming version: yields reply tokens as they arrive.
        Accumulates the full reply to save in session history afterward.
        """
        session.add_message("user", user_message)
        messages = self._build_messages(session)

        stream_llm = ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=0.7,
            openai_api_key=settings.OPENAI_API_KEY,
            streaming=True,
        )

        full_reply = ""
        async for chunk in stream_llm.astream(messages):
            token = chunk.content
            full_reply += token
            yield token

        # Save the complete reply to history
        session.add_message("assistant", full_reply)

    def get_history(self, session: Session) -> list[dict]:
        """Return the full conversation history for a session."""
        return session.messages

    def summarise_prompt(self, session: Session) -> str:
        """
        Generate a prompt to summarise the conversation so far.
        Useful for long conversations — the summary can replace raw history
        to keep token usage low (not called automatically — use as needed).
        """
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}" for m in session.messages
        )
        return (
            f"Summarise the following customer support conversation in 3-5 sentences:\n\n"
            f"{history_text}\n\nSummary:"
        )
