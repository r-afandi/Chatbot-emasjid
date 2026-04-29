from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from typing import List
import re
from app.models.schemas import Question, Answer
from pydantic import BaseModel
from app.services.ai_service import ai_service
from app.services.vector_db_service import vector_db_service
from app.services.file_processing_service import file_processing_service
from app.services.conversation_service import conversation_service

import requests
from app.core.config import settings

api_router = APIRouter()

class UrlInput(BaseModel):
    url: str

class SitemapInput(BaseModel):
    url: str
    limit: int = 10  # Batasi jumlah URL yang diproses dalam 1 request agar tidak timeout

def check_order_status(order_id: str) -> str:
    """Mock function to check order status"""
    # In a real implementation, this would call your Laravel API
    # For now, we'll return a mock response
    return f"Pesanan #{order_id} status: sedang diproses"

def fallback_to_cs() -> str:
    """Fallback response when no other handler can process the query"""
    return "Saya tidak yakin dengan jawaban ini. Silakan hubungi Customer Service 👩‍💻."

@api_router.post("/ask", response_model=Answer)
async def ask_question(question: Question) -> Answer:
    """
    Main endpoint for asking questions, now with persona support.
    The logic first tries to find relevant context from the vector DB.
    Based on the context's category, it adopts a persona (CRM, Sales, etc.).
    """
    # 1. Setup conversation and store original question
    conversation_id = question.conversation_id or conversation_service.create_conversation("user")
    original_question_text = question.question
    lower_question = original_question_text.lower()
    tokens_used = 0

    # 2. Handle special commands first (e.g., order status)
    if "pesanan" in lower_question or "order" in lower_question:
        match = re.search(r"\d+", lower_question)
        if match:
            order_id = match.group(0)
            answer_text = check_order_status(order_id)
        else:
            answer_text = "Silakan sertakan nomor pesanan Anda."

    # 3. For all other questions, use RAG and persona logic
    else:
        # Search for relevant context with a score threshold to ensure relevance
        results = vector_db_service.search(original_question_text, limit=1, score_threshold=0.7)

        persona = "CRM"  # Default persona if no context is found
        context = None

        # Determine persona and context from search results
        if results:
            top_result = results[0]
            context = " ".join([r["content"] for r in results])
            # Retrieve category from the document's metadata
            retrieved_kategori = top_result.get("metadata", {}).get("kategori", "Umum").lower()

            if "sales" in retrieved_kategori:
                persona = "Sales"
            elif "crm" in retrieved_kategori:
                persona = "CRM"
            elif "komplain" in retrieved_kategori:
                persona = "Komplain"

        # Define persona instructions to be prepended to the AI prompt
        persona_prompts = {
            "Sales": "Anda adalah spesialis penjualan dari emasjid.id. Gaya bicara Anda harus ramah, antusias, dan persuasif. Tujuan utama Anda adalah meyakinkan pengguna untuk menggunakan atau meng-upgrade layanan. Fokus pada manfaat dan nilai tambah produk. Akhiri jawaban dengan ajakan bertindak (call to action) yang relevan jika memungkinkan.",
            "CRM": "Anda adalah customer support senior dari emasjid.id. Gaya bicara Anda harus sabar, informatif, dan sangat membantu. Selalu gunakan sapaan 'Bapak/Ibu' dan emoji positif (seperti 🙏, 😊, ✨). Tujuan Anda adalah membuat pengguna merasa didukung dan mendorong mereka untuk terus menggunakan layanan emasjid.id.",
            "Komplain": "Anda adalah staf teknis dari emasjid.id yang menangani keluhan. Gaya bicara Anda harus tenang, empatik, dan solutif. Tunjukkan pemahaman terhadap masalah pengguna dan berikan solusi jelas atau informasikan langkah selanjutnya. Tujuannya adalah menenangkan pengguna dan meyakinkan mereka bahwa masalahnya sedang ditangani.",
            "General": "Anda adalah asisten virtual resmi dari emasjid.id. Jawab pertanyaan dengan jelas, akurat, dan profesional."
        }

        # Get the persona instruction, but do not prepend it to the question text
        persona_instruction = persona_prompts.get(persona, persona_prompts["CRM"])

        # Call AI service with or without context
        # The original question text is in `question.question`
        # The persona instruction is passed separately
        response = ai_service.generate_response(question, context, persona_prompt=persona_instruction)
        answer_text = response["answer"]
        tokens_used = response.get("tokens_used", 0)

    # 4. Save conversation history with the original question
    conversation_service.add_message(conversation_id, {
        "role": "user",
        "content": original_question_text
    })
    conversation_service.add_message(conversation_id, {
        "role": "assistant",
        "content": answer_text
    })

    # 5. Return the final answer
    return Answer(
        answer=answer_text,
        conversation_id=conversation_id,
        tokens_used=tokens_used
    )

