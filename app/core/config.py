from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Customer Support Chatbot"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Session / memory settings
    MAX_HISTORY_MESSAGES: int = 20    # keep last N messages in memory
    SESSION_TTL_HOURS: int = 24       # sessions expire after 24 hours

    # Chatbot persona
    DEFAULT_SYSTEM_PROMPT: str = """You are a friendly and professional customer support agent.
Your job is to help users with their questions clearly and concisely.
Always be polite, empathetic, and solution-focused.
If you don't know the answer to something, say so honestly and offer to escalate.
Keep responses concise — aim for 2-4 sentences unless the user asks for more detail."""

    class Config:
        env_file = ".env"


settings = Settings()
