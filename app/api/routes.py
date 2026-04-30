from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from typing import Optional
import re
from app.models.schemas import Question, Answer, UserProfile
from pydantic import BaseModel
from app.services.ai_service import ai_service
from app.services.vector_db_service import vector_db_service
from app.services.file_processing_service import file_processing_service
from app.services.conversation_service import conversation_service
from app.services.user_profile_service import get_user_profile, save_user_profile

# ── BARU: session state untuk melacak asked_fields & first_message ──
from app.services.session_state_service import (
    is_first_message,
    mark_not_first,
    get_asked_fields,
    set_asked_fields,
)

import requests
from app.core.config import settings

api_router = APIRouter()


# ─────────────────────────────────────────────
# FIELD PROFIL YANG BELUM TERISI
# ─────────────────────────────────────────────
PROFILE_FIELDS_ORDER = ["jabatan", "tipe_tempat", "nama_masjid", "jumlah_jamaah", "lokasi"]

PROFILE_QUESTIONS = {
    "jabatan":       "Boleh saya tahu, Anda menjabat sebagai apa di sana? (misalnya Ketua DKM, Bendahara, Takmir, dll) 🙏",
    "tipe_tempat":   "Tempat ibadahnya masjid atau mushola/langgar? 😊",
    "nama_masjid":   "Nama masjid/musholanya apa? ✨",
    "jumlah_jamaah": "Kira-kira berapa jamaah aktifnya? (boleh perkiraan) 😊",
    "lokasi":        "Berada di kota/daerah mana? 🙏",
}

GREETING_FIRST = (
    "Assalamualaikum! Selamat datang di emasjid.id 🙏\n\n"
    "Saya asisten virtual yang siap membantu pengelolaan masjid/mushola Anda.\n\n"
    "Sebelum kita mulai, boleh saya kenalan dulu?\n"
    "{first_question}"
)


def _get_missing_fields(profile: Optional[UserProfile]) -> list[str]:
    """Kembalikan daftar field yang belum terisi, sesuai urutan prioritas."""
    if not profile:
        return PROFILE_FIELDS_ORDER[:]
    missing = []
    for field in PROFILE_FIELDS_ORDER:
        if not getattr(profile, field, None):
            missing.append(field)
    return missing


def extract_profile_from_text(text: str, current: Optional[UserProfile]) -> UserProfile:
    profile = current or UserProfile()
    text_lower = text.lower()

    if not profile.jabatan:
        jabatan_map = {
            "ketua": "Ketua DKM", "bendahara": "Bendahara",
            "sekretaris": "Sekretaris", "takmir": "Takmir",
            "marbot": "Marbot", "pengurus": "Pengurus DKM", "dkm": "Pengurus DKM",
        }
        for kw, label in jabatan_map.items():
            if kw in text_lower:
                profile.jabatan = label
                break

    if not profile.tipe_tempat:
        if any(k in text_lower for k in ["mushola", "musola", "langgar", "surau"]):
            profile.tipe_tempat = "Mushola/Langgar"
        elif "jami" in text_lower:
            profile.tipe_tempat = "Masjid Jami'"
        elif "masjid" in text_lower:
            profile.tipe_tempat = "Masjid"

    if not profile.jumlah_jamaah:
        for a in re.findall(r'\b(\d{2,4})\b', text):
            if 50 <= int(a) <= 10000:
                profile.jumlah_jamaah = f"~{a} orang"
                break

    return profile