@api_router.post("/upload-document")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a document"""
    try:
        content = await file.read()
        
        # Process based on file extension
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
            supported_types = [
                "PDF (.pdf) - untuk dokumen umum",
                "Word (.docx) - terbaik untuk tabel dan format",
                "CSV (.csv) - untuk data terstruktur",
                "Text (.txt) - untuk konten sederhana"
            ]
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {file.content_type}. Supported types: {', '.join(supported_types)}"
            )
        
        # Store chunks in vector database
        document_ids = []
        for chunk in chunks:
            doc_id = vector_db_service.upsert_document(chunk)
            document_ids.append(doc_id)
        
        return {
            "status": "Document processed successfully",
            "chunks": len(chunks),
            "document_ids": document_ids
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

@api_router.post("/process-url")
async def process_url(input_data: UrlInput):
    """Scrape a URL and add its content to the vector database"""
    try:
        chunks = file_processing_service.process_url(input_data.url)
        
        if not chunks:
            raise HTTPException(
                status_code=400, 
                detail="Tidak dapat mengekstrak teks dari URL. Website mungkin memblokir bot, menggunakan full JavaScript, atau konten kosong."
            )
            
        document_ids = []
        for chunk in chunks:
            doc_id = vector_db_service.upsert_document(
                content=chunk,
                metadata={"source": input_data.url, "type": "website"}
            )
            if doc_id:
                document_ids.append(doc_id)
                
        return {
            "status": "Berhasil membaca dan menyimpan data dari URL",
            "chunks_added": len(chunks),
            "url": input_data.url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing URL: {str(e)}")

@api_router.post("/process-sitemap")
async def process_sitemap(input_data: SitemapInput):
    """Scrape multiple URLs from a sitemap XML"""
    try:
        urls = file_processing_service.process_sitemap(input_data.url)
        
        if not urls:
            raise HTTPException(status_code=400, detail="Tidak dapat menemukan URL atau format sitemap tidak valid.")
            
        urls_to_process = urls[:input_data.limit]
        total_chunks = 0
        processed_urls = []
        
        for url in urls_to_process:
            chunks = file_processing_service.process_url(url)
            if chunks:
                for chunk in chunks:
                    vector_db_service.upsert_document(
                        content=chunk,
                        metadata={"source": url, "type": "website"}
                    )
                total_chunks += len(chunks)
                processed_urls.append(url)
                
        return {
            "status": "Proses sitemap selesai",
            "total_urls_in_sitemap": len(urls),
            "urls_processed": len(processed_urls),
            "chunks_added": total_chunks,
            "processed_urls": processed_urls,
            "message": f"Berhasil memproses {len(processed_urls)} URL dari total {len(urls)} URL (dibatasi {input_data.limit})."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing sitemap: {str(e)}")

api_router.get("/set_webhook")
async def set_telegram_webhook(url: str = None):
    """Set webhook URL for Telegram bot"""
    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN not set")
    
    if not url:
        raise HTTPException(status_code=400, detail="Provide 'url' query parameter, e.g. /set_webhook?url=https://your-ngrok-url.ngrok.io/api/v1/webhook/telegram")
    
    telegram_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    payload = {"url": url}
    response = requests.post(telegram_url, json=payload)
    
    if response.status_code == 200:
        return {"status": "Webhook set successfully", "url": url}
    else:
        raise HTTPException(status_code=500, detail=f"Failed to set webhook: {response.text}")

@api_router.post("/webhook/telegram")
async def telegram_webhook(update: dict):
    """Handle incoming messages from Telegram"""
    try:
        # Extract message details
        message = update.get("message", {})
        if not message or "text" not in message:
            return {"status": "ok"}  # Ignore non-text messages
        
        chat_id = message["chat"]["id"]
        user_id = message["from"]["id"]
        text = message["text"]
        
        # Use chat_id as conversation_id for simplicity
        conversation_id = str(chat_id)
        
        # Call internal ask endpoint
        internal_response = await ask_question(Question(
            question=text,
            conversation_id=conversation_id,
            model=settings.DEFAULT_MODEL  

        ))
        
        # Send response back to Telegram
        telegram_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": internal_response.answer
        }
        requests.post(telegram_url, json=payload)
        
        return {"status": "ok"}
    
    except Exception as e:
        # Log error and respond
        print(f"Telegram webhook error: {e}")
        return {"status": "error"}

@api_router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history"""
    conversation = conversation_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation

@api_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}