import os
from typing import List, Union
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Chatbot Backend"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # CORS settings
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []
    
    # AI Provider settings
    OPENROUTER_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEEPSEEK_API_KEY: str = ""
    
    # Vector DB settings
    QDRANT_HOST: str = "./qdrant_data"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "docs"
    
    # File storage settings
    FILE_STORAGE_PATH: str = "./uploads"
    TELEGRAM_BOT_TOKEN: str = ""
    
    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()