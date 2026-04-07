import uuid
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field

from app.core.config import settings


@dataclass
class Session:
    session_id: str
    system_prompt: str
    messages: list = field(default_factory=list)   # list of {"role": ..., "content": ...}
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)   # e.g. user_name, topic, etc.

    def is_expired(self) -> bool:
        ttl = timedelta(hours=settings.SESSION_TTL_HOURS)
        return datetime.utcnow() - self.updated_at > ttl

    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self.updated_at = datetime.utcnow()
        # Trim history to avoid exceeding context window
        if len(self.messages) > settings.MAX_HISTORY_MESSAGES:
            # Always keep the first message (often introductory context)
            self.messages = self.messages[:1] + self.messages[-(settings.MAX_HISTORY_MESSAGES - 1):]

    def to_dict(self) -> dict:
        return {
            "session_id":    self.session_id,
            "message_count": len(self.messages),
            "created_at":    self.created_at.isoformat(),
            "updated_at":    self.updated_at.isoformat(),
            "metadata":      self.metadata,
            "is_expired":    self.is_expired(),
        }


class SessionStore:
    """
    In-memory session store.
    In production, replace with Redis for persistence and horizontal scaling.
    """

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def create(
        self,
        system_prompt: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> Session:
        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            system_prompt=system_prompt or settings.DEFAULT_SYSTEM_PROMPT,
            metadata=metadata or {},
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[Session]:
        session = self._sessions.get(session_id)
        if session and session.is_expired():
            del self._sessions[session_id]
            return None
        return session

    def delete(self, session_id: str) -> bool:
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def list_sessions(self) -> list[dict]:
        active = []
        expired_ids = []
        for sid, session in self._sessions.items():
            if session.is_expired():
                expired_ids.append(sid)
            else:
                active.append(session.to_dict())
        for sid in expired_ids:
            del self._sessions[sid]
        return active

    def clear_expired(self) -> int:
        expired = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)


# Global singleton
session_store = SessionStore()
