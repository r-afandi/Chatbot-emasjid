# Dokumentasi Sistem UI eMasjid Chatbot

Sistem antarmuka ini terbagi menjadi dua aplikasi web mandiri yang berjalan di atas FastAPI:
1.  **Chatbot UI (`chatbot_ui.py`)**: Antarmuka untuk pengguna akhir (jamaah/klien) berinteraksi dengan AI.
2.  **Admin UI (`ui_kategori.py`)**: Antarmuka untuk pengurus/admin mengelola dan mengunggah data *Knowledge Base*.

---

## 1. Chatbot UI (`chatbot_ui.py`)

File ini bertindak sebagai jembatan (penengah) antara browser pengguna dan server *backend* AI utama. File ini berjalan di *port* `8001`.

### Alur Kerja (Data Flow)
1.  Pengguna membuka browser di `http://localhost:8001`.
2.  Halaman memuat antarmuka obrolan (HTML/CSS/JS).
3.  Saat pengguna mengetik pesan dan menekan "Kirim", JavaScript di browser mengirimkan *request* ke *endpoint* lokal `/api/chat`.
4.  *Endpoint* `/api/chat` (di file ini) menerima pesan, lalu meneruskannya ke server AI utama di `http://localhost:8000/api/v1/ask`.
5.  Setelah server AI merespons, jawaban dikembalikan ke browser pengguna untuk ditampilkan.

### Penjelasan Fungsi dan Komponen

*   **`CHATBOT_BACKEND_URL` (Konstanta)**
    Menyimpan alamat URL *backend* utama. Jika *backend* utama dipindahkan ke server *cloud* (misalnya VPS), URL ini harus diubah menyesuaikan alamat server tersebut.

*   **`class ChatInput(BaseModel)`**
    Struktur data (*schema*) yang mendefinisikan format *request* dari JavaScript UI ke server UI. Memiliki dua atribut:
    *   `question`: Teks pertanyaan pengguna.
    *   `conversation_id`: ID unik untuk melacak riwayat percakapan (bersifat opsional).

*   **`HTML_TEMPLATE` (Variabel String)**
    Menyimpan seluruh kode HTML, CSS, dan JavaScript untuk antarmuka pengguna.
    *   **Fungsi JS `addMessage(text, sender)`**: Bertugas membuat elemen HTML baru (gelembung *chat*) ke dalam layar.
    *   **Fungsi JS `sendMessage()`**: Bertugas membaca input pengguna, mematikan (*disable*) tombol agar pengguna tidak *spam* klik, memunculkan teks "Sedang menulis...", dan melakukan *fetch* (HTTP Request) ke `/api/chat`.

*   **`@app.get("/") -> get_chat_ui()`**
    *Endpoint* utama. Saat pengguna mengakses URL dasar (`http://localhost:8001`), fungsi ini mengembalikan kode `HTML_TEMPLATE` agar dirender oleh browser.

*   **`@app.post("/api/chat") -> chat_with_bot(chat_input)`**
    *Endpoint* ini adalah *middleware* (perantara). Fungsi ini mengambil `question` dan `conversation_id` dari antarmuka, membungkusnya dalam *payload*, dan menembakkannya menggunakan pustaka `requests.post` ke `CHATBOT_BACKEND_URL`. Fungsi ini juga dilengkapi dengan blok `try-except` untuk menangani *error* jika *backend* utama mati atau *timeout*.

---

## 2. Admin UI / Knowledge Base Manager (`ui_kategori.py`)

File ini berfungsi sebagai panel admin agar pengurus dapat dengan mudah memasukkan data basis pengetahuan (*Knowledge Base*) tanpa perlu menguasai bahasa pemrograman. File ini berjalan di *port* `8080`.

### Alur Kerja (Data Flow)
1.  Admin membuka browser di `http://localhost:8080`.
2.  Admin dapat memilih untuk mengetik data Q&A (Tanya Jawab) secara manual atau mengunggah file Excel (`.xlsx`).
3.  Data yang dikirim akan diproses oleh *endpoint* terkait, lalu disimpan atau ditambahkan ke dalam file `data_kategori_sementara.json`.
4.  File JSON ini nantinya akan dibaca oleh skrip `seed_knowledge.py` untuk dimasukkan ke dalam otak AI (Qdrant Vector DB).

### Penjelasan Fungsi dan Komponen

*   **`JSON_FILE` (Konstanta)**
    Menentukan nama file tempat penyimpanan data (yaitu `data_kategori_sementara.json`).

*   **`load_json_records(filepath: str) -> list`**
    Fungsi pembantu (*helper*) untuk membaca isi file JSON yang sudah ada. Dilengkapi pengamanan: jika file tidak ditemukan, kosong, atau formatnya rusak (*JSONDecodeError*), ia akan otomatis mengembalikan daftar (*list*) kosong `[]` agar aplikasi tidak *crash*.

*   **`class LayananInput(BaseModel)`**
    Skema data untuk menerima input dari form manual. Berisi `nama`, `kategori`, `pertanyaan`, dan `jawaban`.

*   **`HTML_TEMPLATE` (Variabel String)**
    Menyimpan tampilan UI Admin. Terdapat dua form di dalamnya:
    *   `#kategoriForm`: Mengirim data ketikan manual via JSON.
    *   `#uploadForm`: Mengirim file Excel via *FormData (Multipart)*.

*   **`@app.get("/") -> tampilkan_ui()`**
    *Endpoint* untuk merender dan menampilkan halaman antarmuka admin ke browser.

*   **`@app.post("/api/simpan") -> simpan_data(data)`**
    Fungsi ini menangani penyimpanan data secara manual.
    1.  Membaca data lama menggunakan `load_json_records()`.
    2.  Membuat *ID Tiket* baru secara otomatis berdasarkan jumlah data yang ada (contoh: `TKT-0012`).
    3.  Mencatat waktu saat ini (`datetime.now()`).
    4.  Menggabungkan data input ke dalam satu kamus (*dictionary*) dan menambahkannya (`append`) ke daftar data lama.
    5.  Menyimpan kembali seluruh data ke dalam file `.json` dengan `ensure_ascii=False` agar karakter khusus tidak rusak.

*   **`@app.post("/api/upload-xlsx") -> upload_xlsx(file, kategori)`**
    Fungsi pemrosesan unggah masal (*bulk upload*).
    1.  Menerima file biner dari antarmuka.
    2.  Membaca isi file Excel menggunakan pustaka `openpyxl`.
    3.  Membaca baris pertama sebagai *Header* kolom (contoh: kolom 'pertanyaan', 'jawaban'). Header diubah menjadi huruf kecil (*lowercase*) agar sistem tidak sensitif terhadap huruf besar/kecil.
    4.  Melakukan *looping* untuk baris kedua dan seterusnya.
    5.  Jika kolom `pertanyaan` dan `jawaban` ada isinya (tidak kosong/None), sistem akan membuat *record* baru.
    6.  Menyimpan semua penambahan data ke dalam file JSON dan mengembalikan jumlah data yang berhasil ditambahkan.