# ─────────────────────────────────────────────
# EKSTRAKSI PROFIL — HANYA DARI JAWABAN EKSPLISIT
# Field hanya disimpan jika AI memang menanyakannya (ada di asked_fields)
# ─────────────────────────────────────────────
def extract_profile_from_answer(
    text: str,
    current: Optional[UserProfile],
    asked_fields: set,
) -> UserProfile:
    """
    Ekstrak info profil HANYA untuk field yang memang ditanyakan AI.
    Jika asked_fields kosong, tidak ada yang disimpan.
    """
    profile = current or UserProfile()
    text_lower = text.lower()

    if "jabatan" in asked_fields:
        jabatan_map = {
            "ketua": "Ketua DKM",
            "bendahara": "Bendahara",
            "sekretaris": "Sekretaris",
            "takmir": "Takmir",
            "marbot": "Marbot",
            "pengurus": "Pengurus DKM",
            "dkm": "Pengurus DKM",
        }
        for kw, label in jabatan_map.items():
            if kw in text_lower:
                profile.jabatan = label
                break

    if "tipe_tempat" in asked_fields:
        if any(k in text_lower for k in ["mushola", "musola", "langgar", "surau"]):
            profile.tipe_tempat = "Mushola/Langgar"
        elif "jami" in text_lower:
            profile.tipe_tempat = "Masjid Jami'"
        elif "masjid" in text_lower:
            profile.tipe_tempat = "Masjid"

    if "jumlah_jamaah" in asked_fields:
        angka = re.findall(r'\b(\d{2,4})\b', text)
        for a in angka:
            if 50 <= int(a) <= 10000:
                profile.jumlah_jamaah = f"~{a} orang"
                break

    # nama_masjid & lokasi: simpan teks mentah jika sedang ditanya
    if "nama_masjid" in asked_fields and len(text.strip()) > 2:
        profile.nama_masjid = text.strip().title()

    if "lokasi" in asked_fields and len(text.strip()) > 2:
        profile.lokasi = text.strip().title()

    return profile


# ─────────────────────────────────────────────
# Input models
# ─────────────────────────────────────────────
class UrlInput(BaseModel):
    url: str

class SitemapInput(BaseModel):
    url: str
    limit: int = 10


def check_order_status(order_id: str) -> str:
    return f"Pesanan #{order_id} status: sedang diproses"


# ─────────────────────────────────────────────
# /ask — dengan proaktif profiling
# ─────────────────────────────────────────────
@api_router.post("/ask", response_model=Answer)
async def ask_question(question: Question) -> Answer:
    conversation_id = question.conversation_id or conversation_service.create_conversation("user")
    original_question_text = question.question
    lower_question = original_question_text.lower()
    tokens_used = 0
    user_id = question.user_id or conversation_id   # fallback ke conversation_id

    # ── Ambil profil ──
    profile = question.user_profile
    if not profile and user_id:
        profile = get_user_profile(user_id)

    # ── Ambil asked_fields dari session ──
    asked_fields = get_asked_fields(user_id)

    # ── Update profil HANYA dari jawaban atas pertanyaan yang sudah ditanyakan ──
    if asked_fields:
        profile = extract_profile_from_answer(original_question_text, profile, asked_fields)
        if user_id:
            save_user_profile(user_id, profile)
        set_asked_fields(user_id, set())   # reset setelah diproses

    # ── Handle perintah khusus order/pesanan ──
    if "pesanan" in lower_question or "order" in lower_question:
        match = re.search(r"\d+", lower_question)
        answer_text = check_order_status(match.group(0)) if match else "Silakan sertakan nomor pesanan Anda."
        conversation_service.add_message(conversation_id, {"role": "user", "content": original_question_text})
        conversation_service.add_message(conversation_id, {"role": "assistant", "content": answer_text})
        return Answer(
            answer=answer_text,
            conversation_id=conversation_id,
            tokens_used=0,
            user_profile=profile
        )

    # ─────────────────────────────────────────────
    # PROAKTIF PROFILING
    # ─────────────────────────────────────────────
    missing = _get_missing_fields(profile)
    first = is_first_message(user_id)

    # KASUS 1: Pesan pertama → sapa + tanya field pertama
    if first:
        mark_not_first(user_id)
        next_field = missing[0] if missing else None
        if next_field:
            set_asked_fields(user_id, {next_field})
            answer_text = GREETING_FIRST.format(
                first_question=PROFILE_QUESTIONS[next_field]
            )
            conversation_service.add_message(conversation_id, {"role": "user", "content": original_question_text})
            conversation_service.add_message(conversation_id, {"role": "assistant", "content": answer_text})
            return Answer(
                answer=answer_text,
                conversation_id=conversation_id,
                tokens_used=0,
                user_profile=profile
            )
        # Profil sudah lengkap dari awal → lanjut normal
        mark_not_first(user_id)

    # KASUS 2: Profil belum lengkap → AI jawab dulu, lalu tanya 1 field di akhir
    # (tidak interrupt user, tapi tetap gali profil secara natural)
    profiling_suffix = ""
    if missing:
        next_field = missing[0]
        set_asked_fields(user_id, {next_field})
        profiling_suffix = f"\n\n---\n💬 *{PROFILE_QUESTIONS[next_field]}*"
    else:
        set_asked_fields(user_id, set())

    # ── Cari di knowledge base ──
    results = vector_db_service.search(original_question_text, limit=1, score_threshold=0.7)

    persona = "CRM"
    context = None

    if results:
        top_result = results[0]
        context = " ".join([r["content"] for r in results])
        retrieved_kategori = top_result.get("metadata", {}).get("kategori", "Umum").lower()
        if "sales" in retrieved_kategori:
            persona = "Sales"
        elif "komplain" in retrieved_kategori:
            persona = "Komplain"

    persona_prompts = {
        "Sales": (
            "Anda adalah spesialis penjualan dari emasjid.id. "
            "Gaya bicara Anda ramah, antusias, dan persuasif. "
            "Fokus pada manfaat produk dan akhiri dengan call to action jika memungkinkan."
        ),
        "CRM": (
            "Anda adalah customer support senior dari emasjid.id. "
            "Gaya bicara sabar, informatif, dan membantu. "
            "Gunakan sapaan 'Bapak/Ibu' dan emoji positif (🙏, 😊, ✨)."
        ),
        "Komplain": (
            "Anda adalah staf teknis emasjid.id yang menangani keluhan. "
            "Gaya bicara tenang, empatik, dan solutif. "
            "Tunjukkan pemahaman dan berikan solusi yang jelas."
        ),
        "General": (
            "Anda adalah asisten virtual resmi dari emasjid.id. "
            "Jawab pertanyaan dengan jelas, akurat, dan profesional."
        ),
    }

    persona_instruction = persona_prompts.get(persona, persona_prompts["CRM"])

    question_with_profile = Question(
        question=question.question,
        model=question.model,
        conversation_id=conversation_id,
        user_id=user_id,
        user_profile=profile
    )

    # ── Ambil riwayat percakapan sebelumnya untuk dikirim ke AI ──
    history = []
    conv = conversation_service.get_conversation(conversation_id)
    if conv:
        history = conv.get("messages", [])

    response = ai_service.generate_response(
        question_with_profile,
        context,
        persona_prompt=persona_instruction,
        conversation_history=history,       # ← riwayat percakapan
        is_first_message=False,             # ← di titik ini salam sudah dilakukan
    )
    answer_text = response["answer"] + profiling_suffix
    tokens_used = response.get("tokens_used", 0)

    # Simpan riwayat percakapan
    conversation_service.add_message(conversation_id, {"role": "user", "content": original_question_text})
    conversation_service.add_message(conversation_id, {"role": "assistant", "content": answer_text})

    return Answer(
        answer=answer_text,
        conversation_id=conversation_id,
        tokens_used=tokens_used,
        user_profile=profile
    )

