from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

# ─────────────────────────────────────────────
# User Profile — disimpan permanen per nomor WA/Telegram
# Terpisah dari conversation agar tidak hilang saat sesi baru
# ─────────────────────────────────────────────
class UserProfile(BaseModel):
    jabatan: Optional[str] = None           # Ketua DKM, Bendahara, Takmir, dll
    tipe_tempat: Optional[str] = None       # Masjid Jami', Mushola, Langgar
    nama_masjid: Optional[str] = None
    jumlah_jamaah: Optional[str] = None
    lokasi: Optional[str] = None
    updated_at: Optional[datetime] = None

class Question(BaseModel):
    question: str
    model: str = "deepseek/deepseek-chat"
    conversation_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    # BARU: identitas permanen pengirim (nomor WA / Telegram user_id)
    user_id: Optional[str] = None
    # BARU: profil yang sudah terkumpul sebelumnya, di-inject tiap request
    user_profile: Optional[UserProfile] = None

class Answer(BaseModel):
    answer: str
    conversation_id: str
    sources: Optional[List[str]] = None
    tokens_used: Optional[int] = None
    # BARU: profil terbaru setelah mungkin ada update dari percakapan ini
    user_profile: Optional[UserProfile] = None

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