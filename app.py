import spacy
from flask import Flask, request, jsonify, render_template, session
from markupsafe import escape
import random
import os
import secrets
import json
import traceback
import re
from spacy.matcher import PhraseMatcher # <-- Import yang benar
import time # <-- Jangan lupa import time

# --- KONFIGURASI APLIKASI ---
# Pastikan direktori ini relatif terhadap lokasi script ini
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "intent_model_ft_v2")
DATA_DIR = os.path.join(BASE_DIR, 'data')

CONFIDENCE_THRESHOLD = 0.5

# Placeholder Links (GANTI DENGAN LINK AKTUAL!)
# Pastikan link ini valid dan bisa diakses
# LINK_JADWAL_TI kini menjadi kurang penting jika data JSON tersedia, tapi simpan sbg fallback
LINK_JADWAL_TI = "[Gdrive Jadwal TI]" # Contoh jika sudah diganti
LINK_JADWAL_SIPIL = "[GANTI LINK JADWAL SIPIL]"
LINK_JADWAL_TAMBANG = "[GANTI LINK JADWAL TAMBANG]"
LINK_JADWAL_UMUM_FT = "[GANTI LINK UMUM FT JIKA ADA]"
LINK_PRODI_SIPIL = "https://teknik.unanda.ac.id/teknik-sipil" # Contoh jika sudah diganti
LINK_PRODI_INFORMATIKA = "https://teknik.unanda.ac.id/teknik-informatika" # Contoh jika sudah diganti
LINK_PRODI_TAMBANG = "https://teknik.unanda.ac.id/teknik-pertambangan" # Contoh jika sudah diganti
KONTAK_TU_INFO = "Anda bisa menghubungi Tata Usaha (TU) Fakultas Teknik di Gedung FT Lantai [2], Ruangan Akademik. Atau cek kontak resmi di website fakultas." # << GANTI INFO KONTAK LENGKAP & AKURAT

# --- Inisialisasi Aplikasi Flask ---
app = Flask(__name__)
# SANGAT PENTING: Ganti dengan kunci rahasia yang kuat dan simpan di environment variable untuk production!
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'ganti-ini-dengan-kunci-rahasia-acak-yang-aman-' + secrets.token_hex(16))

# --- Helper Functions for Loading Data ---
def load_json_data(filename):
    """Memuat data dari file JSON di folder data."""
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"INFO: Data '{filename}' berhasil dimuat.")
            return data
    except FileNotFoundError:
        print(f"ERROR: File data '{filepath}' tidak ditemukan.")
        return {} # Kembalikan dictionary kosong agar tidak crash
    except json.JSONDecodeError as e:
        print(f"ERROR: File data '{filepath}' bukan JSON yang valid. Kesalahan: {e}")
        return {}
    except Exception as e:
        print(f"ERROR: Terjadi kesalahan lain saat memuat '{filepath}': {e}")
        traceback.print_exc() # Cetak traceback untuk debug
        return {}

def load_text_data(filename):
    """Memuat data dari file teks di folder data."""
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            print(f"INFO: Teks '{filename}' berhasil dimuat.")
            return content
    except FileNotFoundError:
        print(f"ERROR: File teks '{filepath}' tidak ditemukan.")
        return f"Konten panduan '{os.path.basename(filepath)}' tidak ditemukan." # Pesan lebih spesifik
    except Exception as e:
        print(f"ERROR: Terjadi kesalahan saat memuat '{filepath}': {e}")
        traceback.print_exc() # Cetak traceback untuk debug
        return f"Terjadi kesalahan saat memuat panduan '{os.path.basename(filepath)}'."

# --- Muat Semua Data Eksternal ---
print("\n--- Memuat Data Eksternal ---")
# Pastikan nama file ini sesuai dengan yang Anda buat di folder 'data'
FT_FEES = load_json_data('ft_fees.json')
PMB_INFO = load_json_data('pmb_info.json')
LEARNING_CONTENT = load_json_data('learning_content.json')
SPP_DATA = load_json_data('spp_data.json')
TERMS_DATA = load_json_data('terms.json')
JADWAL_TI_DATA = load_json_data('jadwal_ti.json') # <<<--- TAMBAHKAN PEMUATAN DATA JADWAL TI
KRS_SEVIMA_GUIDE = load_text_data('krs_guide.txt')
PAYMENT_SEVIMA_TOKOPEDIA_GUIDE = load_text_data('payment_guide.txt')


# Ekstrak terms setelah data dimuat
PRODI_TERMS = TERMS_DATA.get('prodi', {})
LAB_TERMS = TERMS_DATA.get('lab', {})
print("--- Selesai Memuat Data Eksternal ---\n")

# --- Helper function format Rupiah ---
def format_idr(amount):
    """Memformat angka menjadi string Rupiah."""
    if amount is None or amount == "N/A": return "Informasi belum tersedia"
    try:
        # Pastikan amount adalah angka sebelum format
        numeric_amount = float(amount)
        return f"Rp {numeric_amount:,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        # Jika konversi gagal, kembalikan apa adanya (mungkin sudah string)
        print(f"WARNING: Gagal memformat '{amount}' sebagai Rupiah.")
        return str(amount)

# --- Memuat Model spaCy & Inisialisasi Matcher ---
# (Kode ini tidak berubah)
nlp = None # Inisialisasi nlp
matcher = None # Inisialisasi matcher
entity_details = {}

try:
    if not os.path.exists(MODEL_DIR):
         raise OSError(f"Direktori model '{MODEL_DIR}' tidak ditemukan.")
    nlp = spacy.load(MODEL_DIR)
    print(f"INFO: Model spaCy '{MODEL_DIR}' berhasil dimuat.")
    matcher = PhraseMatcher(nlp.vocab, attr='LOWER') # Inisialisasi di sini

    # Tambahkan Pola PRODI
    if PRODI_TERMS:
        added_prodi_count = 0
        for canonical, variations in PRODI_TERMS.items():
            if not isinstance(variations, list):
                print(f"WARNING: Variasi untuk PRODI '{canonical}' bukan list, dilewati.")
                continue
            patterns = [nlp.make_doc(text) for text in variations if isinstance(text, str)]
            if patterns:
                match_id = f"PRODI_{canonical.replace(' ', '_').replace('&', 'and').upper()}" # ID unik & aman
                matcher.add(match_id, patterns)
                entity_details[match_id] = {"label": "PRODI", "canonical": canonical}
                added_prodi_count += 1
        print(f"INFO: Menambahkan {added_prodi_count} pola PRODI ke PhraseMatcher.")
    else:
        print("WARNING: PRODI_TERMS kosong atau gagal dimuat. Deteksi prodi rules tidak aktif.")

    # Tambahkan Pola LAB
    if LAB_TERMS:
        added_lab_count = 0
        for canonical, variations in LAB_TERMS.items():
            if not isinstance(variations, list):
                 print(f"WARNING: Variasi untuk LAB '{canonical}' bukan list, dilewati.")
                 continue
            patterns = [nlp.make_doc(text) for text in variations if isinstance(text, str)]
            if patterns:
                # ID lebih aman, handle karakter non-alphanumeric
                safe_canonical = re.sub(r'\W+', '_', canonical)
                match_id = f"LAB_{safe_canonical.upper()}"
                matcher.add(match_id, patterns)
                entity_details[match_id] = {"label": "LAB", "canonical": canonical}
                added_lab_count += 1
        print(f"INFO: Menambahkan {added_lab_count} pola LAB ke PhraseMatcher.")

    else:
         print("WARNING: LAB_TERMS kosong atau gagal dimuat. Deteksi lab rules tidak aktif.")

    if matcher:
         print(f"INFO: PhraseMatcher diinisialisasi dengan total {len(matcher)} pola.")
    else:
         print("WARNING: PhraseMatcher tidak berhasil diinisialisasi.")


except OSError as e:
    print(f"FATAL ERROR: Tidak dapat memuat model spaCy dari '{MODEL_DIR}'. {e}")
    print("Pastikan direktori model ada dan berisi model spaCy yang valid.")
    print("Aplikasi tidak bisa berjalan tanpa model.")
    exit(1) # Keluar jika model gagal dimuat
except Exception as e:
    print(f"FATAL ERROR lain saat memuat model spaCy atau inisialisasi Matcher: {e}")
    traceback.print_exc()
    exit(1) # Keluar jika ada error kritis lain

# --- Helper Functions Lanjutan ---
# (Fungsi extract_model_person_name, process_nlu, _get_spp_response tidak berubah)
def extract_model_person_name(doc):
    """Mengekstrak entitas PERSON pertama dari Doc spaCy."""
    if not doc or not doc.ents: return None
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            # Filter nama yang terlalu umum atau pendek
            name_text = ent.text.strip()
            if len(name_text) > 2 and name_text.lower() not in ["bapak", "ibu", "mas", "mbak", "kak", "pak", "bu"]:
                 return name_text
    return None

def process_nlu(text):
    """Memproses teks input menggunakan spaCy (Intent & NER) dan PhraseMatcher (PRODI/LAB)."""
    # Normalisasi input sebelum diproses
    normalized_text = text.lower().strip()

    if not nlp or not matcher: # Cek jika nlp atau matcher gagal load di awal
        print("ERROR: Model NLP atau Matcher tidak tersedia untuk NLU.")
        # Kembalikan struktur default agar tidak error di pemanggilan
        return {"doc": None, "intent": None, "score": 0.0, "entities": {"PERSON": None, "PRODI": [], "LAB": []}}

    try:
        doc = nlp(normalized_text) # Proses teks yang sudah dinormalisasi
        intents = doc.cats
        top_intent = max(intents, key=intents.get) if intents else None
        top_score = intents.get(top_intent, 0.0) if top_intent else 0.0

        ner_person = extract_model_person_name(doc)

        matches = matcher(doc)
        detected_prodi_list = []
        detected_lab_list = []
        found_prodi_can = set()
        found_lab_can = set()

        # Urutkan matches berdasarkan posisi awal untuk prioritas jika tumpang tindih
        sorted_matches = sorted(matches, key=lambda m: m[1])

        for match_id_hash, start, end in sorted_matches:
            string_id = nlp.vocab.strings[match_id_hash] # Dapatkan ID string dari hash
            if string_id in entity_details:
                details = entity_details[string_id]
                label = details["label"]
                canonical = details["canonical"]
                span_text = doc[start:end].text # Teks yang cocok

                # Hindari duplikasi canonical form
                if label == "PRODI" and canonical not in found_prodi_can:
                     # Optional: Cek jika span overlap dengan entitas lain jika perlu
                     detected_prodi_list.append(canonical)
                     found_prodi_can.add(canonical)
                     # print(f"DEBUG Matcher: Found PRODI '{canonical}' from text '{span_text}'")
                elif label == "LAB" and canonical not in found_lab_can:
                     detected_lab_list.append(canonical)
                     found_lab_can.add(canonical)
                     # print(f"DEBUG Matcher: Found LAB '{canonical}' from text '{span_text}'")

        return {
            "doc": doc,
            "intent": top_intent,
            "score": top_score,
            "entities": {
                "PERSON": ner_person,
                "PRODI": detected_prodi_list,
                "LAB": detected_lab_list
            }
        }
    except Exception as e:
         print(f"ERROR saat NLU processing untuk teks: '{text}'. Kesalahan: {e}")
         traceback.print_exc()
         return {"doc": None, "intent": None, "score": 0.0, "entities": {"PERSON": None, "PRODI": [], "LAB": []}}


