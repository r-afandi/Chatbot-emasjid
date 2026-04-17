import requests
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional

# URL backend chatbot utama Anda (yang berjalan di port 8000)
CHATBOT_BACKEND_URL = "http://localhost:8000/api/v1/ask"

# Inisialisasi Aplikasi FastAPI untuk UI
app = FastAPI(title="UI Chatbot")

# Model data untuk request dari UI ke server UI ini
class ChatInput(BaseModel):
    question: str
    conversation_id: Optional[str] = None

# Template HTML, CSS, dan JavaScript untuk halaman chat
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Chat dengan Asisten eMasjid.id</title>
    <style>
        body { font-family: 'Segoe UI', sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .chat-container { width: 100%; max-width: 500px; height: 90vh; max-height: 700px; background: white; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.1); display: flex; flex-direction: column; }
        .chat-header { background-color: #007bff; color: white; padding: 15px; border-top-left-radius: 12px; border-top-right-radius: 12px; text-align: center; }
        .chat-header h2 { margin: 0; font-size: 1.2em; }
        .chat-messages { flex-grow: 1; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; }
        .message { max-width: 80%; padding: 10px 15px; border-radius: 18px; line-height: 1.5; word-wrap: break-word; }
        .message.user { background-color: #007bff; color: white; align-self: flex-end; border-bottom-right-radius: 4px; }
        .message.bot { background-color: #e9e9eb; color: #333; align-self: flex-start; border-bottom-left-radius: 4px; }
        .message.bot.thinking { color: #888; font-style: italic; }
        .chat-input { display: flex; padding: 15px; border-top: 1px solid #ddd; }
        #message-input { flex-grow: 1; border: 1px solid #ccc; border-radius: 20px; padding: 10px 15px; font-size: 1em; outline: none; }
        #send-button { background: #007bff; color: white; border: none; border-radius: 20px; padding: 0 20px; height: 40px; margin-left: 10px; cursor: pointer; font-size: 1em; font-weight: bold; display: flex; justify-content: center; align-items: center; }
        #send-button:hover { background: #0056b3; }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="chat-header">
            <h2>Asisten Virtual eMasjid.id</h2>
        </div>
        <div class="chat-messages" id="chat-messages">
            <div class="message bot">Assalamualaikum! Ada yang bisa saya bantu terkait layanan eMasjid.id?</div>
        </div>
        <div class="chat-input">
            <input type="text" id="message-input" placeholder="Ketik pertanyaan Anda..." autocomplete="off">
            <button id="send-button" type="button">Kirim</button>
        </div>
    </div>

    <script>
        const messageInput = document.getElementById('message-input');
        const sendButton = document.getElementById('send-button');
        const chatMessages = document.getElementById('chat-messages');
        let conversationId = null; // Akan diisi setelah chat pertama

        // Fungsi untuk menambahkan pesan ke UI
        function addMessage(text, sender) {
            const messageElement = document.createElement('div');
            // Menggunakan className karena sender bisa memiliki spasi (contoh: 'bot thinking')
            messageElement.className = `message ${sender}`;
            
            // Mengganti newline menjadi <br> secara aman dari interpretasi Python
            messageElement.innerHTML = String(text).replace(/\\\\n/g, '<br>').replace(/\\n/g, '<br>');

            chatMessages.appendChild(messageElement);
            chatMessages.scrollTop = chatMessages.scrollHeight; // Auto-scroll ke bawah
            return messageElement;
        }

        // Fungsi utama untuk mengirim pesan
        async function sendMessage() {
            const userMessage = messageInput.value.trim();
            if (!userMessage) return;

            // Nonaktifkan input dan tombol saat request dikirim
            messageInput.disabled = true;
            sendButton.disabled = true;

            addMessage(userMessage, 'user');
            messageInput.value = ''; // Kosongkan input

            const thinkingMessage = addMessage("Sedang menulis...", 'bot thinking');
            
            try {
                // Kirim pertanyaan ke server UI (yang akan meneruskannya ke backend utama)
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: userMessage,
                        conversation_id: conversationId
                    })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                
                // Hapus pesan "thinking..."
                thinkingMessage.remove();
                
                // Tampilkan jawaban dari bot
                addMessage(data.answer, 'bot');

                // Simpan conversation_id untuk chat selanjutnya
                if (data.conversation_id) {
                    conversationId = data.conversation_id;
                }

            } catch (error) {
                thinkingMessage.remove();
                addMessage('Maaf, terjadi kesalahan. Backend tidak dapat dihubungi. Pastikan server utama berjalan.', 'bot');
                console.error('Error:', error);
            } finally {
                // Aktifkan kembali input dan tombol setelah selesai, apapun hasilnya
                messageInput.disabled = false;
                sendButton.disabled = false;
                messageInput.focus();
            }
        }

        // Event handler untuk klik tombol kirim
        sendButton.addEventListener('click', sendMessage);

        // Event handler untuk menekan 'Enter' di input field
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault(); // Mencegah form submit default atau baris baru
                sendMessage();
            }
        });
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def get_chat_ui():
    """Menampilkan halaman utama UI Chatbot."""
    return HTML_TEMPLATE

@app.post("/api/chat")
async def chat_with_bot(chat_input: ChatInput):
    """
    Endpoint ini menerima pertanyaan dari UI, meneruskannya ke backend chatbot utama,
    dan mengembalikan jawabannya ke UI.
    """
    payload = {
        "question": chat_input.question,
        "conversation_id": chat_input.conversation_id,
        "model": "openai/gpt-3.5-turbo" # Anda bisa mengubah model default di sini
    }

    try:
        # Kirim request ke backend utama
        response = requests.post(CHATBOT_BACKEND_URL, json=payload, timeout=60)
        response.raise_for_status()  # Akan raise error jika status code bukan 2xx
        
        return response.json()

    except requests.exceptions.RequestException as e:
        # Jika backend utama tidak aktif atau ada error jaringan
        return {
            "answer": f"Maaf, tidak dapat terhubung ke server AI. Pastikan backend utama berjalan di {CHATBOT_BACKEND_URL}. Error: {e}",
            "conversation_id": chat_input.conversation_id,
            "tokens_used": 0
        }

if __name__ == "__main__":
    print("Menjalankan UI Chatbot di http://localhost:8001")
    print("Pastikan backend utama Anda juga sedang berjalan di port 8000.")
    uvicorn.run(app, host="0.0.0.0", port=8001)