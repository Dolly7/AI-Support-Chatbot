import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.session_store import SessionStore, Session
from app.core.config import settings


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── Session store unit tests ──────────────────────────────────────────────────

def test_session_store_create():
    store = SessionStore()
    session = store.create()
    assert session.session_id is not None
    assert session.system_prompt == settings.DEFAULT_SYSTEM_PROMPT
    assert session.messages == []


def test_session_store_create_custom_prompt():
    store = SessionStore()
    session = store.create(system_prompt="You are a billing expert.")
    assert session.system_prompt == "You are a billing expert."


def test_session_store_get():
    store = SessionStore()
    session = store.create(metadata={"user": "Alice"})
    retrieved = store.get(session.session_id)
    assert retrieved is not None
    assert retrieved.metadata["user"] == "Alice"


def test_session_store_get_not_found():
    store = SessionStore()
    assert store.get("nonexistent-id") is None


def test_session_store_delete():
    store = SessionStore()
    session = store.create()
    deleted = store.delete(session.session_id)
    assert deleted is True
    assert store.get(session.session_id) is None


def test_session_store_delete_not_found():
    store = SessionStore()
    assert store.delete("ghost-id") is False


def test_session_add_message():
    session = Session(session_id="test", system_prompt="Test prompt")
    session.add_message("user", "Hello")
    session.add_message("assistant", "Hi there!")
    assert len(session.messages) == 2
    assert session.messages[0]["role"] == "user"
    assert session.messages[1]["content"] == "Hi there!"


def test_session_history_trimming():
    session = Session(session_id="test", system_prompt="Test")
    # Add more messages than MAX_HISTORY_MESSAGES
    for i in range(settings.MAX_HISTORY_MESSAGES + 10):
        session.add_message("user", f"Message {i}")
    assert len(session.messages) <= settings.MAX_HISTORY_MESSAGES


def test_session_not_expired():
    session = Session(session_id="test", system_prompt="Test")
    assert session.is_expired() is False


def test_session_to_dict():
    session = Session(session_id="abc", system_prompt="Test", metadata={"x": 1})
    d = session.to_dict()
    assert d["session_id"] == "abc"
    assert d["metadata"] == {"x": 1}
    assert "created_at" in d
    assert "is_expired" in d


# ── API integration tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_session(client):
    r = await client.post("/api/v1/sessions/", json={})
    assert r.status_code == 201
    data = r.json()
    assert "session_id" in data
    assert data["expires_in_hrs"] == settings.SESSION_TTL_HOURS


@pytest.mark.asyncio
async def test_create_session_custom_prompt(client):
    r = await client.post("/api/v1/sessions/", json={
        "system_prompt": "You are a billing specialist.",
        "metadata": {"department": "billing"},
    })
    assert r.status_code == 201
    assert r.json()["metadata"]["department"] == "billing"


@pytest.mark.asyncio
async def test_get_session(client):
    create_r = await client.post("/api/v1/sessions/", json={})
    session_id = create_r.json()["session_id"]

    r = await client.get(f"/api/v1/sessions/{session_id}")
    assert r.status_code == 200
    assert r.json()["session_id"] == session_id


@pytest.mark.asyncio
async def test_get_session_not_found(client):
    r = await client.get("/api/v1/sessions/does-not-exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_session(client):
    create_r = await client.post("/api/v1/sessions/", json={})
    session_id = create_r.json()["session_id"]

    r = await client.delete(f"/api/v1/sessions/{session_id}")
    assert r.status_code == 200

    r2 = await client.get(f"/api/v1/sessions/{session_id}")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_chat_message(client):
    create_r = await client.post("/api/v1/sessions/", json={})
    session_id = create_r.json()["session_id"]

    with patch("app.routers.chat.svc") as mock_svc:
        mock_svc.chat = AsyncMock(return_value={
            "session_id":    session_id,
            "user_message":  "Hello, I need help",
            "reply":         "Hi! I'm happy to help. What do you need?",
            "message_count": 2,
            "model":         "gpt-4o-mini",
        })
        r = await client.post("/api/v1/chat/message", json={
            "session_id": session_id,
            "message":    "Hello, I need help",
        })

    assert r.status_code == 200
    data = r.json()
    assert data["reply"] == "Hi! I'm happy to help. What do you need?"
    assert data["message_count"] == 2


@pytest.mark.asyncio
async def test_chat_empty_message(client):
    create_r = await client.post("/api/v1/sessions/", json={})
    session_id = create_r.json()["session_id"]
    r = await client.post("/api/v1/chat/message", json={
        "session_id": session_id,
        "message":    "   ",
    })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_chat_invalid_session(client):
    r = await client.post("/api/v1/chat/message", json={
        "session_id": "fake-session-id",
        "message":    "Hello",
    })
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_history(client):
    create_r = await client.post("/api/v1/sessions/", json={})
    session_id = create_r.json()["session_id"]

    with patch("app.routers.chat.svc") as mock_svc:
        mock_svc.chat = AsyncMock(return_value={
            "session_id": session_id, "user_message": "Hi",
            "reply": "Hello!", "message_count": 2, "model": "gpt-4o-mini",
        })
        mock_svc.get_history.return_value = [
            {"role": "user",      "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        await client.post("/api/v1/chat/message", json={
            "session_id": session_id, "message": "Hi"
        })
        r = await client.get(f"/api/v1/chat/{session_id}/history")

    assert r.status_code == 200


@pytest.mark.asyncio
async def test_clear_history(client):
    create_r = await client.post("/api/v1/sessions/", json={})
    session_id = create_r.json()["session_id"]

    r = await client.delete(f"/api/v1/chat/{session_id}/history")
    assert r.status_code == 200
    assert "cleared" in r.json()["message"]


@pytest.mark.asyncio
async def test_list_sessions(client):
    await client.post("/api/v1/sessions/", json={})
    r = await client.get("/api/v1/sessions/")
    assert r.status_code == 200
    assert "total_active" in r.json()
    assert r.json()["total_active"] >= 1