@api_router.get("/webhook/whatsapp")
async def whatsapp_webhook_verify():
    """Fonnte butuh GET yang return 200 untuk verifikasi"""
    return {"status": "ok"}

@api_router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request):
    try:
        # Coba parse form-data
        try:
            form = await request.form()
            data = dict(form)
        except:
            data = {}

        # Kalau form kosong, coba JSON
        if not data:
            try:
                data = await request.json()
            except:
                data = {}

        # Log SETELAH data ada
        print(f"[WEBHOOK HIT] sender={data.get('sender')} msg={str(data.get('message', ''))[:50]}")
        print(f"FINAL DATA: {data}")

        wa_user_id = data.get("sender", "")
        text = data.get("message", "")

        if not wa_user_id or not text:
            return {"status": "ok"}

        if wa_user_id == settings.WHATSAPP_BOT_NUMBER:
            return {"status": "ok"}

        profile = get_user_profile(wa_user_id)
        profile = extract_profile_from_text(text, profile)
        save_user_profile(wa_user_id, profile)

        internal_response = await ask_question(Question(
            question=text,
            conversation_id=wa_user_id,
            model=settings.DEFAULT_MODEL,
            user_id=wa_user_id,
            user_profile=profile
        ))

        _send_whatsapp_message(wa_user_id, internal_response.answer)
        return {"status": "ok"}

    except Exception as e:
        print(f"Error: {e}")
        return {"status": "ok"}