def _get_spp_response(user_input_text, detected_prodi_canonical, user_name):
    """Membuat respons spesifik untuk pertanyaan SPP/UKT."""
    text = user_input_text.lower()
    response = ""
    periode_terdeteksi = None
    # Perbaiki keyword agar lebih akurat
    keywords_lama = ["angkatan 2018", "angkatan 2019", "angkatan 2020", "angkatan 2021", "angkatan 2022", "spp lama", "spp dulu"]
    keywords_baru = ["angkatan 2023", "angkatan 2024", "spp terbaru", "spp sekarang", "spp saat ini", "biaya berlaku"]

    # Cek periode dengan lebih hati-hati
    if any(k in text for k in keywords_lama):
        periode_terdeteksi = "2018-2022"
    # Cek baru *setelah* cek lama untuk prioritas jika ada keduanya (meski aneh)
    elif any(k in text for k in keywords_baru):
        periode_terdeteksi = "2023-2024"

    prodi_terdeteksi = detected_prodi_canonical # Gunakan hasil NLU
    sapaan = f"Baik {escape(user_name)}" if user_name else "Baik" # Escape nama di sini

    if not SPP_DATA:
        return f"Maaf {escape(user_name) if user_name else ''}, data SPP tidak dapat dimuat saat ini. Mohon coba lagi nanti atau hubungi TU." # Escape nama

    # Jika prodi terdeteksi dan ada datanya
    if prodi_terdeteksi and prodi_terdeteksi in SPP_DATA:
        spp_prodi = SPP_DATA[prodi_terdeteksi]
        # Default ke periode terbaru jika tidak terdeteksi spesifik
        target_periode = periode_terdeteksi if periode_terdeteksi else "2023-2024"
        amount = spp_prodi.get(target_periode)

        if amount is not None:
            response = f"{sapaan}, biaya SPP/UKT untuk prodi **{prodi_terdeteksi}** periode **{target_periode}** adalah **{format_idr(amount)}** per semester."
            # Tambahkan konteks jika periode default digunakan
            if not periode_terdeteksi and target_periode == "2023-2024":
                response += " (Ini adalah biaya SPP yang berlaku saat ini)."
            # Tambahkan info jika periode lama diminta tapi ada yang baru
            elif periode_terdeteksi == "2018-2022" and "2023-2024" in spp_prodi:
                 amount_baru = spp_prodi.get("2023-2024")
                 if amount_baru:
                     response += f"\nSebagai info, biaya SPP terbaru (periode 2023-2024) untuk prodi ini adalah {format_idr(amount_baru)} per semester."

        else: # Data periode spesifik tidak ada
            response = f"Maaf {escape(user_name) if user_name else ''}, saya tidak memiliki data SPP untuk prodi **{prodi_terdeteksi}** pada periode **{target_periode}**. "
            # Coba berikan info periode terbaru jika tersedia
            spp_terbaru = spp_prodi.get("2023-2024")
            if spp_terbaru is not None:
                response += f"Biaya SPP yang berlaku saat ini (periode 2023-2024) untuk **{prodi_terdeteksi}** adalah **{format_idr(spp_terbaru)}** per semester."
            else:
                response += f"Informasi SPP terbaru untuk **{prodi_terdeteksi}** juga belum tersedia di data saya."
    # Jika prodi tidak terdeteksi atau datanya tidak ada
    else:
        # Berikan ringkasan umum jika data SPP ada
        response = f"{sapaan}, "
        if prodi_terdeteksi and prodi_terdeteksi not in SPP_DATA:
             response += f"mohon maaf, data SPP spesifik untuk prodi '{prodi_terdeteksi}' belum tersedia. "

        response += "Berikut adalah ringkasan biaya SPP (UKT) per semester Fakultas Teknik yang berlaku saat ini (periode 2023-2024):\n"
        found_any = False
        for prodi, data in SPP_DATA.items():
            spp_terbaru = data.get("2023-2024")
            if spp_terbaru is not None:
                # Gunakan list agar format lebih rapi
                response += f"\n- **{prodi}**: {format_idr(spp_terbaru)}"
                found_any = True

        if not found_any:
            response = f"Maaf {escape(user_name) if user_name else ''}, saya belum memiliki informasi detail biaya SPP saat ini. Silakan hubungi bagian akademik/keuangan."
        elif not prodi_terdeteksi: # Tambahkan ajakan jika tidak ada prodi terdeteksi
             response += f"\n\nSebutkan nama prodi jika Anda ingin info yang lebih spesifik."

    return response.strip()

# <<<--- FUNGSI BARU UNTUK MENCARI DAN MEMFORMAT JADWAL TI --->>>
def _get_jadwal_ti_response(original_text_lower, sapaan):
    """
    Mencari dan memformat jadwal TI dari JADWAL_TI_DATA berdasarkan input pengguna.
    """
    if not JADWAL_TI_DATA or "jadwal_kuliah" not in JADWAL_TI_DATA or "TI" not in JADWAL_TI_DATA["jadwal_kuliah"]:
        return (f"Maaf {sapaan}, data jadwal kuliah Teknik Informatika tidak dapat dimuat atau kosong saat ini. "
                f"Anda bisa cek link ini sebagai alternatif: {LINK_JADWAL_TI}" if LINK_JADWAL_TI and "[GANTI" not in LINK_JADWAL_TI else
                "Silakan cek pengumuman resmi dari prodi.")

    # Asumsi periode, bisa dibuat lebih dinamis jika data punya banyak periode
    periode = "2024-2025"
    schedule_data = JADWAL_TI_DATA["jadwal_kuliah"]["TI"].get(periode)

    if not schedule_data:
        return (f"Maaf {sapaan}, data jadwal kuliah Teknik Informatika untuk periode {periode} belum tersedia di data saya. "
                f"Coba cek link ini: {LINK_JADWAL_TI}" if LINK_JADWAL_TI and "[GANTI" not in LINK_JADWAL_TI else
                "Silakan cek pengumuman resmi dari prodi.")

    found_schedule = []
    search_term = None # Untuk menyimpan matkul atau hari yang dicari

    # 1. Cek apakah user mencari mata kuliah spesifik
    # Buat daftar nama matkul untuk pencocokan
    course_names = [name.lower() for name in schedule_data.keys()]
    matched_course = None
    for course_name_lower in course_names:
        # Cari nama matkul dalam teks input (butuh penyesuaian agar lebih akurat)
        if course_name_lower in original_text_lower:
             # Cari nama matkul asli (dengan kapitalisasi)
             for real_name, details in schedule_data.items():
                 if real_name.lower() == course_name_lower:
                     matched_course = real_name
                     search_term = matched_course # Simpan nama matkul yang cocok
                     found_schedule.append((real_name, details))
                     break # Ambil yang pertama cocok
             if matched_course: break # Hentikan pencarian matkul

    # 2. Jika tidak mencari matkul, cek apakah mencari hari spesifik
    if not found_schedule:
        days_map = {"senin": "Senin", "selasa": "Selasa", "rabu": "Rabu",
                    "kamis": "Kamis", "jumat": "Jumat", "sabtu": "Sabtu"}
        matched_day_key = None
        for day_key, day_proper in days_map.items():
            # Cari keyword hari + "hari" (misal "hari senin") atau hanya nama hari
            if f"hari {day_key}" in original_text_lower or (day_key in original_text_lower.split() and "hari" in original_text_lower):
                matched_day_key = day_key
                search_term = f"Hari {day_proper}" # Simpan hari yang cocok
                break
            # Opsi: cari hanya nama hari jika input pendek
            elif len(original_text_lower.split()) <= 3 and day_key in original_text_lower.split():
                 matched_day_key = day_key
                 search_term = f"Hari {day_proper}"
                 break

        if matched_day_key:
            day_proper_case = days_map[matched_day_key]
            for course_name, details in schedule_data.items():
                if details.get("hari", "").lower() == day_proper_case.lower():
                    found_schedule.append((course_name, details))
            # Urutkan berdasarkan jam mulai jika ditemukan untuk hari
            found_schedule.sort(key=lambda item: item[1].get("jam", "99:99"))

    # 3. Buat Teks Respons
    response_parts = []
    if found_schedule:
        if search_term:
            response_parts.append(f"Berikut jadwal yang saya temukan untuk **{search_term}** (Periode {periode}):\n")
        else: # Seharusnya tidak terjadi jika found_schedule True, tapi sbg fallback
             response_parts.append(f"Berikut jadwal yang relevan (Periode {periode}):\n")

        for course_name, details in found_schedule:
            jam = details.get("jam", "N/A")
            ruang = details.get("ruang", "N/A")
            dosen = details.get("dosen", "N/A")
            hari = details.get("hari", "N/A")
            semester = details.get("semester", "N/A")
            kelas = details.get("kelas", "N/A")

            # Format berbeda jika mencari matkul vs hari
            if matched_course: # Jika fokus pada 1 matkul
                 response_parts.append(f"- **{course_name}**:")
                 response_parts.append(f"  - Hari/Jam: {hari}, {jam}")
                 response_parts.append(f"  - Ruang: {ruang}")
                 response_parts.append(f"  - Dosen: {dosen}")
                 response_parts.append(f"  - Kelas/Semester: {kelas} / Sem {semester}")
            else: # Jika menampilkan daftar untuk satu hari
                 response_parts.append(f"- **{course_name}** ({jam}) di R.{ruang} - Dosen: {dosen} (Kelas: {kelas} / Sem: {semester})")

        response_parts.append("\n*Jadwal dapat berubah, selalu konfirmasi ke prodi/dosen.*")

    # Jika tidak ada yang cocok (tidak cari matkul/hari spesifik ATAU tidak ditemukan)
    else:
        response_parts.append(f"Saya bisa bantu cek jadwal kuliah **Teknik Informatika** untuk periode {periode}.")
        # Berikan opsi atau link umum
        response_parts.append("Apakah Anda ingin tahu jadwal untuk:\n"
                            "- **Mata kuliah spesifik?** (Contoh: 'jadwal metode numerik')\n"
                            "- **Hari tertentu?** (Contoh: 'jadwal kuliah hari senin')")
        if LINK_JADWAL_TI and "[GANTI" not in LINK_JADWAL_TI:
            response_parts.append(f"\nAtau Anda bisa cek link jadwal lengkap (jika tersedia) di sini: {LINK_JADWAL_TI}")
        else:
             response_parts.append("\nSilakan cek juga pengumuman resmi dari prodi untuk jadwal lengkap.")

    return "\n".join(response_parts)
