# =======================================
# 1️⃣ Install Package (hanya sekali jalan di Colab / lokal)
# =======================================
!pip install fastapi uvicorn nest_asyncio pyngrok qdrant-client sentence-transformers pypdf requests

import nest_asyncio
from pyngrok import ngrok
import io
import uuid
import re

# patch supaya FastAPI bisa jalan di Colab
nest_asyncio.apply()

# =======================================
# 2️⃣ Import Library
# =======================================
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import uvicorn
from pypdf import PdfReader
import qdrant_client
from qdrant_client.models import PointStruct, VectorParams, Distance
import requests
import os

# =======================================
# 3️⃣ Setup Vector DB (Qdrant in-memory)
# =======================================
client = qdrant_client.QdrantClient(":memory:")

COLLECTION = "docs"
embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")  # support bhs Indo

client.recreate_collection(
    collection_name=COLLECTION,
    vectors_config=VectorParams(
        size=embedding_model.get_sentence_embedding_dimension(),
        distance=Distance.COSINE
    )
)

# =======================================
# 4️⃣ FastAPI App + CORS
# =======================================
app = FastAPI()

# ✅ Izinkan akses dari semua domain (atau ganti ke domain Laravel kamu)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # bisa diganti ["http://localhost:8000"] kalau spesifik
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Schema request
class Question(BaseModel):
    question: str
    model: str = "deepseek/deepseek-chat"


# =======================================
# 5️⃣ Konfigurasi API OpenRouter
# =======================================
OPENROUTER_API_KEY = "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"  # ganti dengan key kamu
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


# ========== Upload PDF → VectorDB ==========
@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))

        texts = []
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                texts.append(txt)

        chunks = []
        for t in texts:
            for chunk in t.split(". "):
                if len(chunk.strip()) > 20:
                    chunks.append(chunk.strip())

        points = []
        for chunk in chunks:
            vec = embedding_model.encode(chunk).tolist()
            points.append(
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vec,
                    payload={"text": chunk}
                )
            )

        client.upsert(collection_name=COLLECTION, points=points)

        return {"status": "PDF processed", "chunks": len(chunks)}

    except Exception as e:
        return {"error": str(e)}


# ========== RAG Answer ==========
def ask_rag(question: str, model: str):
    q_vec = embedding_model.encode(question).tolist()
    results = client.search(collection_name=COLLECTION, query_vector=q_vec, limit=3)

    if not results:
        return "Maaf, saya tidak menemukan jawaban yang relevan."

    context = " ".join([r.payload["text"] for r in results])

    prompt = f"""
    Anda adalah asisten yang membantu menjawab pertanyaan user.
    Gunakan informasi berikut untuk menjawab dengan bahasa alami:

    KONTEKS:
    {context}

    PERTANYAAN: {question}
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "Laravel Chatbot"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Anda adalah asisten ramah dan membantu."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 300
    }

    response = requests.post(OPENROUTER_ENDPOINT, headers=headers, json=payload)
    resp_json = response.json()

    if "choices" in resp_json:
        return resp_json["choices"][0]["message"]["content"]

    return f"Error dari API: {resp_json}"


# ========== Cek Status Pesanan (API Laravel) ==========
def check_order_status(order_id: str):
    try:
        resp = requests.get(f"http://127.0.0.1:8000/api/orders/{order_id}")  # ganti sesuai Laravel
        if resp.status_code == 200:
            data = resp.json()
            return f"Pesanan #{order_id} status: {data.get('status', 'tidak ditemukan')}"
        return f"Pesanan #{order_id} tidak ditemukan."
    except Exception as e:
        return f"Error cek pesanan: {str(e)}"


# ========== Fallback ke CS ==========
def fallback_to_cs():
    return "Saya tidak yakin dengan jawaban ini. Silakan hubungi Customer Service 👩‍💻."


# ========== Endpoint Hybrid /ask ==========
@app.post("/ask")
async def ask(q: Question):
    question = q.question.lower()

    # Case 1: cek status pesanan
    if "pesanan" in question or "order" in question:
        match = re.search(r"\d+", question)
        if match:
            order_id = match.group(0)
            return {"answer": check_order_status(order_id)}
        else:
            return {"answer": "Silakan sertakan nomor pesanan Anda."}

    # Case 2: FAQ umum → RAG
    elif any(keyword in question for keyword in ["harga", "alamat", "jam", "produk", "layanan"]):
        return {"answer": ask_rag(q.question, q.model)}

    # Case 3: fallback
    else:
        return {"answer": fallback_to_cs()}


# =======================================
# 6️⃣ Jalankan di Colab (ngrok) atau Lokal
# =======================================

# 🔹 Kalau di Google Colab:
!ngrok config add-authtoken "2r3kCqjGShBkd2uc7MnDlpE4C4e_5u5kWjQ7f4XoJPNnfouCV"
public_url = ngrok.connect(8000)
print("Public URL:", public_url)
uvicorn.run(app, host="0.0.0.0", port=8000)

# 🔹 Kalau di lokal (terminal):
# simpan file ini sebagai `app.py`, lalu jalankan:
# uvicorn app:app --reload --host 0.0.0.0 --port 8000
