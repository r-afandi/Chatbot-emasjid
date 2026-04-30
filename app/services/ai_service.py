import requests
import time
from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.models.schemas import Question, UserProfile

class AIService:
    def __init__(self):
        self.providers = {
            "openrouter": {
                "api_key": settings.OPENROUTER_API_KEY,
                "endpoint": "https://openrouter.ai/api/v1/chat/completions"
            },
            "openai": {
                "api_key": settings.OPENAI_API_KEY,
                "endpoint": "https://api.openai.com/v1/chat/completions"
            },
            "anthropic": {
                "api_key": settings.ANTHROPIC_API_KEY,
                "endpoint": "https://api.anthropic.com/v1/messages"
            }
        }

    def _build_profile_block(self, profile: Optional[UserProfile]) -> str:
        if not profile:
            return ""
        lines = []
        if profile.jabatan:
            lines.append(f"- Jabatan     : {profile.jabatan}")
        if profile.tipe_tempat:
            lines.append(f"- Tipe tempat : {profile.tipe_tempat}")
        if profile.nama_masjid:
            lines.append(f"- Nama masjid : {profile.nama_masjid}")
        if profile.jumlah_jamaah:
            lines.append(f"- Jamaah      : {profile.jumlah_jamaah}")
        if profile.lokasi:
            lines.append(f"- Lokasi      : {profile.lokasi}")
        if not lines:
            return ""
        return "\nPROFIL USER YANG SUDAH DIKETAHUI:\n" + "\n".join(lines)

    def _profile_is_sufficient(self, profile: Optional[UserProfile]) -> bool:
        if not profile:
            return False
        return bool(profile.jabatan and profile.tipe_tempat)

    def _get_provider_from_model(self, model: str) -> str:
        model_lower = model.lower()
        if "/" in model:
            prefix = model_lower.split("/")[0]
            if prefix in ["openai", "anthropic", "meta-llama", "mistral", "neural-chat", "nous", "teknium", "openrouter"]:
                return "openrouter"
        if "gpt" in model_lower:
            return "openai"
        elif "claude" in model_lower:
            return "anthropic"
        else:
            return "openrouter"

    def _resolve_provider(self, model: str) -> Optional[str]:
        provider = self._get_provider_from_model(model)
        api_key = self.providers.get(provider, {}).get("api_key")
        if api_key:
            return provider
        for fallback in ["openrouter", "openai", "anthropic"]:
            if self.providers.get(fallback, {}).get("api_key"):
                return fallback
        return None

    def _prepare_headers(self, provider: str) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if provider == "openrouter":
            headers["Authorization"] = f"Bearer {self.providers['openrouter']['api_key']}"
            headers["HTTP-Referer"] = "http://localhost"
            headers["X-Title"] = "Chatbot Backend"
        elif provider == "openai":
            headers["Authorization"] = f"Bearer {self.providers['openai']['api_key']}"
        elif provider == "anthropic":
            headers["x-api-key"] = self.providers['anthropic']['api_key']
            headers["anthropic-version"] = "2023-06-01"
        return headers

    def _prepare_payload(self, provider: str, model: str, messages: List[Dict[str, str]],
                         max_tokens: int = 1500, temperature: float = 0.3) -> Dict[str, Any]:
        return {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

    def generate_response(
        self,
        question: Question,
        context: str = "",
        persona_prompt: str = "",
        # ── BARU: terima riwayat percakapan & flag first message ──
        conversation_history: Optional[List[Dict[str, str]]] = None,
        is_first_message: bool = False,
    ) -> Dict[str, Any]:

        provider = self._resolve_provider(question.model)
        if not provider:
            return {"answer": "Error: Tidak ada AI provider yang terkonfigurasi.", "tokens_used": 0}

        profile = question.user_profile
        profile_block = self._build_profile_block(profile)

        base_persona = persona_prompt or (
            "Anda adalah asisten virtual dari emasjid.id. "
            "Jawab pertanyaan dengan jelas dan akurat."
        )

        # ── BARU: aturan salam yang tegas ──
        salam_rules = """
        ATURAN SALAM (WAJIB):
        - Ucapkan salam pembuka (Assalamualaikum / Waalaikumsalam) HANYA pada pesan pertama sesi.
        - Jika riwayat percakapan sudah ada (ada pesan sebelumnya), JANGAN ulangi salam.
        - Jika user mengirim salam dalam percakapan yang sudah berjalan, balas singkat
        seperti "Wa'alaikumsalam 🙏 Ada lagi yang bisa saya bantu?" tanpa blok salam panjang.
        - JANGAN membuka setiap respons dengan "Assalamualaikum" di tengah percakapan.
        """

        proactive_rules = """
        ATURAN PROAKTIF (WAJIB DIIKUTI):
        1. SELALU jawab pertanyaan user terlebih dahulu, meski secara umum.
        Jangan pernah tanya dulu sebelum memberikan jawaban — kecuali pertanyaan
        benar-benar tidak bisa dijawab tanpa konteks (misalnya: "berapa iuran yang wajar?").
        2. Cari jawaban di knowledge base yang tersedia SEBELUM meminta info ke user.
        3. Setelah menjawab, tawarkan jawaban lebih spesifik jika profil user belum lengkap.
        4. Jika PROFIL USER SUDAH DIKETAHUI (lihat blok profil):
        - Langsung personalisasi jawaban sesuai profilnya.
        - JANGAN tanya ulang data yang sudah ada.
        - Gunakan sapaan sesuai jabatan (Pak Bendahara, Pak Ketua, dll).
        5. Jika harus menggali info, tanyakan maksimal 1 hal sekaligus.
        """

        profile_section = (
            profile_block if profile_block
            else "\nPROFIL USER: belum ada data."
        )

        # ── BARU: beri tahu AI apakah ini pesan pertama atau lanjutan ──
        conversation_context = (
            "\nSTATUS PERCAKAPAN: Ini adalah pesan PERTAMA dari user dalam sesi ini."
            if is_first_message
            else "\nSTATUS PERCAKAPAN: Percakapan sedang BERLANGSUNG. Salam sudah dilakukan. Jangan ulangi salam pembuka."
        )

        system_message = (
            base_persona
            + salam_rules
            + proactive_rules
            + profile_section
            + conversation_context
        )

        # ── BARU: bangun messages dengan riwayat percakapan ──
        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_message}
        ]

        # Inject riwayat percakapan sebelumnya agar AI punya memori konteks
        if conversation_history:
            # Batasi maksimal 10 pesan terakhir agar tidak membengkak token
            for msg in conversation_history[-10:]:
                if msg.get("role") in ("user", "assistant") and msg.get("content"):
                    messages.append({"role": msg["role"], "content": msg["content"]})

        # Tambahkan pesan user saat ini (dengan konteks KB jika ada)
        if context:
            user_message = (
                f"Berdasarkan KONTEKS berikut, jawab pertanyaan user.\n"
                f"Jika jawaban tidak ada di dalam konteks, katakan dengan jujur.\n"
                f"Jangan menambah fakta dari luar konteks.\n\n"
                f"KONTEKS:\n{context}\n\n"
                f"PERTANYAAN: {question.question}"
            )
        else:
            user_message = question.question

        messages.append({"role": "user", "content": user_message})

        headers = self._prepare_headers(provider)
        payload = self._prepare_payload(provider, question.model, messages)

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.providers[provider]["endpoint"],
                    headers=headers,
                    json=payload,
                    timeout=30
                )

                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            retry_delay = int(retry_after)
                        except ValueError:
                            pass
                    if attempt < max_retries - 1:
                        print(f"Rate limited (429). Retrying in {retry_delay}s... ({attempt + 1}/{max_retries})")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                        continue
                    else:
                        return {"answer": "API rate limit exceeded. Coba lagi nanti.", "tokens_used": 0}

                response.raise_for_status()
                resp_json = response.json()

                if provider == "anthropic":
                    content = resp_json.get("content", [{}])[0].get("text", "")
                    return {
                        "answer": content,
                        "tokens_used": resp_json.get("usage", {}).get("total_tokens", 0)
                    }
                else:
                    content = resp_json.get("choices", [{}])[0].get("message", {}).get("content", "")
                    usage = resp_json.get("usage", {})
                    tokens_used = usage.get("total_tokens", 0) or (
                        usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
                    )
                    return {"answer": content, "tokens_used": tokens_used}

            except requests.exceptions.RequestException as e:
                error_msg = str(e)
                if "429" in error_msg and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return {"answer": f"Error: {error_msg}", "tokens_used": 0}
            except Exception as e:
                return {"answer": f"Unexpected error: {str(e)}", "tokens_used": 0}


ai_service = AIService()