# <<<--- AKHIR FUNGSI BARU --->>>


def generate_intent_response(nlu_result, user_name, original_text=""):
    """
    Menghasilkan teks respons berdasarkan intent yang terdeteksi.
    Mengembalikan tuple: (response_text, final_intent_category)
    """
    intent = nlu_result['intent']
    score = nlu_result['score'] # Ambil skor untuk referensi jika perlu
    entities = nlu_result['entities']
    detected_prodi_list = entities.get("PRODI", [])
    detected_lab_list = entities.get("LAB", [])
    # Ambil yang pertama terdeteksi (mungkin perlu logika lebih kompleks jika ada > 1)
    detected_prodi = detected_prodi_list[0] if detected_prodi_list else None
    detected_lab = detected_lab_list[0] if detected_lab_list else None
    safe_user_name = escape(user_name) if user_name else None
    # Gunakan sapaan yang lebih konsisten
    sapaan_untuk_user = f"{safe_user_name}, " if safe_user_name else "" # Nama sudah di-escape
    sapaan_awal_kalimat = f"Baik {safe_user_name}" if safe_user_name else "Baik" # Untuk awal kalimat


    # Default response jika tidak ada handler intent yang cocok
    response_text = f"Maaf {sapaan_untuk_user}saya belum bisa memproses permintaan terkait '{intent}' saat ini. Mungkin bisa coba tanyakan dengan cara lain?"
    final_intent_category = intent if intent else "unhandled_intent" # Kategori awal

    # --- Logika Respons per Intent ---
    # Pastikan menggunakan sapaan yang tepat, konstanta link, dan cek ketersediaan data eksternal

    if intent == "greeting_ft":
        # Respon sapaan bervariasi tergantung ada nama atau tidak
        if safe_user_name:
             response_text = random.choice([
                 f"Halo lagi {safe_user_name}! Ada lagi yang bisa saya bantu?",
                 f"Hai {safe_user_name}! Senang bertemu Anda lagi.",
                 f"Ya {safe_user_name}, ada keperluan apa lagi?"
             ])
        else:
            response_text = random.choice([
                "Halo! Ada yang bisa saya bantu?",
                "Hai! Selamat datang di chatbot Fakultas Teknik UNANDA.",
                "Salam! Ada yang ingin ditanyakan seputar Fakultas Teknik?"
            ])

    elif intent == "goodbye_ft":
        response_text = random.choice([
            f"{sapaan_awal_kalimat}, sampai jumpa!", # Gunakan sapaan awal kalimat
            "Sampai jumpa!",
            "Senang bisa membantu. Jika ada lagi, jangan ragu bertanya.",
            "Terima kasih telah bertanya!"
            ])

    elif intent == "thankyou_ft":
        response_text = random.choice([
            f"Sama-sama, {safe_user_name}!" if safe_user_name else "Sama-sama!",
            "Dengan senang hati!",
            "Tidak masalah!",
            "Senang bisa membantu!"
            ])

    elif intent == "ask_bot_identity":
         response_text = ("Saya adalah chatbot Fakultas Teknik Universitas Andi Djemma. "
                          "Saya dirancang untuk membantu memberikan informasi seputar fakultas, "
                          "Penerimaan Mahasiswa Baru (PMB), biaya kuliah (SPP, praktikum), "
                          "informasi prodi & lab, jadwal kuliah (termasuk detail jadwal TI), panduan KRS dan pembayaran, serta kontak. " # <--- Sebutkan jadwal TI
                          "Ada yang bisa saya bantu?")

    elif intent == "info_biaya_umum":
        # Intent ini harusnya mengarahkan user untuk lebih spesifik
        final_intent_category = "disambiguate_cost"
        response_text = (f"Tentu {sapaan_untuk_user}. Saya bisa bantu informasi biaya di Fakultas Teknik. "
                         "Jenis biaya apa yang spesifik Anda maksud?\n\n"
                         "1. **SPP/UKT** (Biaya kuliah per semester)\n"
                         "2. **Praktikum/Laboratorium** (Biaya kegiatan di lab)\n"
                         "3. **Pendaftaran Mahasiswa Baru (PMB)** (Biaya formulir, tes, orientasi awal, dll.)\n\n"
                         "Silakan sebutkan jenisnya (misal: 'info SPP', 'biaya praktikum', atau 'biaya PMB').")

    elif intent == "info_spp_ft":
        # Panggil fungsi helper khusus SPP
        response_text = _get_spp_response(original_text, detected_prodi, safe_user_name)

    elif intent == "cara_bayar_spp_ft":
         # Arahkan ke panduan spesifik atau info umum
         response_text = (f"{sapaan_untuk_user}Untuk pembayaran SPP/UKT (setelah Anda resmi menjadi mahasiswa), "
                          "biasanya dilakukan melalui sistem akademik online Sevima/SIAKAD Cloud. "
                          "Apakah Anda ingin tahu:\n"
                          "1. **Panduan bayar via Tokopedia** (jika tersedia)?\n"
                          "2. **Informasi metode pembayaran lain** (misal transfer bank)?\n"
                          "3. **Batas waktu pembayaran** semester ini?\n\n"
                          "Mohon konfirmasi ke bagian keuangan atau cek pengumuman resmi fakultas/universitas "
                          "untuk detail metode pembayaran yang valid dan jadwalnya.")
         # Jika panduan Tokopedia ada, tawarkan langsung
         if PAYMENT_SEVIMA_TOKOPEDIA_GUIDE and "tidak ditemukan" not in PAYMENT_SEVIMA_TOKOPEDIA_GUIDE:
             response_text += "\n\nJika ingin panduan pembayaran via Tokopedia, ketik 'cara bayar sevima tokopedia'."

    elif intent == "cara_bayar_sevima_tokopedia":
         if PAYMENT_SEVIMA_TOKOPEDIA_GUIDE and "tidak ditemukan" not in PAYMENT_SEVIMA_TOKOPEDIA_GUIDE:
              response_text = (f"{sapaan_awal_kalimat}, ini panduan umum membayar uang kuliah melalui Sevima Pay " # Ganti sapaan
                               f"di platform Tokopedia:\n\n{PAYMENT_SEVIMA_TOKOPEDIA_GUIDE}\n\n"
                               "**Penting:** Pastikan Anda mengikuti langkah-langkah ini dengan benar, "
                               "memilih tagihan yang sesuai, dan membayar sebelum batas waktu yang ditentukan. "
                               "Simpan bukti pembayaran Anda.")
         else:
             response_text = (f"Maaf {sapaan_untuk_user}, panduan spesifik pembayaran via Tokopedia belum tersedia di data saya. "
                              "Silakan cek pengumuman resmi dari bagian keuangan atau universitas mengenai metode pembayaran yang tersedia.")

    elif intent == "info_krs_sevima":
         if KRS_SEVIMA_GUIDE and "tidak ditemukan" not in KRS_SEVIMA_GUIDE:
              response_text = (f"{sapaan_awal_kalimat}, berikut panduan umum pengisian Kartu Rencana Studi (KRS) " # Ganti sapaan
                               f"di sistem Sevima/SIAKAD Cloud:\n\n{KRS_SEVIMA_GUIDE}\n\n"
                               "**Ingat:** Selalu perhatikan **jadwal resmi pengisian KRS** yang dikeluarkan oleh fakultas/universitas. "
                               "Jika ada mata kuliah yang tidak muncul, error, atau Anda ragu, segera konsultasikan "
                               "dengan **Dosen Pembimbing Akademik (PA)** Anda atau bagian akademik.")
         else:
             response_text = (f"Maaf {sapaan_untuk_user}, panduan pengisian KRS via Sevima belum tersedia di data saya. "
                              "Secara umum, Anda perlu login ke sistem SIAKAD/Sevima pada jadwal yang ditentukan, "
                              "memilih mata kuliah yang akan diambil sesuai dengan semester dan kurikulum Anda, "
                              "lalu menyimpannya. Pastikan status KRS Anda disetujui oleh Dosen PA. "
                              "Untuk panduan detail, silakan cek sumber informasi resmi dari kampus.")

    # <<<--- MODIFIKASI HANDLER JADWAL KULIAH --->>>
    elif intent == "jadwal_kuliah_ft":
        # Jika prodi terdeteksi adalah TI, coba gunakan data JSON
        if detected_prodi == "Teknik Informatika":
            response_text = _get_jadwal_ti_response(original_text.lower(), sapaan_untuk_user)
        # Jika prodi lain terdeteksi atau tidak ada prodi terdeteksi
        else:
            base_response = f"Untuk jadwal kuliah Fakultas Teknik semester ini, {sapaan_untuk_user}berikut link yang mungkin relevan:\n"
            links_found = []
            # Tampilkan link prodi yang terdeteksi (selain TI karena sudah ditangani di atas)
            if detected_prodi == "Teknik Sipil" and LINK_JADWAL_SIPIL and "[GANTI" not in LINK_JADWAL_SIPIL: links_found.append(f"- **Teknik Sipil**: {LINK_JADWAL_SIPIL}")
            if detected_prodi == "Teknik Pertambangan" and LINK_JADWAL_TAMBANG and "[GANTI" not in LINK_JADWAL_TAMBANG: links_found.append(f"- **Teknik Pertambangan**: {LINK_JADWAL_TAMBANG}")

            # Jika tidak ada prodi spesifik terdeteksi ATAU link prodi spesifik tidak ada, tampilkan semua link (termasuk TI sbg fallback)
            if not detected_prodi or not links_found:
                if LINK_JADWAL_TI and "[GANTI" not in LINK_JADWAL_TI: links_found.append(f"- **Teknik Informatika**: {LINK_JADWAL_TI} (atau tanya saya detailnya)") # Info tambahan
                if LINK_JADWAL_SIPIL and "[GANTI" not in LINK_JADWAL_SIPIL: links_found.append(f"- **Teknik Sipil**: {LINK_JADWAL_SIPIL}")
                if LINK_JADWAL_TAMBANG and "[GANTI" not in LINK_JADWAL_TAMBANG: links_found.append(f"- **Teknik Pertambangan**: {LINK_JADWAL_TAMBANG}")
                if LINK_JADWAL_UMUM_FT and "[GANTI" not in LINK_JADWAL_UMUM_FT: links_found.append(f"- **Umum Fakultas**: {LINK_JADWAL_UMUM_FT}")

            if links_found:
                response_text = base_response + "\n".join(links_found)
                response_text += "\n\nJadwal biasanya dibagikan oleh masing-masing prodi atau koordinator mata kuliah. Anda juga bisa cek pengumuman di grup mahasiswa atau sistem Sevima/SIAKAD."
                # Jika user bertanya umum dan data TI ada, beri tahu bisa tanya detail
                if not detected_prodi and JADWAL_TI_DATA:
                    response_text += "\nUntuk **Teknik Informatika**, saya bisa bantu cek jadwal mata kuliah atau hari tertentu jika Anda bertanya lebih spesifik (misal: 'jadwal metode numerik' atau 'jadwal hari senin')."
            else: # Jika tidak ada link sama sekali
                response_text = (f"Maaf {sapaan_untuk_user}, saya belum memiliki link jadwal kuliah yang bisa dibagikan saat ini. "
                                 "Silakan cek pengumuman resmi dari prodi Anda, grup mahasiswa, atau sistem Sevima/SIAKAD. "
                                 "Jadwal biasanya keluar mendekati awal semester.")
            # Tambahkan catatan jika prodi terdeteksi (selain TI) tapi linknya tidak ada
            if detected_prodi and detected_prodi != "Teknik Informatika" and not any(detected_prodi in link_text for link_text in links_found) and links_found:
                response_text += f"\n(Link spesifik untuk {detected_prodi} belum saya temukan, tapi Anda bisa cek link umum di atas)."
    # <<<--- AKHIR MODIFIKASI HANDLER JADWAL KULIAH --->>>


    elif intent == "fasilitas_umum_ft":
        response_text = (f"{sapaan_untuk_user}Fasilitas umum yang tersedia di lingkungan Fakultas Teknik UNANDA antara lain:\n"
                         "- Ruang kuliah yang dilengkapi AC dan LCD Proyektor.\n"
                         "- Jaringan WiFi di beberapa area kampus.\n"
                         "- Perpustakaan fakultas/universitas.\n"
                         "- Laboratorium komputer dan laboratorium spesifik per prodi.\n"
                         "- Area diskusi mahasiswa.\n"
                         "- Kantin atau area jajan terdekat.\n"
                         "- Mushola/Tempat ibadah.\n"
                         "- Toilet.\n\n"
                         "Untuk detail fasilitas laboratorium spesifik prodi, Anda bisa tanyakan misalnya 'info lab informatika'.")

    # (Handler Info Lab, Info Prodi, Biaya Praktikum, Kontak, PMB, Pembelajaran tidak berubah signifikan, hanya penyesuaian sapaan)
    # Gabungkan handler Info Lab menjadi satu blok logis
    elif intent.startswith("info_lab_") or (detected_lab and intent not in ["tanya_pembelajaran_lab", "tanya_biaya_praktikum"]):
        target_prodi_from_intent = None
        if intent == "info_lab_sipil": target_prodi_from_intent = "Teknik Sipil"
        elif intent == "info_lab_informatika": target_prodi_from_intent = "Teknik Informatika"
        elif intent == "info_lab_pertambangan": target_prodi_from_intent = "Teknik Pertambangan"

        # Prioritaskan prodi dari NLU jika ada, baru dari intent
        target_prodi = detected_prodi or target_prodi_from_intent

        response_parts = [f"{sapaan_awal_kalimat}. Mengenai laboratorium di Fakultas Teknik:"] # Ganti sapaan

        # Cek ketersediaan data yang relevan
        has_learning_data = bool(LEARNING_CONTENT)
        has_fee_data = bool(FT_FEES and "praktikum" in FT_FEES)

        if not has_learning_data and not has_fee_data:
             response_parts.append("Maaf, informasi detail mengenai laboratorium (materi atau biaya) tidak dapat dimuat saat ini.")
        else:
            # Jika ada target prodi (dari NLU atau intent)
            if target_prodi:
                response_parts.append(f"\n**Untuk Prodi {target_prodi}:**")
                labs_in_prodi = []
                if has_learning_data and target_prodi in LEARNING_CONTENT:
                    # Ambil nama lab dari kunci di learning content, kecuali _prodi_summary
                    labs_in_prodi = [lab for lab in LEARNING_CONTENT[target_prodi] if not lab.startswith("_")]

                # Jika user menyebut lab spesifik DAN lab itu ada di prodi target
                if detected_lab and detected_lab in labs_in_prodi:
                    response_parts.append(f"- Fokus pada: **{detected_lab}**.")
                    # Tambahkan info biaya jika ada
                    if has_fee_data:
                         fee_info = FT_FEES["praktikum"].get(detected_lab, FT_FEES["praktikum"].get("_default"))
                         if fee_info:
                             biaya_partisipasi = fee_info.get('amount')
                             biaya_ujian = fee_info.get('ujian_akhir_praktikum_amount')
                             notes = fee_info.get('notes', '')
                             biaya_text = f"  Biaya partisipasi sekitar {format_idr(biaya_partisipasi)}"
                             if biaya_ujian is not None:
                                 biaya_text += f" + {format_idr(biaya_ujian)} (ujian akhir)."
                             else: biaya_text += "."
                             response_parts.append(biaya_text)
                             if notes: response_parts.append(f"  Catatan: {notes}")
                         else: response_parts.append("  Informasi biaya spesifik lab ini belum tersedia.")
                    # Tambahkan ajakan tanya materi
                    if has_learning_data and detected_lab in LEARNING_CONTENT[target_prodi]:
                        response_parts.append(f"  Anda bisa tanya 'apa yang dipelajari di {detected_lab}?'")
                # Jika user tidak menyebut lab spesifik TAPI ada daftar lab di prodi target
                elif labs_in_prodi:
                    response_parts.append(f"  Terdapat beberapa laboratorium utama, antara lain: **{', '.join(labs_in_prodi)}**.")
                    # Berikan info biaya default jika ada
                    if has_fee_data:
                         fee_info = FT_FEES["praktikum"].get("_default")
                         if fee_info:
                             biaya_partisipasi = fee_info.get('amount')
                             biaya_ujian = fee_info.get('ujian_akhir_praktikum_amount')
                             notes = fee_info.get('notes', '')
                             biaya_text = f"  Biaya praktikum umumnya sekitar {format_idr(biaya_partisipasi)}"
                             if biaya_ujian is not None:
                                 biaya_text += f" + {format_idr(biaya_ujian)} (ujian akhir)."
                             else: biaya_text += "."
                             response_parts.append(biaya_text)
                             if notes: response_parts.append(f"  Catatan umum: {notes}")
                         else: response_parts.append("  Informasi biaya praktikum umum belum tersedia.")
                    response_parts.append("  Anda bisa tanya info lebih detail tentang lab spesifik (misal: 'info lab jaringan komputer' atau 'biaya lab hidrolika').")
                # Jika tidak ada daftar lab di prodi target
                else:
                    response_parts.append(f"  Maaf, daftar laboratorium spesifik untuk Prodi {target_prodi} belum tersedia di data saya.")
            # Jika tidak ada target prodi (user tanya umum 'info lab')
            else:
                all_labs = list(LAB_TERMS.keys()) # Ambil dari terms sebagai fallback list
                if all_labs:
                   response_parts.append("\nFakultas Teknik memiliki berbagai laboratorium untuk mendukung pembelajaran.")
                   # Sebutkan beberapa contoh jika daftarnya panjang
                   if len(all_labs) > 5:
                        response_parts.append(f"Beberapa di antaranya seperti: **{', '.join(random.sample(all_labs, 5))}**...")
                   else:
                        response_parts.append(f"Antara lain: **{', '.join(all_labs)}**.")
                   # Tambahkan info biaya default jika ada
                   if has_fee_data:
                        fee_info = FT_FEES["praktikum"].get("_default")
                        if fee_info:
                             biaya_partisipasi = fee_info.get('amount')
                             biaya_ujian = fee_info.get('ujian_akhir_praktikum_amount')
                             notes = fee_info.get('notes', '')
                             biaya_text = f"\nBiaya praktikum umumnya sekitar {format_idr(biaya_partisipasi)}"
                             if biaya_ujian is not None:
                                 biaya_text += f" + {format_idr(biaya_ujian)} (ujian akhir)."
                             else: biaya_text += "."
                             response_parts.append(biaya_text)
                             if notes: response_parts.append(f"Catatan umum: {notes}")
                   response_parts.append("\nApakah ada laboratorium spesifik atau dari prodi tertentu yang ingin Anda ketahui lebih lanjut?")
                else:
                   response_parts.append("\nMaaf, informasi umum mengenai laboratorium belum tersedia saat ini.")

        response_text = "\n".join(response_parts)


    # Gabungkan handler Info Prodi
    elif intent.startswith("info_prodi_"):
        target_prodi = None
        if intent == "info_prodi_sipil": target_prodi = "Teknik Sipil"
        elif intent == "info_prodi_informatika": target_prodi = "Teknik Informatika"
        elif intent == "info_prodi_pertambangan": target_prodi = "Teknik Pertambangan"

        # Prioritaskan NLU jika ada
        target_prodi = detected_prodi or target_prodi

        # Siapkan data link dan info singkat (bisa juga dari JSON)
        prodi_links = {
             "Teknik Sipil": LINK_PRODI_SIPIL,
             "Teknik Informatika": LINK_PRODI_INFORMATIKA,
             "Teknik Pertambangan": LINK_PRODI_TAMBANG
        }
        prodi_general_info = {
             "Teknik Sipil": "Fokus pada perancangan, pembangunan, dan pemeliharaan infrastruktur seperti gedung, jembatan, jalan, dan sistem air.",
             "Teknik Informatika": "Mempelajari dasar-dasar ilmu komputer, pengembangan perangkat lunak (software), jaringan komputer, kecerdasan buatan, dan manajemen data.",
             "Teknik Pertambangan": "Berkaitan dengan eksplorasi, penambangan (ekstraksi), dan pengolahan sumber daya mineral dan batubara secara efisien dan aman."
        }

        if target_prodi and target_prodi in prodi_links:
            link = prodi_links[target_prodi]
            info = prodi_general_info.get(target_prodi, "")
            response_text = f"{sapaan_untuk_user}Berikut informasi umum mengenai **Prodi {target_prodi}**:\n"
            if info: response_text += f"\n- **Fokus Utama**: {info}\n"
            # Cek link valid sebelum ditampilkan
            if link and "[GANTI" not in link and "http" in link:
                response_text += f"- **Website/Info Akademik Lengkap**: {link}\n"
            else:
                 response_text += f"- Website Prodi: (Link belum tersedia)\n"

            # Tambahkan ajakan tanya pembelajaran jika datanya ada
            if LEARNING_CONTENT and target_prodi in LEARNING_CONTENT and "_prodi_summary" in LEARNING_CONTENT[target_prodi]:
                response_text += f"\nAnda juga bisa bertanya 'apa saja yang dipelajari di {target_prodi}?' untuk mendapatkan gambaran materi kuliahnya."
            # Tambahkan ajakan tanya SPP
            if SPP_DATA and target_prodi in SPP_DATA:
                 response_text += f"\nUntuk biaya kuliah, Anda bisa tanya 'berapa spp {target_prodi}?'."

        elif target_prodi: # Prodi disebut tapi tidak ada di data link/info
            response_text = f"{sapaan_untuk_user}Maaf, informasi umum untuk Prodi {target_prodi} belum tersedia lengkap di data saya. Anda bisa coba cek langsung di website Fakultas Teknik UNANDA."
        else: # User tanya 'info prodi' tanpa spesifik
            prodi_list = list(prodi_links.keys())
            if prodi_list:
                 response_text = f"{sapaan_untuk_user}Fakultas Teknik UNANDA saat ini memiliki program studi: **{', '.join(prodi_list)}**. Prodi mana yang spesifik ingin Anda ketahui informasinya?"
            else:
                 response_text = f"{sapaan_untuk_user}Maaf, daftar program studi di Fakultas Teknik belum tersedia di data saya."

    elif intent == "tanya_biaya_praktikum":
        if not FT_FEES or "praktikum" not in FT_FEES:
            response_text = f"Maaf {sapaan_untuk_user}, informasi biaya praktikum tidak dapat dimuat saat ini. Silakan hubungi laboratorium terkait atau bagian akademik."
        else:
            biaya_praktikum_info = FT_FEES["praktikum"]
            response_parts = [f"{sapaan_awal_kalimat}, terkait biaya praktikum di Fakultas Teknik:"] # Ganti sapaan
            info = None
            lab_specified = False
            default_info = biaya_praktikum_info.get("_default") # Ambil info default jika ada

            # Jika user menyebut lab spesifik
            if detected_lab:
                lab_name = detected_lab
                lab_specified = True
                # Cari info spesifik lab itu, fallback ke default jika tidak ada
                info = biaya_praktikum_info.get(lab_name, default_info)
                if lab_name in biaya_praktikum_info:
                    response_parts.append(f"\nUntuk praktikum **{lab_name}**:")
                elif default_info: # Info spesifik tidak ada, tapi default ada
                     response_parts.append(f"\nUntuk praktikum **{lab_name}** (menggunakan info biaya umum):")
                else: # Info spesifik dan default tidak ada
                     response_parts.append(f"\nMaaf, info biaya spesifik untuk **{lab_name}** belum tersedia.")
                     info = None # Pastikan info None
            # Jika user tidak menyebut lab spesifik, gunakan default
            elif default_info:
                info = default_info
                response_parts.append("\nSecara umum untuk praktikum di Fakultas Teknik:")
            # Jika tidak menyebut lab dan default juga tidak ada
            else:
                 response_parts.append("\nMaaf, informasi biaya praktikum umum belum tersedia.")
                 info = None # Pastikan info None

            # Jika ada info biaya yang bisa ditampilkan (spesifik atau default)
            if info:
                details = []
                biaya_partisipasi = info.get('amount')
                biaya_ujian = info.get('ujian_akhir_praktikum_amount')
                notes = info.get('notes', 'Biaya dapat berubah, mohon konfirmasi ke lab/akademik.') # Default note

                if biaya_partisipasi is not None:
                    details.append(f"- Biaya partisipasi/modul utama: **{format_idr(biaya_partisipasi)}**.")
                if biaya_ujian is not None:
                    details.append(f"- Biaya ujian akhir praktikum: **{format_idr(biaya_ujian)}**.")

                if details:
                    response_parts.extend(details)
                else: # Jika amount dan ujian_akhir tidak ada di data info
                    response_parts.append("Detail komponen biaya (partisipasi/ujian) belum tersedia.")

                response_parts.append(f"- Catatan: {notes}")

            # Tambahkan ajakan jika user belum spesifik
            if not lab_specified and default_info:
                 response_parts.append("\nJika Anda ingin tahu biaya lab lain, silakan sebutkan nama labnya (contoh: 'biaya lab software').")
            elif not lab_specified and not default_info and list(biaya_praktikum_info.keys()) != ['_default']:
                 response_parts.append("\nSebutkan nama lab spesifik jika Anda perlu info biayanya.")


            response_text = "\n".join(filter(None, response_parts)) # Gabungkan dan hilangkan baris kosong

    elif intent == "kontak_ft":
         # Pastikan KONTAK_TU_INFO sudah diganti
         if "[GANTI" in KONTAK_TU_INFO:
             response_text = (f"{sapaan_untuk_user}Informasi kontak Tata Usaha (TU) belum lengkap di data saya. "
                              "Anda bisa coba cek langsung di website resmi Fakultas Teknik UNANDA untuk informasi kontak terbaru.")
         else:
              response_text = f"{sapaan_untuk_user}{KONTAK_TU_INFO}"


    # --- Handler PMB (Penerimaan Mahasiswa Baru) ---
    elif intent == "info_pmb_umum":
        if not PMB_INFO:
            response_text = f"Maaf {sapaan_untuk_user}, informasi Penerimaan Mahasiswa Baru (PMB) tidak dapat dimuat saat ini. Silakan cek website resmi UNANDA."
        else:
            website = PMB_INFO.get('website', '')
            kontak = PMB_INFO.get('contact_person', '')
            response_text = "Informasi lengkap mengenai Penerimaan Mahasiswa Baru (PMB) UNANDA, termasuk untuk Fakultas Teknik, "
            if website and 'http' in website:
                 response_text += f"biasanya dapat diakses melalui website resmi PMB di: **{website}**\n\n"
            else:
                 response_text += "biasanya dapat diakses melalui website resmi PMB UNANDA.\n\n"

            response_text += ("Di sana Anda bisa menemukan informasi tentang:\n"
                              "- Jadwal pendaftaran\n"
                              "- Jalur seleksi yang tersedia\n"
                              "- Persyaratan pendaftaran\n"
                              "- Rincian biaya awal\n"
                              "- Alur dan prosedur pendaftaran online\n\n")

            if kontak:
                response_text += f"Jika ada pertanyaan lebih lanjut mengenai PMB, Anda juga bisa menghubungi kontak panitia PMB: **{kontak}**.\n\n"

            response_text += "Apakah ada informasi spesifik terkait PMB yang ingin Anda tanyakan kepada saya? (misalnya tentang jalur, biaya awal, atau cara daftar)"

    elif intent == "info_jalur_pmb":
        if not PMB_INFO or not PMB_INFO.get('jalur'):
             response_text = f"Maaf {sapaan_untuk_user}, informasi detail mengenai jalur pendaftaran PMB tidak dapat dimuat. Silakan cek website PMB resmi."
        else:
            response_parts = [f"{sapaan_awal_kalimat}, berikut adalah jalur pendaftaran yang umumnya tersedia (berdasarkan data terakhir):"] # Ganti sapaan
            jalur_data = PMB_INFO.get('jalur', {})
            website = PMB_INFO.get('website', '')
            if not jalur_data:
                 response_parts.append("- Informasi jalur pendaftaran belum tersedia.")
            else:
                for key, info in jalur_data.items():
                    name = info.get('name', key.replace('_', ' ').title()) # Nama default dari key
                    desc = info.get('description', 'Informasi detail belum tersedia.')
                    response_parts.append(f"\n- **{name}**: {desc}")

            response_parts.append("\n\n**Penting:** Persyaratan detail, kuota, dan jadwal spesifik untuk setiap jalur dapat berubah setiap tahun.")
            if website and 'http' in website:
                response_parts.append(f"Pastikan Anda selalu memeriksa informasi terbaru dan paling akurat di website PMB resmi: **{website}**")
            else:
                 response_parts.append("Pastikan Anda selalu memeriksa informasi terbaru dan paling akurat di website PMB resmi UNANDA.")
            response_text = "\n".join(response_parts)

    elif intent == "info_biaya_pmb":
        if not PMB_INFO or not PMB_INFO.get('fees'):
            response_text = f"Maaf {sapaan_untuk_user}, informasi rincian biaya awal PMB tidak dapat dimuat. Silakan cek website PMB resmi."
        else:
            response_parts = [f"{sapaan_awal_kalimat}, berikut adalah perkiraan komponen biaya awal yang terkait dengan Pendaftaran Mahasiswa Baru (berdasarkan data terakhir):"] # Ganti sapaan
            fees_data = PMB_INFO.get('fees', {})
            website = PMB_INFO.get('website', '')
            found_fee = False
            if not fees_data:
                 response_parts.append("- Rincian biaya pendaftaran belum tersedia.")
            else:
                for key, info in fees_data.items():
                    name = info.get('name', key.replace('_', ' ').title())
                    amount = info.get('amount')
                    notes = info.get('notes', '')

                    if amount is not None:
                        response_parts.append(f"\n- **{name}**: **{format_idr(amount)}**")
                        if notes: response_parts.append(f"  *({notes})*")
                        found_fee = True
                    # Handle jika amount tidak ada tapi ada nama/notes
                    elif name != key: # Hanya tampilkan jika ada nama eksplisit
                         response_parts.append(f"\n- **{name}**: Informasi biaya belum tersedia")
                         if notes: response_parts.append(f"  *({notes})*")


            if found_fee:
                response_parts.append("\n\n**Penting:**")
                response_parts.append("- Ini adalah **biaya awal** yang terkait pendaftaran dan mungkin kegiatan orientasi/pembekalan.")
                response_parts.append("- Biaya ini **umumnya belum termasuk** biaya SPP/UKT untuk semester pertama dan biaya variabel lainnya (seperti praktikum jika ada di semester 1).")
                response_parts.append("- Jumlah dan komponen biaya dapat berubah. Selalu konfirmasi rincian biaya terbaru.")

            if website and 'http' in website:
                response_parts.append(f"Cek rincian biaya resmi dan terbaru di website PMB: **{website}**")
            else:
                 response_parts.append("Cek rincian biaya resmi dan terbaru di website PMB UNANDA.")

            response_text = "\n".join(response_parts)

    elif intent == "cara_daftar_pmb":
        if not PMB_INFO or not PMB_INFO.get('general_steps'):
             response_text = f"Maaf {sapaan_untuk_user}, panduan umum langkah pendaftaran PMB tidak dapat dimuat. Silakan cek alur pendaftaran di website PMB resmi."
        else:
            response_parts = [f"Siap {safe_user_name}! Berikut adalah gambaran umum langkah-langkah mendaftar sebagai mahasiswa baru secara online (berdasarkan prosedur umum):"] # Ganti sapaan
            steps_data = PMB_INFO.get('general_steps', [])
            website = PMB_INFO.get('website', '')
            if not steps_data:
                 response_parts.append("- Langkah-langkah pendaftaran belum tersedia.")
            else:
                for i, step in enumerate(steps_data):
                    response_parts.append(f"{i+1}. {step}")

            response_parts.append("\n\n**Mohon Diperhatikan:**")
            response_parts.append("- Ini adalah alur umum, langkah spesifik mungkin sedikit berbeda tergantung jalur pendaftaran dan sistem yang digunakan.")
            response_parts.append("- Pastikan Anda membaca **semua petunjuk** dengan teliti di portal pendaftaran.")
            response_parts.append("- Siapkan **semua dokumen** yang diperlukan dalam format digital (scan/foto) sesuai persyaratan.")
            response_parts.append("- Perhatikan **jadwal dan batas waktu** setiap tahapan.")

            if website and 'http' in website:
                response_parts.append(f"\nUntuk panduan paling akurat dan memulai pendaftaran, kunjungi website PMB resmi: **{website}**")
            else:
                 response_parts.append("\nUntuk panduan paling akurat dan memulai pendaftaran, kunjungi website PMB resmi UNANDA.")
            response_text = "\n".join(response_parts)


    # --- Handler Tanya Pembelajaran ---
    elif intent == "tanya_pembelajaran_prodi":
        if not LEARNING_CONTENT:
            response_text = f"Maaf {sapaan_untuk_user}, informasi materi pembelajaran prodi tidak dapat dimuat saat ini."
        else:
            if detected_prodi:
                prodi_info = LEARNING_CONTENT.get(detected_prodi)
                # Cari deskripsi summary yang sudah disiapkan
                prodi_summary = prodi_info.get("_prodi_summary") if prodi_info else None

                if prodi_summary:
                    response_text = (f"Secara garis besar, di **Prodi {detected_prodi}**, mahasiswa akan mempelajari berbagai hal terkait bidangnya. "
                                     f"Berikut adalah ringkasan fokus pembelajarannya:\n\n{prodi_summary}\n\n"
                                     "Tentu saja ini gambaran umum. Mata kuliah spesifik akan dipelajari per semester sesuai kurikulum. "
                                     f"Anda bisa cek detail kurikulum di website prodi {detected_prodi} jika tersedia.")
                else:
                    # Fallback jika summary tidak ada, tapi data prodi ada
                    response_text = (f"Maaf {sapaan_untuk_user}, ringkasan materi pembelajaran untuk **Prodi {detected_prodi}** belum tersedia secara spesifik di data saya. "
                                     "Secara umum, prodi ini akan membahas topik-topik yang relevan dengan bidangnya. "
                                     f"Anda bisa mencari silabus atau kurikulum di website resmi Prodi {detected_prodi} untuk detail mata kuliah.")
            else: # Jika tidak ada prodi terdeteksi
                prodi_options = [prodi for prodi in LEARNING_CONTENT if not prodi.startswith("_")] # Ambil nama prodi dari data
                if prodi_options:
                    response_text = f"{sapaan_untuk_user}Anda ingin mengetahui gambaran pembelajaran di program studi mana? Pilihan yang tersedia di data saya: **{', '.join(prodi_options)}**."
                else:
                     response_text = f"{sapaan_untuk_user}Maaf, informasi pembelajaran untuk program studi belum tersedia di data saya."

    elif intent == "tanya_pembelajaran_lab":
        if not LEARNING_CONTENT:
             response_text = f"Maaf {sapaan_untuk_user}, informasi materi pembelajaran laboratorium tidak dapat dimuat saat ini."
        # Jika user tidak menyebutkan nama lab spesifik
        elif not detected_lab:
            all_labs_with_desc = []
            # Cek semua prodi dan lab di dalamnya yang punya deskripsi
            for prodi, content in LEARNING_CONTENT.items():
                 if isinstance(content, dict):
                      all_labs_with_desc.extend([lab for lab in content if not lab.startswith("_") and content[lab]])

            if all_labs_with_desc:
                # Ambil beberapa contoh unik
                contoh_lab = list(set(all_labs_with_desc))
                contoh_display = random.sample(contoh_lab, min(len(contoh_lab), 5))
                response_text = (f"{sapaan_untuk_user}Anda ingin tahu materi pembelajaran di laboratorium mana? "
                                 "Mohon sebutkan nama laboratorium spesifiknya. "
                                 f"Contohnya: 'apa yang dipelajari di {random.choice(contoh_display)}?'")
            else:
                response_text = (f"{sapaan_untuk_user}Anda ingin tahu materi pembelajaran di laboratorium mana? "
                                 "Mohon sebutkan nama laboratorium spesifiknya.")
        # Jika user menyebutkan nama lab
        else:
            possible_prodi_owners = []
            lab_description = None
            target_prodi_for_lab = None # Untuk menyimpan prodi tempat deskripsi ditemukan

            # Cari deskripsi lab di semua prodi
            for prodi, content in LEARNING_CONTENT.items():
                 # Pastikan content adalah dictionary dan lab ada di dalamnya
                if isinstance(content, dict) and detected_lab in content:
                    desc = content.get(detected_lab)
                    # Hanya catat jika ada deskripsi non-kosong
                    if desc and isinstance(desc, str) and desc.strip():
                        possible_prodi_owners.append(prodi)
                        # Prioritaskan jika prodi dari NLU cocok DAN deskripsi ditemukan
                        if detected_prodi and detected_prodi == prodi:
                            lab_description = desc
                            target_prodi_for_lab = prodi
                            break # Ditemukan kecocokan terbaik

                        # Jika belum ada kecocokan prodi NLU, simpan deskripsi pertama yang ditemukan
                        elif not lab_description:
                            lab_description = desc
                            target_prodi_for_lab = prodi
                            # Jangan break dulu, mungkin ada prodi NLU cocok nanti

            # Buat respons berdasarkan hasil pencarian
            if lab_description:
                 # Jika lab ditemukan di beberapa prodi & user tidak spesifik prodi
                 if len(possible_prodi_owners) > 1 and not detected_prodi:
                     response_text = (f"Laboratorium **{detected_lab}** relevan untuk beberapa prodi "
                                      f"(misalnya {', '.join(possible_prodi_owners)}).\n\n"
                                      f"Secara umum, di lab ini fokus pembelajarannya adalah:\n{lab_description}\n\n"
                                      f"Materi spesifik mungkin disesuaikan tergantung kebutuhan prodi.")
                 # Jika lab ditemukan (unik atau sesuai NLU prodi)
                 else:
                     prodi_konteks = f"(Prodi {target_prodi_for_lab})" if target_prodi_for_lab else ""
                     response_text = (f"Di laboratorium **{detected_lab}** {prodi_konteks}, "
                                      f"fokus materi pembelajaran dan praktikumnya meliputi:\n\n{lab_description}")

            # Jika lab terdeteksi tapi deskripsi tidak ditemukan di mana pun
            else:
                response_text = (f"Maaf {sapaan_untuk_user}, deskripsi detail mengenai apa yang dipelajari di laboratorium "
                                 f"**{detected_lab}** belum tersedia di data saya. "
                                 "Biasanya lab ini mendukung mata kuliah praktikum terkait.")

    else:
        # Intent dikenali oleh model (skor > threshold) tapi tidak ada handler spesifik di sini
        if score >= CONFIDENCE_THRESHOLD: # Cek lagi threshold untuk memastikan
             final_intent_category = "unhandled_valid_intent"
             response_text = (f"Saya mengerti Anda bertanya tentang '{intent}' ({score*100:.1f}%). "
                              f"Namun, saya belum memiliki informasi detail atau tindakan spesifik untuk topik tersebut saat ini. "
                              "Mungkin Anda bisa bertanya tentang topik lain seperti biaya, pendaftaran, jadwal, atau prodi?")
        # Jika intent tidak dikenali ATAU skor rendah (ini seharusnya sudah ditangani di /predict, tapi sbg fallback)
        else:
             final_intent_category = "fallback_low_confidence_or_unknown"
             response_text = f"Maaf {sapaan_untuk_user}, saya masih belum yakin memahami maksud Anda (topik: {intent}, keyakinan: {score*100:.1f}%). Bisa coba tanyakan dengan kalimat yang berbeda atau lebih spesifik?"


    # Kembalikan teks respons dan kategori intent final
    return response_text, final_intent_category


