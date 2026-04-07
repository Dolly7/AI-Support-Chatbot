from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.routers import chat, sessions
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="AI Customer Support Chatbot API",
    description="""
    A context-aware AI customer support chatbot with conversation memory.
    Maintains full chat history per session, supports custom system prompts,
    and provides streaming responses. Built with LangChain and OpenAI.
    """,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,     prefix="/api/v1/chat",     tags=["Chat"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])


@app.get("/", tags=["Health"])
async def root():
    return {"message": "AI Customer Support Chatbot API", "docs": "/docs"}


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "healthy"}