# @api_router.post("/webhook/whatsapp")
# async def whatsapp_webhook(request: Request):
#     try:
#         # Coba parse form-data
#         try:
#             form = await request.form()
#             data = dict(form)
#         except:
#             data = {}

#         # Kalau form kosong, coba JSON
#         if not data:
#             try:
#                 data = await request.json()
#             except:
#                 data = {}

#         # ── VAR DUMP & EXIT ──
#         return {
#             "debug": True,
#             "data": data,
#             "sender": data.get("sender"),
#             "message": data.get("message"),
#             "device": data.get("device"),
#             "type": data.get("type"),
#         }

#     except Exception as e:
#         return {"error": str(e)}



def _send_whatsapp_message(to: str, text: str):
    response = requests.post(
        "https://api.fonnte.com/send",
        headers={"Authorization": settings.FONNTE_TOKEN},
        data={"target": to, "message": text, "countryCode": "62"}
    )
    if response.status_code != 200:
        print(f"Fonnte send error: {response.text}")

# ─────────────────────────────────────────────
# Endpoint lain (tidak berubah)
# ─────────────────────────────────────────────
@api_router.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):
    try:
        content = await file.read()
        chunks = []
        if file.content_type == "application/pdf":
            chunks = file_processing_service.process_pdf(content)
        elif file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            chunks = file_processing_service.process_docx(content)
        elif file.content_type == "text/plain":
            chunks = file_processing_service.process_txt(content)
        elif file.content_type == "text/csv" or file.filename.endswith('.csv'):
            chunks = file_processing_service.process_csv(content)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}")

        document_ids = [vector_db_service.upsert_document(chunk) for chunk in chunks]
        return {"status": "Document processed successfully", "chunks": len(chunks), "document_ids": document_ids}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")


@api_router.post("/process-url")
async def process_url(input_data: UrlInput):
    try:
        chunks = file_processing_service.process_url(input_data.url)
        if not chunks:
            raise HTTPException(status_code=400, detail="Tidak dapat mengekstrak teks dari URL.")
        document_ids = [
            vector_db_service.upsert_document(content=chunk, metadata={"source": input_data.url, "type": "website"})
            for chunk in chunks
        ]
        return {"status": "Berhasil", "chunks_added": len(chunks), "url": input_data.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@api_router.post("/process-sitemap")
async def process_sitemap(input_data: SitemapInput):
    try:
        urls = file_processing_service.process_sitemap(input_data.url)
        if not urls:
            raise HTTPException(status_code=400, detail="Tidak dapat menemukan URL dari sitemap.")
        urls_to_process = urls[:input_data.limit]
        total_chunks = 0
        processed_urls = []
        for url in urls_to_process:
            chunks = file_processing_service.process_url(url)
            if chunks:
                for chunk in chunks:
                    vector_db_service.upsert_document(content=chunk, metadata={"source": url, "type": "website"})
                total_chunks += len(chunks)
                processed_urls.append(url)
        return {
            "status": "Proses sitemap selesai",
            "total_urls_in_sitemap": len(urls),
            "urls_processed": len(processed_urls),
            "chunks_added": total_chunks,
            "processed_urls": processed_urls
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
@api_router.post("/webhook/telegram")
async def telegram_webhook(update: dict):
    try:
        message = update.get("message", {})
        if not message or "text" not in message:
            return {"status": "ok"}

        chat_id = str(message["chat"]["id"])
        telegram_user_id = str(message["from"]["id"])
        text = message["text"]
        conversation_id = telegram_user_id

        # Load profil — ekstraksi dilakukan di dalam ask_question berdasarkan asked_fields
        profile = get_user_profile(telegram_user_id)

        internal_response = await ask_question(Question(
            question=text,
            conversation_id=conversation_id,
            model=settings.DEFAULT_MODEL,
            user_id=telegram_user_id,
            user_profile=profile
        ))

        # Simpan profil yang mungkin sudah terupdate
        if internal_response.user_profile:
            save_user_profile(telegram_user_id, internal_response.user_profile)

        telegram_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(telegram_url, json={
            "chat_id": chat_id,
            "text": internal_response.answer,
            "parse_mode": "Markdown"
        })

        return {"status": "ok"}
    
    except Exception as e:
        print(f"Telegram webhook error: {e}")
        return {"status": "error"}

@api_router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    conversation = conversation_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@api_router.get("/health")
async def health_check():
    return {"status": "healthy"}