# --- Route Utama ---
# (Tidak berubah)
@app.route("/")
def index():
    """Menampilkan halaman utama chatbot."""
    return render_template("index.html")

# --- Route Prediksi Chat (Coordinator) ---
# (Tidak berubah signifikan, pastikan sapaan konsisten jika perlu)
@app.route("/predict", methods=["POST"])
def predict():
    """Menerima input teks, memproses NLU, dan mengembalikan jawaban."""
    final_intent_category = "unknown_flow" # Kategori debug akhir
    response_text = "Maaf, terjadi sedikit gangguan dalam memproses permintaan Anda." # Default response
    debug_info = {} # Akan diisi nanti
    start_time = time.time() # Ukur waktu proses

    try:
        # Validasi input JSON
        if not request.is_json:
            return jsonify({"error": "Request harus dalam format JSON", "debug_info": {}}), 400

        data = request.get_json()
        text = data.get("text")

        if not text or not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Input 'text' tidak boleh kosong!", "debug_info": {"user_text": text}}), 400

        # Sanitasi dasar input teks (opsional, tergantung kebutuhan)
        text = text.strip()
        if len(text) > 500: # Batasi panjang input
             return jsonify({"error": "Input terlalu panjang (maks 500 karakter)", "debug_info": {"user_text": text[:50] + "..."}}), 400

        user_name_from_session = session.get('user_name')
        safe_user_name = escape(user_name_from_session) if user_name_from_session else None
        # Definisikan sapaan yang akan digunakan di blok ini
        sapaan_session_basic = f"{safe_user_name}, " if safe_user_name else "" # Untuk tengah kalimat
        sapaan_session_awal = f"{safe_user_name}" if safe_user_name else "Anda" # Untuk awal, bisa disesuaikan


        # --- 1. Handle Special Cases (Salam Islami, dll.) ---
        text_lower_stripped = text.lower()
        # Pola regex yang lebih robust untuk salam
        salam_pattern = r"^\s*assalamu'?alaikum(\s*wr\.?\s*wb\.?)?\s*[\.!\?]?\s*$"
        if re.match(salam_pattern, text_lower_stripped):
            salam_responses = ["Wa'alaikumsalam!", "Wa'alaikumussalam.", "Wa'alaikumsalam warahmatullahi wabarakatuh."]
            answer = random.choice(salam_responses)
            if safe_user_name:
                 answer += f" Ada yang bisa saya bantu, {safe_user_name}?"
            else:
                 answer += " Ada yang bisa saya bantu?"
            final_intent_category = "greeting_islamic_handled"
            debug_info = {
                "user_text": text,
                "detected_intent": final_intent_category,
                "intent_score": 1.0, # Skor 1.0 karena rule-based
                "user_name_in_session": user_name_from_session,
                "top_intent_raw": None,
                "ner_person_model": None,
                "rule_extracted_name": None,
                "ner_prodi_rules": [],
                "ner_lab_rules": [],
            }
            end_time = time.time()
            debug_info["processing_time_ms"] = round((end_time - start_time) * 1000)
            return jsonify({ "answer": answer, "debug_info": debug_info })

        # --- 2. Proses NLU ---
        nlu_result = process_nlu(text) # Gunakan teks asli (NLU function akan handle lowercase)
        top_intent = nlu_result['intent']
        top_score = nlu_result['score']
        entities = nlu_result['entities']
        extracted_name_person_ner = entities.get("PERSON") # Hasil dari NER model
        detected_prodi_list = entities.get("PRODI", [])
        detected_lab_list = entities.get("LAB", [])

        # --- 3. Handle Interaksi Nama ---
        rule_extracted_name = None # Untuk debug jika nama diekstrak pakai rule

        # Kondisi user kemungkinan sedang *memberikan* nama:
        # 1. Intent 'provide_name' terdeteksi dengan confidence tinggi.
        # 2. ATAU Inputnya pendek (<= 5 kata), NER mendeteksi nama, DAN belum ada nama di sesi.
        is_short_input = len(text.split()) <= 5
        likely_providing_name = (top_intent == "provide_name" and top_score >= CONFIDENCE_THRESHOLD) or \
                                (is_short_input and extracted_name_person_ner is not None and not user_name_from_session and top_intent != 'goodbye_ft') # Jangan anggap "makasih pak budi" sbg pemberian nama

        # --- Alur Logika Utama ---

        # Kasus 1: Belum kenal nama & user TIDAK sedang memberi nama -> Minta nama
        if not user_name_from_session and not likely_providing_name:
            final_intent_category = "prompt_for_name"
            # Sesuaikan prompt tergantung apakah user sudah bertanya sesuatu atau baru mulai
            if top_intent and top_intent not in ["greeting_ft", "ask_bot_identity"] and top_score >= CONFIDENCE_THRESHOLD:
                 prompt_options = [
                     f"Tentu, saya coba bantu jawab. Tapi agar lebih akrab, boleh saya tahu nama Anda?",
                     f"Oke, sebelum masuk ke detailnya, Anda ingin dipanggil siapa?",
                     f"Siap! Untuk mempermudah komunikasi, boleh perkenalkan diri dulu?"
                 ]
            else: # Baru mulai atau hanya sapaan umum
                 prompt_options = [
                     "Halo! Selamat datang di chatbot FT UNANDA. Sebelum kita mulai, boleh saya tahu nama panggilan Anda?",
                     "Hai! Supaya lebih enak ngobrolnya, Anda nyaman dipanggil siapa?",
                     "Salam kenal! Saya chatbot FT UNANDA. Boleh tahu nama Anda?"
                 ]
            response_text = random.choice(prompt_options)

        # Kasus 2: User kemungkinan MEMBERIKAN nama (baik sudah kenal atau belum) -> Proses nama
        elif likely_providing_name:
            user_name_to_save = None
            name_source = "unknown" # Untuk debug

            # Prioritas 1: Gunakan hasil NER jika ada
            if extracted_name_person_ner:
                # Coba bersihkan dari sapaan umum di depan/belakang jika ada
                cleaned_name_ner = re.sub(r"^(nama|panggilan)\s+(saya|aku)\s+(adalah|yaitu)?\s*", "", extracted_name_person_ner, flags=re.IGNORECASE).strip(' .,?!')
                cleaned_name_ner = re.sub(r"\s*terima kasih$", "", cleaned_name_ner, flags=re.IGNORECASE).strip(' .,?!')
                if len(cleaned_name_ner) > 1 and len(cleaned_name_ner.split()) <= 5: # Validasi sederhana
                    user_name_to_save = cleaned_name_ner
                    name_source = "ner"

            # Prioritas 2: Jika NER gagal ATAU intent provide_name kuat, coba rule-based
            # Hanya jika belum dapat nama dari NER atau jika intent 'provide_name' sangat kuat
            if not user_name_to_save or (top_intent == "provide_name" and top_score > 0.8):
                # Pola untuk ekstraksi nama setelah kata kunci
                name_patterns = [
                    r"^(?:nama|panggilan)\s+(?:saya|aku)\s+(?:adalah|yaitu)?\s+(.+)", # nama saya adalah [nama]
                    r"^(?:saya|aku)\s+(?:adalah|yaitu)?\s+(.+)",                   # saya adalah [nama]
                    r"^panggil\s+(?:saya|aku)?\s+(.+)",                             # panggil saya [nama]
                ]
                potential_name_rule = None
                for pattern in name_patterns:
                     match = re.search(pattern, text, flags=re.IGNORECASE)
                     if match:
                         potential_name_rule = match.group(1).strip(' .,?!')
                         break # Ambil yang pertama cocok

                # Jika tidak cocok pola di atas, tapi input pendek dan intent kuat, anggap seluruh teks (setelah trigger) adalah nama
                if not potential_name_rule and is_short_input and top_intent == "provide_name":
                    potential_name_rule = re.sub(r"^(nama|panggilan|saya|aku|panggil)\s+", "", text, flags=re.IGNORECASE).strip(' .,?!')


                # Validasi nama hasil rule
                if potential_name_rule and len(potential_name_rule) > 1 and len(potential_name_rule.split()) <= 5 and potential_name_rule.lower() not in ["iya", "ya", "oke", "ok", "baik", "siap"]:
                    # Jika nama dari NER sudah ada tapi beda, mungkin prioritaskan rule jika intent provide_name kuat
                    if not user_name_to_save or (top_intent == "provide_name" and top_score >= CONFIDENCE_THRESHOLD):
                         user_name_to_save = potential_name_rule
                         name_source = "rule"
                         rule_extracted_name = user_name_to_save # Simpan untuk debug

            # Jika nama berhasil didapatkan (dari NER atau Rule) dan valid
            if user_name_to_save:
                 session['user_name'] = user_name_to_save.strip()
                 safe_user_name = escape(session['user_name']) # Update nama yg aman dipakai
                 # Update sapaan lagi setelah nama disimpan
                 sapaan_session_basic = f"{safe_user_name}, "
                 sapaan_session_awal = f"{safe_user_name}"

                 final_intent_category = "provide_name_handled"
                 response_text = random.choice([
                     f"Baik {safe_user_name}, senang berkenalan! Nama Anda sudah saya ingat. Ada yang bisa saya bantu selanjutnya?",
                     f"Oke {safe_user_name}, terima kasih informasinya! Sekarang, apa yang ingin Anda tanyakan tentang Fakultas Teknik?",
                     f"Siap {safe_user_name}! Silakan ajukan pertanyaan Anda."
                     ])
                 debug_info["name_extraction_source"] = name_source
            # Jika user sepertinya memberi nama TAPI gagal diekstrak
            else:
                final_intent_category = "provide_name_failed"
                response_text = random.choice([
                    "Hmm, sepertinya saya belum berhasil menangkap nama Anda dengan jelas. Bisa coba sebutkan nama panggilannya saja?",
                    "Maaf, saya agak kesulitan mengenali namanya. Bisa diulangi?",
                    "Oke, tapi nama yang saya tangkap sepertinya kurang pas. Bisa tolong sebutkan lagi nama Anda?"
                    ])

        # Kasus 3: Sudah kenal nama ATAU user tidak sedang memberi nama -> Proses intent utama
        else:
           # Cek apakah intent terdeteksi dengan confidence cukup tinggi
           if top_intent and top_score >= CONFIDENCE_THRESHOLD:
               # Panggil helper utama untuk generate respons berdasarkan intent
               response_text, final_intent_category = generate_intent_response(nlu_result, user_name_from_session, text)
           # Jika intent tidak jelas (skor rendah) -> Fallback
           else:
               final_intent_category = "fallback_low_confidence"
               # Berikan saran yang lebih kontekstual (gunakan sapaan yang sudah di-escape)
               fallback_options = [
                   (f"Maaf {sapaan_session_basic}saya kurang yakin memahami maksud Anda (topik: '{top_intent}'?, skor: {top_score:.2f}). "
                    "Bisa coba tanyakan tentang:\n"
                    "- Biaya kuliah (SPP/Praktikum)\n"
                    "- Pendaftaran mahasiswa baru (PMB)\n"
                    "- Informasi prodi atau laboratorium\n"
                    "- Jadwal kuliah (khususnya TI)\n" # Tambahkan hint jadwal TI
                    "- Panduan KRS atau cara pembayaran"),
                   f"Hmm {sapaan_session_basic}sepertinya saya belum mengerti sepenuhnya. Mungkin bisa dijelaskan dengan kata-kata lain?",
                   f"Maaf {sapaan_session_basic}bisa diperjelas lagi pertanyaannya mengenai Fakultas Teknik?",
               ]
               # Jika ada intent terdeteksi tapi skor rendah, gunakan fallback pertama
               if top_intent:
                    response_text = fallback_options[0]
               else: # Jika tidak ada intent sama sekali (jarang terjadi jika model ada)
                    response_text = random.choice(fallback_options[1:])

        # --- 5. Siapkan Debug Info & Kembalikan Respons ---
        # (Tidak berubah)
        debug_info = {
            "user_text": text,
            "final_intent_category": final_intent_category, # Kategori setelah semua logika
            "top_intent_raw_model": top_intent, # Intent mentah dari model
            "intent_score": round(top_score, 4),
            "entities_ner_model": {"PERSON": extracted_name_person_ner}, # Hanya NER dari model
            "entities_rules": { # Entitas dari PhraseMatcher
                "PRODI": detected_prodi_list,
                "LAB": detected_lab_list
            },
            "name_in_session_before": user_name_from_session, # Nama di sesi sebelum diproses
            "name_in_session_after": session.get('user_name'), # Nama di sesi setelah diproses
            "rule_extracted_name": rule_extracted_name, # Nama jika diekstrak rule
            "name_extraction_source": debug_info.get("name_extraction_source", None), # Sumber ekstraksi nama
            "confidence_threshold": CONFIDENCE_THRESHOLD,
            "likely_providing_name_flag": likely_providing_name,
        }
        end_time = time.time()
        debug_info["processing_time_ms"] = round((end_time - start_time) * 1000)

        # Return dalam format JSON
        return jsonify({"answer": response_text, "debug_info": debug_info})

    # --- Exception Handling ---
    # (Tidak berubah)
    except Exception as e:
        # Tangkap error tak terduga selama pemrosesan
        print(f"FATAL ERROR in /predict route: {e}")
        traceback.print_exc() # Cetak traceback lengkap ke log server

        # Berikan pesan error umum yang aman ke pengguna
        error_message = "Maaf, terjadi kendala teknis di sistem saya. Silakan coba beberapa saat lagi."
        # Coba tambahkan nama pengguna ke pesan error jika ada di sesi (dengan aman)
        try:
            user_name_in_session_on_error = session.get('user_name')
            if user_name_in_session_on_error:
                 error_message = f"Maaf {escape(user_name_in_session_on_error)}, terjadi kendala teknis di sistem saya. Silakan coba beberapa saat lagi."
        except Exception as session_e:
             print(f"Warning: Gagal mengakses session saat menangani error utama: {session_e}")
             # Abaikan jika error saat akses sesi dalam blok error handling

        # Siapkan debug info minimal untuk error
        error_debug_info = {
            "error_message": str(e),
            "user_text_on_error": data.get("text") if 'data' in locals() else "Input not parsed",
            "final_intent_category": "internal_server_error",
            "user_name_in_session_on_error": user_name_in_session_on_error if 'user_name_in_session_on_error' in locals() else "N/A",
        }
        end_time = time.time()
        error_debug_info["processing_time_ms"] = round((end_time - start_time) * 1000)


        # Kembalikan response error 500
        return jsonify({
            "answer": error_message,
            "error": "Internal Server Error",
            "debug_info": error_debug_info
        }), 500

