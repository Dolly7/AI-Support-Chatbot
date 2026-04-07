# 🤖 AI Customer Support Chatbot API

A context-aware AI chatbot API with full **conversation memory**, session management, and streaming responses. Built with **FastAPI**, **LangChain**, and **OpenAI**.

## How It Works

```
POST /api/v1/sessions/          ← create a session (get session_id)
        ↓
POST /api/v1/chat/message       ← send messages (include session_id)
        ↓
LangChain builds full history:
  [SystemMessage]               ← chatbot persona
  [HumanMessage: "Hi..."]       ← turn 1
  [AIMessage: "Hello!..."]      ← turn 1 reply
  [HumanMessage: "My order..."] ← turn 2  ← new message appended here
        ↓
OpenAI GPT generates reply aware of full conversation
        ↓
Reply saved to session history → returned to user
```

## Features

- 🧠 **Conversation memory** — full history sent to the LLM every turn
- 🏷️ **Session management** — create, list, get, delete sessions
- 🎭 **Custom personas** — override system prompt per session (billing bot, tech support bot, etc.)
- 📡 **Streaming responses** — token-by-token output for real-time UX
- ✂️ **Automatic history trimming** — prevents context window overflow
- 🗑️ **Clear history** — reset conversation without ending session
- 🧹 **Session expiry** — auto-cleanup after 24 hours (configurable)
- 🐳 **Docker-ready**

## Tech Stack

| Component       | Technology              |
|-----------------|-------------------------|
| API             | FastAPI                 |
| AI Orchestration| LangChain               |
| LLM             | OpenAI GPT-4o-mini      |
| Memory          | In-memory session store |
| Streaming       | FastAPI StreamingResponse|

> 💡 In production, replace the in-memory session store with **Redis** for persistence and multi-instance support.

## Getting Started

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up your API key
```bash
cp .env.example .env
# Edit .env — add your OPENAI_API_KEY
```

Get a key at: https://platform.openai.com/api-keys

### 3. Run the server
```bash
uvicorn app.main:app --reload
```

Visit **http://localhost:8000/docs** for the interactive Swagger UI.

### Or run with Docker
```bash
docker-compose up --build
```

## Example Usage

### Step 1 — Create a session
```bash
curl -X POST http://localhost:8000/api/v1/sessions/ \
  -H "Content-Type: application/json" \
  -d '{
    "metadata": {"user_name": "Alice", "plan": "premium"}
  }'
```
```json
{
  "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "expires_in_hrs": 24
}
```

### Step 2 — Chat (multi-turn)
```bash
# Turn 1
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "f47ac10b-...", "message": "My order hasn'\''t arrived."}'

# Turn 2 — bot remembers context from turn 1
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Content-Type: application/json" \
  -d '{"session_id": "f47ac10b-...", "message": "The order number is #12345"}'
```

### Step 3 — Streaming response
```bash
curl -X POST http://localhost:8000/api/v1/chat/message/stream \
  -H "Content-Type: application/json" \
  -d '{"session_id": "f47ac10b-...", "message": "Can you summarise my issue?"}'
```

### Custom persona (e.g. billing-only bot)
```bash
curl -X POST http://localhost:8000/api/v1/sessions/ \
  -H "Content-Type: application/json" \
  -d '{
    "system_prompt": "You are a billing specialist. Only discuss payment and subscription topics.",
    "metadata": {"department": "billing"}
  }'
```

## API Endpoints

| Method | Endpoint                            | Description                        |
|--------|-------------------------------------|------------------------------------|
| POST   | /api/v1/sessions/                   | Create a new chat session          |
| GET    | /api/v1/sessions/                   | List all active sessions           |
| GET    | /api/v1/sessions/{session_id}       | Get session metadata               |
| DELETE | /api/v1/sessions/{session_id}       | Delete a session                   |
| POST   | /api/v1/sessions/cleanup            | Remove all expired sessions        |
| POST   | /api/v1/chat/message                | Send a message (full response)     |
| POST   | /api/v1/chat/message/stream         | Send a message (streaming)         |
| GET    | /api/v1/chat/{session_id}/history   | Get conversation history           |
| DELETE | /api/v1/chat/{session_id}/history   | Clear conversation history         |

## Running Tests
```bash
pytest tests/ -v
```

## Project Structure
```
app/
├── main.py
├── core/
│   └── config.py            # Settings (env vars)
├── routers/
│   ├── chat.py              # Message, history endpoints
│   └── sessions.py          # Session CRUD
└── services/
    ├── session_store.py     # In-memory session management
    └── chatbot_service.py   # LangChain conversation logic
```
