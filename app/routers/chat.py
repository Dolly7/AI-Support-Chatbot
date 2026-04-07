from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from app.services.session_store import session_store
from app.services.chatbot_service import ChatbotService

router = APIRouter()
svc = ChatbotService()


class ChatRequest(BaseModel):
    session_id: str
    message: str

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "session_id": "your-session-uuid-here",
                "message": "Hi, I need help tracking my order.",
            }]
        }
    }


class ChatResponse(BaseModel):
    session_id: str
    user_message: str
    reply: str
    message_count: int
    model: str


@router.post("/message", response_model=ChatResponse)
async def send_message(payload: ChatRequest):
    """
    Send a message to the chatbot.

    The bot remembers all previous messages in the session,
    so you can ask follow-up questions naturally.

    **Example flow:**
    - User: "My order hasn't arrived."
    - Bot: "I'm sorry to hear that! Could you share your order number?"
    - User: "It's #12345"  ← bot remembers the context from previous turn
    """
    session = session_store.get(payload.session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found or expired. Please create a new session."
        )

    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        result = await svc.chat(session, payload.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

    return result


@router.post("/message/stream")
async def send_message_stream(payload: ChatRequest):
    """
    Streaming version of /message.
    Returns reply tokens as they are generated for a real-time typing effect.
    """
    session = session_store.get(payload.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    async def token_stream():
        try:
            async for token in svc.chat_stream(session, payload.message):
                yield token
        except Exception as e:
            yield f"\n[Error: {str(e)}]"

    return StreamingResponse(token_stream(), media_type="text/plain")


@router.get("/{session_id}/history")
async def get_history(session_id: str):
    """
    Retrieve the full conversation history for a session.
    Useful for displaying a chat transcript.
    """
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    return {
        "session_id":    session_id,
        "message_count": len(session.messages),
        "messages":      svc.get_history(session),
    }


@router.delete("/{session_id}/history")
async def clear_history(session_id: str):
    """Clear the conversation history for a session (keeps session alive)."""
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    session.messages = []
    return {"message": "Conversation history cleared", "session_id": session_id}