# --- Route Lupa Nama ---
# (Tidak berubah)
@app.route("/forget_name", methods=["POST"])
def forget_name():
    """Menghapus nama pengguna dari sesi."""
    user_name = session.get('user_name')
    if user_name:
        safe_removed_name = escape(user_name)
        session.pop('user_name', None) # Hapus nama dari session
        # Periksa apakah berhasil dihapus
        if 'user_name' not in session:
            return jsonify({
                "status": "success",
                "message": f"Baik {safe_removed_name}, nama Anda sudah tidak saya simpan lagi. Kita mulai dari awal ya."
            })
        else:
             # Kasus aneh jika pop gagal (jarang terjadi)
             print("WARNING: Session pop 'user_name' tidak berhasil.")
             return jsonify({
                "status": "error",
                "message": "Maaf, terjadi sedikit masalah saat mencoba melupakan nama Anda."
            }), 500
    else:
        return jsonify({
            "status": "no_name",
            "message": "Tidak masalah, saya memang belum menyimpan nama Anda sebelumnya."
        })

# --- Jalankan Server ---
# (Tambahkan jadwal_ti.json ke status data)
if __name__ == "__main__":
    print("\n" + "="*60)
    print("      CHATBOT FAKULTAS TEKNIK SERVER (UNANDA)")
    print("="*60)
    print(f"[*] Base Directory : '{BASE_DIR}'")
    print(f"[*] Model Dimuat dari: '{MODEL_DIR}'")
    print(f"[*] Folder Data    : '{DATA_DIR}'")
    print(f"[*] Conf. Threshold: {CONFIDENCE_THRESHOLD}")
    print(f"[*] Mode Debug Flask: {app.debug}")
    secret_key_status = "Default (TIDAK AMAN!)" if 'ganti-ini-dengan-kunci-rahasia' in app.secret_key else "Custom/Env Var (Lebih Aman)"
    print(f"[*] Status Secret Key: {secret_key_status}")
    if 'ganti-ini-dengan-kunci-rahasia' in app.secret_key:
        print("    >> PERINGATAN: Gunakan kunci rahasia yang kuat dan unik untuk production!")
        print("    >> Set environment variable 'FLASK_SECRET_KEY'.")

    # Cek Ketersediaan Data Penting
    print("\n--- Status Data Eksternal ---")
    data_files = {
        'ft_fees.json': bool(FT_FEES),
        'pmb_info.json': bool(PMB_INFO),
        'learning_content.json': bool(LEARNING_CONTENT),
        'spp_data.json': bool(SPP_DATA),
        'terms.json': bool(TERMS_DATA),
        'jadwal_ti.json': bool(JADWAL_TI_DATA), # <<<--- TAMBAHKAN PENGECEKAN
        'krs_guide.txt': "tidak ditemukan" not in KRS_SEVIMA_GUIDE,
        'payment_guide.txt': "tidak ditemukan" not in PAYMENT_SEVIMA_TOKOPEDIA_GUIDE
    }
    for filename, loaded in data_files.items():
        status = "OK" if loaded else "MISSING/ERROR"
        print(f"[*] {filename.ljust(25)}: {status}")
    if not all(data_files.values()):
        print("    >> PERINGATAN: Beberapa file data penting tidak ditemukan atau gagal dimuat.")
        print("    >> Fitur chatbot yang bergantung pada data tersebut mungkin tidak berfungsi.")

    # Cek Ketersediaan Model & Matcher
    print("\n--- Status Model & Matcher ---")
    print(f"[*] Model spaCy ({os.path.basename(MODEL_DIR)}) : {'Loaded' if nlp else 'FAILED'}")
    print(f"[*] PhraseMatcher            : {'Initialized' if matcher else ('Not Initialized' if nlp else 'Skipped (Model Failed)')}")
    if matcher:
        print(f"    - Pola Prodi    : {len([k for k in entity_details if k.startswith('PRODI_')])}")
        print(f"    - Pola Lab      : {len([k for k in entity_details if k.startswith('LAB_')])}")

    if not nlp:
         print("\n" + "!"*20 + " ERROR KRITIS " + "!"*20)
         print("!! Model spaCy gagal dimuat. Chatbot tidak dapat berfungsi. !!")
         print("!! Periksa path '{MODEL_DIR}' dan integritas model. !!")
         print("!"*60)
         # Tidak perlu exit(1) di sini karena sudah di blok try-except loading model
    else:
        print("\n" + "!"*15 + " PERHATIAN PENTING " + "!"*15)
        print(">> Pastikan semua placeholder [GANTI ...] dalam kode sudah diisi.")
        print(">> Pastikan file data di folder 'data/' adalah versi terbaru & akurat.")
        print(">> Pastikan model spaCy dilatih dengan data yang relevan.")
        print("!"*60 + "\n")

        # Ganti debug=False untuk production
        # Gunakan host='0.0.0.0' agar bisa diakses dari luar container/jaringan lokal
        # Port bisa disesuaikan jika perlu
        app.run(debug=True, host='0.0.0.0', port=5000)

# --- END OF FILE app.py ---