from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class Question(BaseModel):
    question: str
    model: str = "deepseek/deepseek-chat"
    conversation_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class Answer(BaseModel):
    answer: str
    conversation_id: str
    sources: Optional[List[str]] = None
    tokens_used: Optional[int] = None

class Document(BaseModel):
    id: str
    content: str
    metadata: Optional[Dict[str, Any]] = None

class Conversation(BaseModel):
    id: str
    user_id: str
    messages: List[Dict[str, str]]
    created_at: datetime
    updated_at: datetime

class UploadResponse(BaseModel):
    status: str
    chunks: int
    document_id: str