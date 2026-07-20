from pathlib import Path
from typing import Optional
from pydantic import Field, PostgresDsn, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    # Core Application Settings
    APP_NAME: str = "Production-Grade AI Chatbot Backend"
    APP_ENV: str = "development"
    API_V1_STR: str = "/api/v1"

    # Database Configuration (PostgreSQL)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = Field(..., description="PostgreSQL password")
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ai_chatbot"
    
    DATABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info: ValidationInfo) -> str:
        if isinstance(v, str) and v:
            return v
        
        # Build asyncpg connection string automatically
        user = info.data.get("POSTGRES_USER")
        password = info.data.get("POSTGRES_PASSWORD")
        server = info.data.get("POSTGRES_SERVER")
        port = info.data.get("POSTGRES_PORT")
        db = info.data.get("POSTGRES_DB")
        
        return f"postgresql+asyncpg://{user}:{password}@{server}:{port}/{db}"

    # Vector Database Configuration (ChromaDB)
    CHROMADB_HOST: str = "localhost"
    CHROMADB_PORT: int = 8000
    CHROMADB_PERSIST_DIRECTORY: str = "./chroma_db"

    # LLM Configuration (Gemini API)
    GEMINI_API_KEY: str = Field(..., description="Gemini API Key")

    # Security
    SECRET_KEY: str = Field(..., description="Must be securely configured")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # 1 week
    
    # Supabase Auth Configuration
    SUPABASE_JWT_SECRET: Optional[str] = None

    @field_validator("SUPABASE_JWT_SECRET", mode="after")
    @classmethod
    def enforce_production_secrets(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        # Enforce secure secrets only if environment is production
        if info.data.get("APP_ENV") == "production" and not v:
            raise ValueError(f"Missing value for {info.field_name}. Must be securely configured in production.")
        return v
        
    # LangSmith Observability
    LANGCHAIN_TRACING_V2: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: Optional[str] = None
    
    # Agent Memory
    MEMORY_ENABLED: bool = True

    # Human-in-the-Loop
    HITL_ENABLED: bool = True

# Instantiate settings
settings = Settings()
