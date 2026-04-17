#!/usr/bin/env python3
"""
Seed Knowledge Base Script

This script populates the chatbot's knowledge base with initial data.
Run this script to seed the vector database with Q&A pairs and documents.

Usage:
    python seed_knowledge.py

Or from project root:
    py seed_knowledge.py
"""

import sys
import os
from typing import List, Dict, Any
import json

# Add the app directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.vector_db_service import vector_db_service

# Knowledge base data
KNOWLEDGE_DATA = [
    # Q&A Pairs - will be stored as searchable content
    {
        "type": "qa",
        "question": "Apa itu emasjid.id?",
        "answer": "Emasjid.id adalah platform digital terintegrasi untuk pengelolaan masjid modern. Platform ini menyediakan berbagai fitur untuk membantu masjid dalam hal administrasi, keuangan, dan pelayanan kepada jamaah."
    },
    {
        "type": "qa",
        "question": "Bagaimana cara mendaftar di emasjid.id?",
        "answer": "Untuk mendaftar di emasjid.id, pengurus masjid dapat mengakses situs web emasjid.id dan mengklik tombol 'Daftar'. Diperlukan data seperti nama masjid, alamat lengkap, nomor telepon, dan email aktif."
    },
    {
        "type": "qa",
        "question": "Apa saja fitur yang tersedia di emasjid.id?",
        "answer": "Fitur utama emasjid.id meliputi: Sistem informasi masjid, Manajemen keuangan dan zakat, Sistem informasi jamaah, Pengelolaan inventaris, Sistem booking acara, dan Laporan keuangan otomatis."
    },
    {
        "type": "qa",
        "question": "Berapa biaya menggunakan emasjid.id?",
        "answer": "Emasjid.id menawarkan berbagai paket mulai dari gratis hingga premium. Paket gratis menyediakan fitur dasar, sedangkan paket premium memberikan akses penuh ke semua fitur dengan harga terjangkau mulai dari Rp 50.000 per bulan."
    },
    {
        "type": "qa",
        "question": "Bagaimana cara reset password?",
        "answer": "Untuk reset password, klik 'Lupa Password' di halaman login, masukkan email terdaftar, dan ikuti instruksi yang dikirim ke email Anda. Jika tidak menerima email, periksa folder spam atau hubungi customer service."
    },

    {
        "type": "qa",
        "question": "bagaimana setelah memesan paket",
        "answer": """Assalamualaikum Bapak/Ibu 🙏😊

Terima kasih telah mendaftar dan mempercayakan pengelolaan Website serta Aplikasi Manajemen Masjid kepada eMasjid.id. Kami dengan senang hati menyampaikan bahwa *akun Website dan Aplikasi Manajemen Masjid Bapak/Ibu telah berhasil kami aktifkan* ✨

Bapak/Ibu dapat mengakses melalui tautan berikut:
👉 https://www.emasjid.id/member

Selain itu, Bapak/Ibu dapat mengelola profil masjid, mengelola jamaah, mengelola inventaris, hingga mengelola transaksi keuangan. Gunakan username dan password yang telah Bapak/Ibu daftarkan.

Apabila membutuhkan bantuan atau pendampingan lebih lanjut, jangan ragu untuk menghubungi *Kami Admin eMasjid.id.* Kami siap membantu 😊🙏

Semoga bermanfaat dan membawa keberkahan bagi masjid  🤲

Hormat kami,
Tim eMasjid.id
📞 0857-4259-5685"""
    },

    # Document content - will be chunked and stored
    {
        "type": "document",
        "title": "Panduan Form Pendataan emasjidasjid keuangan",
        "content": """
        FORM PENDATAAN MASJID EMASJID.ID

        Data yang wajib diisi untuk pendaftaran masjid baru:

        1. INFORMASI DASAR MASJID
        - Nama Masjid (wajib)
        - Alamat Lengkap (jalan, RT/RW, kelurahan, kecamatan, kota, kode pos)
        - Nomor Telepon Masjid
        - Email Masjid (jika ada)
        - Website/Sosial Media (opsional)

        2. INFORMASI TAKMIR/PENGURUS
        - Nama Ketua Takmir
        - Nomor HP Ketua Takmir
        - Nama Sekretaris (jika ada)
        - Nama Bendahara (jika ada)

        3. INFORMASI FISIK MASJID
        - Luas Tanah (m²)
        - Luas Bangunan (m²)
        - Kapasitas Jamaah (orang)
        - Tahun Berdiri
        - Status Kepemilikan (milik sendiri/sewa/hak pakai)

        4. FASILITAS MASJID
        - Wudhu (ada/tidak)
        - Parkir (ada/tidak, kapasitas berapa)
        - Toilet (ada/tidak)
        - Sarana Ibadah Tambahan (kamar jenazah, dapur, dll)

        Catatan: Semua data yang ditandai wajib harus diisi dengan lengkap dan benar.
        Data akan diverifikasi oleh tim emasjid.id sebelum akun diaktifkan.
        """
    },
    {
        "type": "document",
        "title": "SOP Penggunaan Sistem Chatbot",
        "content": """
        STANDAR OPERASIONAL PROSEDUR (SOP)
        PENGGUNAAN SISTEM CHATBOT EMASJID.ID

        1. TUJUAN
        Sistem chatbot ini bertujuan untuk memberikan informasi cepat dan akurat
        kepada pengguna mengenai layanan emasjid.id.

        2. FITUR CHATBOT
        - Menjawab pertanyaan umum tentang emasjid.id
        - Membantu proses pendaftaran
        - Memberikan informasi harga dan paket
        - Mengarahkan ke customer service jika diperlukan

        3. BATASAN CHATBOT
        Chatbot tidak dapat:
        - Memproses pembayaran
        - Mengubah data akun tanpa verifikasi
        - Memberikan informasi rahasia atau pribadi
        - Menangani keluhan kompleks

        4. PROTOKOL ESCALATION
        Jika chatbot tidak dapat menjawab pertanyaan:
        - Arahkan pengguna ke customer service
        - Berikan nomor kontak yang dapat dihubungi
        - Catat pertanyaan yang tidak terjawab untuk improvement

        5. PEMELIHARAAN
        - Update knowledge base minimal 1 bulan sekali
        - Monitor pertanyaan yang sering ditanyakan
        - Tambahkan jawaban untuk pertanyaan baru
        """
    }
]

