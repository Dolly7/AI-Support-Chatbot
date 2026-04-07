from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.session_store import session_store
from app.core.config import settings

router = APIRouter()


class CreateSessionRequest(BaseModel):
    system_prompt: Optional[str] = None    # override the default persona
    metadata: Optional[dict] = None        # e.g. {"user_name": "Alice", "topic": "billing"}

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "system_prompt": None,
                    "metadata": {"user_name": "Alice", "plan": "premium"},
                },
                {
                    "system_prompt": "You are a billing specialist. Focus only on payment and subscription issues.",
                    "metadata": {"department": "billing"},
                },
            ]
        }
    }


@router.post("/", status_code=201)
async def create_session(payload: CreateSessionRequest):
    """
    Create a new chat session.

    Optionally provide:
    - **system_prompt**: Override the default chatbot persona (e.g. for a billing bot vs. tech support bot)
    - **metadata**: Arbitrary key-value pairs attached to the session (user name, plan, etc.)

    Returns a `session_id` — include this in all subsequent /chat/message requests.
    """
    session = session_store.create(
        system_prompt=payload.system_prompt,
        metadata=payload.metadata or {},
    )
    return {
        "session_id":     session.session_id,
        "created_at":     session.created_at.isoformat(),
        "expires_in_hrs": settings.SESSION_TTL_HOURS,
        "metadata":       session.metadata,
        "message":        "Session created. Use session_id in /api/v1/chat/message",
    }


@router.get("/")
async def list_sessions():
    """List all active (non-expired) sessions."""
    sessions = session_store.list_sessions()
    return {
        "total_active": len(sessions),
        "sessions":     sessions,
    }


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get metadata and stats for a specific session."""
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return session.to_dict()


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session and its entire conversation history."""
    deleted = session_store.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted", "session_id": session_id}


@router.post("/cleanup")
async def cleanup_expired():
    """Manually trigger cleanup of expired sessions."""
    count = session_store.clear_expired()
    return {"message": f"Cleaned up {count} expired sessions"}