def load_from_json(filepath: str) -> List[Dict[str, Any]]:
    """Load knowledge data from a JSON file."""
    if not os.path.exists(filepath):
        print(f"⚠️ JSON file not found at {filepath}. Skipping.")
        return []

    data = []
    try:
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            print(f"⚠️ JSON file not found or empty at {filepath}. Skipping.")
            return []
        with open(filepath, 'r', encoding='utf-8') as f:
            records = json.load(f)
            for row in records:
                data.append({
                    "type": "qa",
                    "question": row.get("pertanyaan", ""),
                    "answer": row.get("jawaban", ""),
                    "kategori": row.get("kategori", "Umum")
                })
    except json.JSONDecodeError as e:
        print(f"❌ Error reading from JSON: {e}")
    return data

def seed_knowledge_base(data_source=None):
    """Seed the knowledge base with initial data"""
    if vector_db_service is None:
        print("\n❌ ERROR KRITIS: Koneksi ke Vector Database (Qdrant) gagal!")
        print("💡 PENYEBAB: Folder database sedang dikunci oleh program lain.")
        print("💡 SOLUSI: Matikan dulu server FastAPI (tekan Ctrl+C pada terminal uvicorn),")
        print("   lalu jalankan ulang script ini.\n")
        return 0, 0
        
    data_to_seed = data_source if data_source is not None else KNOWLEDGE_DATA
    print("🌱 Starting knowledge base seeding...")
    print(f"📊 Found {len(data_to_seed)} knowledge items to process")

    success_count = 0
    error_count = 0

    for i, item in enumerate(data_to_seed, 1):
        try:
            print(f"\n🔄 Processing item {i}/{len(data_to_seed)}: {item.get('question', item.get('title', 'Unknown'))}")

            if item["type"] == "qa":
                # Store Q&A as searchable content
                content = f"Pertanyaan: {item['question']}\nJawaban: {item['answer']}"
                doc_id = vector_db_service.upsert_document(
                    content=content,
                    metadata={
                        "type": "qa",
                        "question": item["question"],
                        "source": item.get("source", "seed_data"),
                        "kategori": item.get("kategori", "Umum")
                    }
                )

            elif item["type"] == "document":
                # Store document content (will be chunked automatically)
                doc_id = vector_db_service.upsert_document(
                    content=item["content"],
                    metadata={
                        "type": "document",
                        "title": item["title"],
                        "source": "seed_data"
                    }
                )

            if doc_id:
                print(f"✅ Successfully stored (ID: {doc_id})")
                success_count += 1
            else:
                print("❌ Failed to store (returned None)")
                error_count += 1

        except Exception as e:
            print(f"❌ Error processing item {i}: {str(e)}")
            error_count += 1

    print("\n🎉 Seeding completed!")
    print(f"✅ Successful: {success_count}")
    print(f"❌ Failed: {error_count}")
    print(f"📈 Success rate: {(success_count / len(KNOWLEDGE_DATA)) * 100:.1f}%")

    return success_count, error_count

def test_knowledge_base():
    """Test the seeded knowledge base with sample queries"""
    print("\n🧪 Testing knowledge base...")

    test_queries = [
        "Apa itu emasjid.id?",
        "Bagaimana cara daftar?",
        "Form pendataan masjid",
        "Biaya berapa?",
        "SOP chatbot"
    ]

    for query in test_queries:
        try:
            results = vector_db_service.search(query, limit=2)
            print(f"\n🔍 Query: '{query}'")
            print(f"📄 Found {len(results)} relevant documents")

            if results:
                for i, result in enumerate(results[:2], 1):
                    content_preview = result["content"][:100] + "..." if len(result["content"]) > 100 else result["content"]
                    print(f"  {i}. {content_preview}")

        except Exception as e:
            print(f"❌ Error testing query '{query}': {str(e)}")

def main():
    """Main function"""
    print("🚀 Knowledge Base Seeder for Chatbot")
    print("=" * 50)

    try:
        # 1. Default: Gunakan data KNOWLEDGE_DATA di dalam file ini
        hardcoded_data = KNOWLEDGE_DATA

        # 2. Load data dari file JSON sementara
        json_path = os.path.join(os.path.dirname(__file__), "data_kategori_sementara.json")
        json_data = load_from_json(json_path)
        print(f"🔍 Found {len(json_data)} items from JSON file.")
        data_to_seed = hardcoded_data + json_data

        # Seed the knowledge base
        success_count, error_count = seed_knowledge_base(data_to_seed)

        if success_count > 0:
            # Test the seeded data
            test_knowledge_base()

            print("\n🎊 Knowledge base seeding completed successfully!")
            print("💡 You can now test the chatbot with questions about emasjid.id")
        else:
            print("\n❌ No data was successfully seeded. Please check the errors above.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️  Seeding interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()