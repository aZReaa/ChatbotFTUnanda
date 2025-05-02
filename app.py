# --- START OF CLEANED FILE app.py ---
import spacy
from flask import Flask, request, jsonify, render_template, session
from markupsafe import escape
import random
import os
import secrets
import json
import traceback
import re
from spacy.matcher import PhraseMatcher
import time

# --- Import Logic Handler ---
import intent_logic

# --- KONFIGURASI APLIKASI ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "intent_model_ft_v2")
DATA_DIR = os.path.join(BASE_DIR, 'data')

CONFIDENCE_THRESHOLD = 0.5
ENABLE_INTENT_DISAMBIGUATION = True
DISAMBIGUATION_MARGIN = 0.15
INTENT_DESCRIPTIONS = {
    "info_spp_ft": "Informasi biaya SPP (kuliah per semester)",
    "info_biaya_pmb": "Informasi biaya awal terkait pendaftaran mahasiswa baru (PMB)",
    "jadwal_kuliah_ft": "Informasi jadwal kuliah",
    "info_krs_sevima": "Panduan atau informasi pengisian KRS",
    "cara_bayar_spp_ft": "Cara umum pembayaran SPP/UKT",
    "cara_daftar_pmb": "Langkah-langkah pendaftaran mahasiswa baru",
    "info_prodi_informatika": "Informasi umum tentang Prodi Teknik Informatika",
    "info_prodi_sipil": "Informasi umum tentang Prodi Teknik Sipil",
    "info_prodi_pertambangan": "Informasi umum tentang Prodi Teknik Pertambangan",
    "tanya_biaya_praktikum": "Informasi biaya praktikum di laboratorium",
    "tanya_pembelajaran_prodi": "Gambaran materi yang dipelajari di suatu prodi",
    # Tambahkan deskripsi intent lain jika ada
}

PLACEHOLDER_CONFIG = {
    "LINK_JADWAL_TI": "[Ganti dengan Link Gdrive Jadwal TI Anda]", # PERLU DIGANTI
    "LINK_JADWAL_SIPIL": "[Ganti dengan Link Gdrive Jadwal Sipil Anda]", # PERLU DIGANTI
    "LINK_JADWAL_TAMBANG": "[Ganti dengan Link Gdrive Jadwal Tambang Anda]", # PERLU DIGANTI
    "LINK_JADWAL_UMUM_FT": "[Ganti dengan Link Gdrive Jadwal Umum FT Jika Ada]", # PERLU DIGANTI jika ada
    "LINK_PRODI_SIPIL": "https://teknik.unanda.ac.id/teknik-sipil", # Pastikan link ini benar
    "LINK_PRODI_INFORMATIKA": "https://teknik.unanda.ac.id/teknik-informatika", # Pastikan link ini benar
    "LINK_PRODI_TAMBANG": "https://teknik.unanda.ac.id/teknik-pertambangan", # Pastikan link ini benar
    "KONTAK_TU_INFO": "Anda bisa menghubungi Tata Usaha (TU) Fakultas Teknik di Gedung FT Lantai [2], Ruangan Akademik. Atau cek kontak resmi di website fakultas.", # PERLU DICEK/DIGANTI jika ada detail spesifik
    "CONFIDENCE_THRESHOLD": CONFIDENCE_THRESHOLD,
}

DOMAIN_KEYWORDS = set([
    "fakultas", "teknik", "unanda", "andi djemma", "informatika", "if", "ti",
    "sipil", "ts", "tambang", "pertambangan", "prodi", "jurusan",
    "lab", "laboratorium", "praktikum", "jadwal", "kuliah", "kelas", "dosen",
    "matkul", "mata kuliah", "spp", "ukt", "biaya", "harga", "tarif",
    "krs", "sevima", "siakad", "pmb", "daftar", "pendaftaran", "mahasiswa", "maba",
    "kampus", "akademik", "semester", "ujian", "skripsi", "gedung", "kontak",
    "tu", "tata usaha", "bayar", "pembayaran", "alur", "syarat", "prosedur",
    "fasilitas", "website", "link", "kurikulum", "silabus", "kaprodi", "dekan",
])
OOS_KEYWORDS = set([
    "cuaca", "resep", "masak", "film", "bioskop", "politik", "bola", "sepakbola",
    "musik", "lagu", "liburan", "jalan-jalan", "traveling", "saham", "investasi",
    "gempa", "berita", "koran", "covid", "corona", "rekomendasi", "resto", "cafe",
    "tempat makan", "peta", "lokasi", "arah", "jalan ke", "presiden", "gubernur",
    "pemilu", "artis", "gosip", "selebriti", "main", "game", "nonton", "anime",
    "ramalan", "horoskop", "mimpi", "agama", "cerpen", "puisi", "novel", "olahraga"
])
MIN_LEN_FOR_NO_DOMAIN_OOS = 4 # Minimal panjang input tanpa keyword domain untuk dianggap OOS potensial

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'ganti-ini-dengan-kunci-rahasia-acak-yang-aman-' + secrets.token_hex(16)) # PENTING: Ganti secret key ini di produksi

# --- Helper Functions for Loading Data ---
def load_json_data(filename):
    """Memuat data dari file JSON di DATA_DIR."""
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"INFO: Data '{filename}' berhasil dimuat.")
        return data
    except FileNotFoundError:
        print(f"ERROR: File data '{filepath}' tidak ditemukan.")
        return {}
    except json.JSONDecodeError as e:
        print(f"ERROR: File data '{filepath}' bukan JSON valid. Kesalahan: {e}")
        return {}
    except Exception as e:
        print(f"ERROR: Terjadi kesalahan lain saat memuat '{filepath}': {e}")
        traceback.print_exc()
        return {}

def load_text_data(filename):
    """Memuat data dari file teks di DATA_DIR."""
    filepath = os.path.join(DATA_DIR, filename)
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content_data = f.read()
        print(f"INFO: Teks '{filename}' berhasil dimuat.")
        return content_data
    except FileNotFoundError:
        error_msg = f"Konten panduan '{os.path.basename(filepath)}' tidak ditemukan."
        print(f"ERROR: File teks '{filepath}' tidak ditemukan.")
        return error_msg
    except Exception as e:
        error_msg = f"Terjadi kesalahan saat memuat panduan '{os.path.basename(filepath)}'."
        print(f"ERROR: Terjadi kesalahan saat memuat '{filepath}': {e}")
        traceback.print_exc()
        return error_msg


# --- Muat Semua Data Eksternal & Buat Config ---
print("\n--- Memuat Data Eksternal ---")
APP_CONFIG = {}
APP_CONFIG.update(PLACEHOLDER_CONFIG)
APP_CONFIG['FT_FEES'] = load_json_data('ft_fees.json')
APP_CONFIG['PMB_INFO'] = load_json_data('pmb_info.json')
APP_CONFIG['LEARNING_CONTENT'] = load_json_data('learning_content.json')
APP_CONFIG['SPP_DATA'] = load_json_data('spp_data.json')
APP_CONFIG['TERMS_DATA'] = load_json_data('terms.json')
APP_CONFIG['JADWAL_TI_DATA'] = load_json_data('jadwal_ti.json')
APP_CONFIG['JADWAL_SIPIL_DATA'] = load_json_data('jadwal_sipil.json') # <<<--- ADDED
APP_CONFIG['JADWAL_TAMBANG_DATA'] = load_json_data('jadwal_tambang.json') # <<<--- ADDED
APP_CONFIG['KRS_SEVIMA_GUIDE'] = load_text_data('krs_guide.txt')
APP_CONFIG['PAYMENT_SEVIMA_TOKOPEDIA_GUIDE'] = load_text_data('payment_guide.txt')

# Safely get TERMS data after loading for Matcher
TERMS_DATA = APP_CONFIG.get('TERMS_DATA', {})
PRODI_TERMS = TERMS_DATA.get('prodi', {})
LAB_TERMS = TERMS_DATA.get('lab', {})
print("--- Selesai Memuat Data Eksternal ---\n")

# --- Memuat Model spaCy & Inisialisasi Matcher ---
nlp = None
matcher = None
entity_details = {} # Initialize here, before the try block

try:
    print("--- Memuat Model NLP & Matcher ---")
    if not os.path.exists(MODEL_DIR):
        raise OSError(f"Direktori model '{MODEL_DIR}' tidak ditemukan.")
    nlp = spacy.load(MODEL_DIR)
    print(f"INFO: Model spaCy '{os.path.basename(MODEL_DIR)}' berhasil dimuat.")

    # Initialize PhraseMatcher with case-insensitive matching
    matcher = PhraseMatcher(nlp.vocab, attr='LOWER')
    added_prodi_count = 0
    if PRODI_TERMS and isinstance(PRODI_TERMS, dict):
        for canonical, variations in PRODI_TERMS.items():
            if not isinstance(variations, list): continue
            # Create patterns only for valid strings and non-empty variations
            patterns = [nlp.make_doc(text) for text in variations if isinstance(text, str) and text.strip()]
            if patterns:
                match_id = f"PRODI_{canonical.replace(' ', '_').replace('&', 'and').upper()}"
                # Add patterns to the matcher
                matcher.add(match_id, patterns)
                entity_details[match_id] = {"label": "PRODI", "canonical": canonical}
                added_prodi_count += len(patterns) # Count individual patterns added
        print(f"INFO: Menambahkan {added_prodi_count} pola PRODI dari {len(PRODI_TERMS)} kanonikal ke PhraseMatcher.")
    else:
        print("WARNING: PRODI_TERMS kosong atau tidak valid. Deteksi prodi rules tidak aktif.")

    added_lab_count = 0
    if LAB_TERMS and isinstance(LAB_TERMS, dict):
        for canonical, variations in LAB_TERMS.items():
            if not isinstance(variations, list): continue
            patterns = [nlp.make_doc(text) for text in variations if isinstance(text, str) and text.strip()]
            if patterns:
                safe_canonical = re.sub(r'\W+', '_', canonical) # Make key safer
                match_id = f"LAB_{safe_canonical.upper()}"
                matcher.add(match_id, patterns)
                entity_details[match_id] = {"label": "LAB", "canonical": canonical}
                added_lab_count += len(patterns) # Count individual patterns added
        print(f"INFO: Menambahkan {added_lab_count} pola LAB dari {len(LAB_TERMS)} kanonikal ke PhraseMatcher.")
    else:
        print("WARNING: LAB_TERMS kosong atau tidak valid. Deteksi lab rules tidak aktif.")

    if matcher and (added_prodi_count > 0 or added_lab_count > 0):
         print(f"INFO: PhraseMatcher diinisialisasi dengan total {len(matcher)} pola. Detail entitas: {len(entity_details)}")
    elif matcher:
         print(f"WARNING: PhraseMatcher diinisialisasi tetapi tidak ada pola yang ditambahkan dari TERMS_DATA.")
    else:
         print("WARNING: PhraseMatcher tidak berhasil diinisialisasi.")

except OSError as e:
    print(f"FATAL ERROR: Tidak dapat memuat model spaCy dari '{MODEL_DIR}'. {e}")
    # Disable NLU functionality
    nlp = None
    matcher = None
    entity_details = {}
except Exception as e:
    print(f"FATAL ERROR lain saat memuat model/matcher atau menginisialisasi matcher: {e}")
    traceback.print_exc()
    # Disable NLU functionality
    nlp = None
    matcher = None
    entity_details = {}
print("--- Selesai Memuat Model NLP & Matcher ---\n")


# --- Helper Functions Lanjutan ---
def extract_model_person_name(doc):
    """Ekstrak nama orang pertama yang terdeteksi oleh model NER spaCy."""
    if not doc or not doc.ents:
        return None
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            name_text = ent.text.strip()
            # Filter basic titles and pronouns, and names that are too short or long
            if 1 < len(name_text) <= 30 and len(name_text.split()) <= 5 and \
               name_text.lower() not in [
                "bapak", "ibu", "mas", "mbak", "kak", "pak", "bu",
                "nama", "panggilan", "saya", "aku", "ku", "admin", "bot", "chatbot"]:
                 # Further check to avoid capturing sentences like "nama saya Budi" as "saya Budi"
                 # by checking if common introductory phrases precede the extracted name.
                 # This is a heuristic and might not be perfect.
                 # Convert doc text slice to lower for comparison
                 doc_text_slice = doc.text[max(0, ent.start_char - 10):ent.end_char + 10].lower()
                 if not any(phrase in doc_text_slice for phrase in ["nama saya", "nama aku", "nama ku", "panggil saya", "panggil aku", "panggil ku"]):
                     return name_text
    return None

def process_nlu(text):
    """Proses teks input menggunakan model spaCy NLU dan PhraseMatcher."""
    normalized_text = text.lower().strip()

    # Check if NLU components are ready
    if not nlp:
        print("WARNING: NLP model not ready. Returning empty NLU result.")
        # Ensure the returned dictionary structure is consistent
        return {"doc": None, "intent": None, "score": 0.0, "entities": {"PERSON": None, "PRODI": [], "LAB": []}, "all_intents": {}}

    try:
        doc = nlp(normalized_text)
        intents = doc.cats
        top_intent = max(intents, key=intents.get) if intents else None
        top_score = intents.get(top_intent, 0.0) if top_intent else 0.0

        # Extract entities from model NER
        ner_person = extract_model_person_name(doc)

        # Extract entities using PhraseMatcher (rules) if matcher is initialized
        detected_prodi_list, detected_lab_list = [], []
        found_prodi_can, found_lab_can = set(), set() # Use sets to avoid duplicates
        if matcher and entity_details: # Only run matcher if it's initialized and has patterns loaded
            matches = matcher(doc)
            # Sort matches by start index to handle overlapping or nested matches more predictably
            sorted_matches = sorted(matches, key=lambda m: m[1])

            for match_id_hash, start, end in sorted_matches:
                string_id = nlp.vocab.strings[match_id_hash]
                details = entity_details.get(string_id) # Use .get() for safety
                if details:
                    label, canonical = details["label"], details["canonical"]
                    # Only add if the canonical form hasn't been added yet
                    if label == "PRODI" and canonical not in found_prodi_can:
                        # Validate that the span matches the original text segment after lowercasing
                        span_text = doc.text[start:end] # text is already lowercased
                        original_span_text = text[start:end].lower() # Get original text part lowercased
                        if span_text == original_span_text: # Basic check
                            detected_prodi_list.append(canonical)
                            found_prodi_can.add(canonical)
                        else:
                            print(f"DEBUG: Matcher span mismatch for PRODI '{span_text}' (original part: '{original_span_text}') at [{start}:{end}]. Skipping.")

                    elif label == "LAB" and canonical not in found_lab_can:
                        # Validate that the span matches the original text segment after lowercasing
                        span_text = doc.text[start:end]
                        original_span_text = text[start:end].lower()
                        if span_text == original_span_text: # Basic check
                            detected_lab_list.append(canonical)
                            found_lab_can.add(canonical)
                        else:
                             print(f"DEBUG: Matcher span mismatch for LAB '{span_text}' (original part: '{original_span_text}') at [{start}:{end}]. Skipping.")

                # else: WARNING already printed during matcher init if entity_details is incomplete

        # Ensure entities dictionary is fully populated even if no entities found
        entities_result = {"PERSON": ner_person, "PRODI": detected_prodi_list, "LAB": detected_lab_list}


        return {
            "doc": doc, # Keep doc for potential downstream use
            "intent": top_intent,
            "score": top_score,
            "entities": entities_result,
            "all_intents": intents # Return all scores for disambiguation
        }
    except Exception as e:
        print(f"ERROR saat NLU: '{text}'. Kesalahan: {e}")
        traceback.print_exc()
        # Return empty result but with the expected structure on error
        return {"doc": None, "intent": None, "score": 0.0, "entities": {"PERSON": None, "PRODI": [], "LAB": []}, "all_intents": {}}

# --- OOS Helper Function ---
def check_out_of_scope(text_lower, domain_kws, oos_kws, min_len_no_domain=5):
    """Cek apakah teks berada di luar cakupan domain berdasarkan keywords."""
    # 1. Cek keyword OOS eksplisit
    for keyword in oos_kws:
        # Gunakan word boundary (\b) untuk mencocokkan kata utuh
        if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
            print(f"DEBUG OOS: Keyword eksplisit '{keyword}' ditemukan.")
            return True, "explicit" # Pasti OOS

    # 2. Cek keberadaan keyword domain
    found_domain_keyword = False
    for keyword in domain_kws:
        if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
            found_domain_keyword = True
            break

    # 3. Logika OOS berdasarkan ketiadaan keyword domain (untuk input yang lebih panjang)
    # Abaikan input input yang sangat pendek (<=2 kata) tanpa keyword domain (mungkin salam generik non-islamic)
    if not found_domain_keyword and len(text_lower.split()) > 2 and len(text_lower.split()) >= min_len_no_domain:
         print(f"DEBUG OOS: Tidak ada keyword domain & panjang >= {min_len_no_domain}. Potensi OOS.")
         # Dianggap OOS jika tidak ada keyword domain DAN input cukup panjang
         return True, "potential_no_domain" # Mengaktifkan heuristic ini sedikit lebih agresif OOS
         # return False, "potential_no_domain_ignored" # Saat ini diabaikan

    # Jika ada keyword domain, pasti BUKAN OOS berdasarkan heuristic ini
    if found_domain_keyword:
        return False, "in_scope_domain_keyword_present"

    # Jika tidak ada keyword domain TAPI inputnya pendek (<= min_len_no_domain atau <= 2 kata)
    else: # (not found_domain_keyword and len(text_lower.split()) < min_len_no_domain) or (len(text_lower.split()) <= 2)
        return False, "in_scope_short_or_generic"

# --- Route Utama ---
@app.route("/")
def index():
    """Render halaman utama dan bersihkan state dialog."""
    # Bersihkan state dialog dan nama pengguna saat halaman di-load/reload
    if 'dialogue_state' in session:
        session.pop('dialogue_state', None)
        session.pop('clarification_options', None)
        session.pop('original_ambiguous_nlu', None)
        print("INFO: Dialogue state cleared on page load.")
    if 'user_name' in session:
         session.pop('user_name', None)
         print("INFO: User name cleared on page load.")

    return render_template("index.html")


# --- Route Prediksi Chat (Coordinator) ---
@app.route("/predict", methods=["POST"])
def predict():
    """Handle permintaan chat, proses NLU, state, OOS, dan panggil logic handler."""
    start_time = time.time()
    final_intent_category = "unknown_flow" # Default category
    response_text = "Maaf, terjadi sedikit gangguan dalam memproses permintaan Anda. Silakan coba lagi." # Default error response
    debug_info = {}

    # Inisialisasi variabel yang mungkin digunakan di berbagai alur atau debug info
    extracted_name_person_ner = None # <<<--- INI YANG DITAMBAHKAN UNTUK INISIALISASI
    rule_extracted_name = None
    name_source = "unknown"
    user_name_to_save = None
    response_generated_by_name_logic = False
    nlu_result = {"doc": None, "intent": None, "score": 0.0, "entities": {"PERSON": None, "PRODI": [], "LAB": []}, "all_intents": {}} # Inisialisasi nlu_result


    try:
        # --- Validasi Input ---
        if not request.is_json:
            return jsonify({"error": "Request JSON diperlukan", "debug_info": {}}), 400
        data = request.get_json()
        text = data.get("text")
        if not text or not isinstance(text, str) or not text.strip():
            return jsonify({"error": "Input 'text' tidak boleh kosong!", "debug_info": {"user_text": text}}), 400

        text = text.strip()
        if len(text) > 500: # Batasi panjang input
            return jsonify({"error": "Input terlalu panjang (maks 500 karakter)", "debug_info": {"user_text": text[:50] + "..."}}), 400

        text_lower_stripped = text.lower()
        user_name_from_session = session.get('user_name') # Ambil nama dari sesi (jika ada)

        # === BAGIAN 1: Cek State Klarifikasi Intent ===
        if session.get('dialogue_state') == 'awaiting_intent_clarification':
            print("INFO: Handling response to intent clarification request.")
            user_choice = text_lower_stripped
            options_map = session.get('clarification_options', {})
            original_nlu = session.get('original_ambiguous_nlu', None)
            original_user_text = original_nlu.get('user_text', 'N/A') if original_nlu else 'N/A'

            resolved_intent = None
            # Cari intent berdasarkan pilihan user (1, 2, dst.)
            # Periksa apakah pilihan user sesuai dengan nomor opsi yang diberikan
            if user_choice in options_map:
                 resolved_intent = options_map[user_choice]

            if resolved_intent and original_nlu:
                print(f"INFO: Intent disambiguated by user to: {resolved_intent}")
                # Buat NLU result baru dengan intent yang sudah pasti
                # Gunakan entitas dari NLU asli saat klarifikasi terjadi
                entities_from_original_nlu = original_nlu.get("entities", {"PERSON": None, "PRODI": [], "LAB": []})

                modified_nlu = {
                    "doc": original_nlu.get("doc"), # Pertahankan doc asli jika ada
                    "intent": resolved_intent,
                    "score": 1.0, # Anggap skor 1.0 karena user memilih
                    "entities": entities_from_original_nlu,
                    "all_intents": {resolved_intent: 1.0}, # Hanya intent yang dipilih dengan skor 1.0
                    "user_text": original_user_text # Simpan teks asli user
                }

                # Hapus state klarifikasi dari session
                session.pop('dialogue_state', None)
                session.pop('clarification_options', None)
                session.pop('original_ambiguous_nlu', None)

                # Panggil logic handler dengan NLU yang sudah dimodifikasi
                try:
                    response_text, final_intent_category = intent_logic.get_response_for_intent(
                        modified_nlu, user_name_from_session, original_user_text, APP_CONFIG
                    )
                except Exception as logic_err:
                     print(f"ERROR saat menjalankan intent logic post-clarification: {logic_err}")
                     traceback.print_exc()
                     safe_user_name_temp = escape(user_name_from_session) if user_name_from_session else None
                     sapaan_temp = f"{safe_user_name_temp}, " if safe_user_name_temp else ""
                     response_text = f"Maaf {sapaan_temp}terjadi kesalahan saat memproses permintaan Anda setelah klarifikasi."
                     final_intent_category = "handler_error_post_clarification"

                debug_info.update({
                    "user_text": text, "original_ambiguous_text": original_user_text,
                    "final_intent_category": final_intent_category, "resolved_intent": resolved_intent,
                    "clarification_successful": True, "user_name_in_session": user_name_from_session,
                    # Tambahkan entitas asli ke debug info klarifikasi
                    "entities_from_original_nlu": entities_from_original_nlu,
                })
            else:
                # Jika user tidak memilih opsi yang valid
                print(f"WARNING: Failed to parse user clarification choice: '{user_choice}'. Options offered: {options_map}")
                response_text = random.choice([
                    "Maaf, pilihan Anda tidak dikenali. Mohon pilih nomor opsi yang tersedia (misal: '1' atau '2').",
                    "Pilihan tidak valid. Silakan ketik nomor (1 atau 2) sesuai opsi yang Anda maksud.",
                    "Saya belum mengerti. Pilihan Anda seharusnya berupa angka dari daftar yang saya berikan."
                ])
                final_intent_category = "clarification_failed_reprompt"
                # Pertahankan state klarifikasi agar user bisa mencoba lagi
                debug_info = {
                    "user_text": text, "final_intent_category": final_intent_category,
                    "clarification_successful": False, "user_name_in_session": user_name_from_session,
                    "clarification_options_offered": options_map,
                }

            end_time = time.time()
            debug_info["processing_time_ms"] = round((end_time - start_time) * 1000)
            return jsonify({"answer": response_text, "debug_info": debug_info})
        # === END BAGIAN 1 ===

        # === BAGIAN 2: Proses Input BARU (Tidak dalam state klarifikasi) ===
        else:
            # --- 0. Cek Out-of-Scope Dulu ---
            is_oos, oos_reason = check_out_of_scope(
                text_lower_stripped, DOMAIN_KEYWORDS, OOS_KEYWORDS, MIN_LEN_FOR_NO_DOMAIN_OOS
            )

            if is_oos: # Trigger OOS if heuristic returns True for any reason
                print(f"INFO: Input terdeteksi OOS. Reason: {oos_reason}. Text: '{text}'")
                final_intent_category = f"out_of_scope_heuristic_{oos_reason}"
                safe_user_name_oos = escape(user_name_from_session) if user_name_from_session else None
                sapaan_oos = f"Maaf {safe_user_name_oos}, " if safe_user_name_oos else "Maaf, "
                oos_responses = [
                    f"{sapaan_oos}saya adalah chatbot khusus untuk informasi Fakultas Teknik Universitas Andi Djemma Palopo. Topik pertanyaan Anda sepertinya di luar fokus utama saya.",
                    f"{sapaan_oos}saya hanya bisa menjawab pertanyaan terkait akademik, biaya, pendaftaran, dan info umum Fakultas Teknik UNANDA.",
                    f"{sapaan_oos}fokus saya adalah seputar Fakultas Teknik UNANDA. Ada hal lain yang bisa saya bantu terkait fakultas?"
                ]
                response_text = random.choice(oos_responses)
                debug_info = {
                    "user_text": text, "final_intent_category": final_intent_category,
                    "oos_detection_reason": oos_reason, "user_name_in_session": user_name_from_session,
                }
                end_time = time.time()
                debug_info["processing_time_ms"] = round((end_time - start_time) * 1000)
                return jsonify({"answer": response_text, "debug_info": debug_info})
            # Jika is_oos False, lanjutkan proses NLU

            # --- 1. Handle Special Cases (Salam Islami, dll.) ---
            # Contoh: Handle Salam Islami secara spesifik
            salam_pattern = r"^\s*assalamu'?alaikum(\s*wr\.?\s*wb\.?)?\s*[\.!\?]?\s*$"
            if re.match(salam_pattern, text_lower_stripped):
                salam_responses = ["Wa'alaikumsalam!", "Wa'alaikumussalam.", "Wa'alaikumsalam warahmatullahi wabarakatuh."]
                answer = random.choice(salam_responses)
                safe_name_temp = escape(user_name_from_session) if user_name_from_session else None
                answer += f" Ada yang bisa saya bantu, {safe_name_temp}?" if safe_name_temp else " Ada yang bisa saya bantu?"
                final_intent_category = "greeting_islamic_handled"
                debug_info = {
                    "user_text": text, "detected_intent": final_intent_category, "intent_score": 1.0,
                    "user_name_in_session": user_name_from_session, "oos_detection_result": (is_oos, oos_reason)
                }
                end_time = time.time()
                debug_info["processing_time_ms"] = round((end_time - start_time) * 1000)
                return jsonify({ "answer": answer, "debug_info": debug_info })
            # Tambahkan handle special case lain jika perlu di sini

            # --- 2. Proses NLU ---
            if not nlp: # Jika model NLP gagal load, beri pesan error
                 print("ERROR: Model NLP tidak tersedia, tidak dapat memproses NLU.")
                 response_text = "Maaf, sistem NLU sedang tidak aktif. Tidak dapat memproses permintaan Anda saat ini."
                 final_intent_category = "nlu_system_unavailable"
                 debug_info = { "user_text": text, "final_intent_category": final_intent_category }
                 end_time = time.time(); debug_info["processing_time_ms"] = round((end_time - start_time) * 1000)
                 return jsonify({ "answer": response_text, "debug_info": debug_info })

            nlu_result = process_nlu(text) # NLU result is guaranteed to be a dictionary
            all_intents_scores = nlu_result.get("all_intents", {})
            # Ensure top intent and score are based on the actual result
            top_intent = nlu_result.get('intent')
            top_score = nlu_result.get('score', 0.0)


            # --- 3. Cek Ambiguitas Intent ---
            needs_disambiguation = False
            ambiguous_intents = []
            if ENABLE_INTENT_DISAMBIGUATION and len(all_intents_scores) > 1:
                # Sort intents by score in descending order
                sorted_intents = sorted(all_intents_scores.items(), key=lambda item: item[1], reverse=True)

                # Check if there are at least two intents to compare
                if len(sorted_intents) >= 2:
                     top_intent_name, top_score_check = sorted_intents[0]
                     second_intent_name, second_score = sorted_intents[1]

                     # Kondisi ambiguitas: Keduanya di atas threshold & selisihnya kecil
                     if (top_score_check >= CONFIDENCE_THRESHOLD and
                         second_score >= CONFIDENCE_THRESHOLD and
                         (top_score_check - second_score) < DISAMBIGUATION_MARGIN):
                         needs_disambiguation = True
                         # Ambil hingga top N intents yang skornya dekat dengan top intent, max 3
                         ambiguous_intents.append((top_intent_name, top_score_check))
                         for i in range(1, len(sorted_intents)):
                              intent_name, score = sorted_intents[i]
                              if (top_score_check - score) < DISAMBIGUATION_MARGIN and len(ambiguous_intents) < 3:
                                   ambiguous_intents.append((intent_name, score))
                              else:
                                   break # Stop if score difference is too large or max options reached

            if needs_disambiguation and len(ambiguous_intents) >= 2: # Only disambiguate if at least 2 options identified
                 print(f"INFO: Intent ambiguity detected for '{text}'. Candidates: {ambiguous_intents}")
                 options = {}
                 response_lines = ["Hmm, saya perlu sedikit klarifikasi. Apakah yang Anda maksud:"]
                 option_num = 1
                 valid_options_count = 0

                 for intent_name, score in ambiguous_intents:
                      # Ambil deskripsi intent, atau buat default jika tidak ada
                      description = INTENT_DESCRIPTIONS.get(intent_name, intent_name.replace("_", " ").capitalize())
                      # Pastikan intent yang ditawarkan adalah intent yang ingin kita handle
                      if description and intent_name in INTENT_DESCRIPTIONS: # Hanya tawarkan jika ada deskripsi
                           response_lines.append(f"{option_num}. {description}?")
                           options[str(option_num)] = intent_name # Simpan mapping nomor ke intent
                           option_num += 1
                           valid_options_count += 1
                      # Tidak perlu break, ambil semua opsi yang relevan hingga max 3 sudah dibatasi di atas

                 # Hanya trigger klarifikasi jika ada minimal 2 opsi valid
                 if valid_options_count >= 2:
                      response_text = "\n".join(response_lines)
                      final_intent_category = "intent_disambiguation_prompt"

                      # Simpan state ke session
                      session['dialogue_state'] = 'awaiting_intent_clarification'
                      session['clarification_options'] = options
                      nlu_result['user_text'] = text # Tambahkan teks asli user ke NLU result yang disimpan
                      # Simpan NLU result asli (termasuk entities dan doc)
                      session['original_ambiguous_nlu'] = nlu_result

                      debug_info = {
                          "user_text": text, "final_intent_category": final_intent_category,
                          "detected_ambiguity": True, "ambiguous_intents_offered": ambiguous_intents,
                          "clarification_options_map": options, "user_name_in_session": user_name_from_session,
                          "oos_detection_result": (is_oos, oos_reason),
                          "confidence_threshold": CONFIDENCE_THRESHOLD,
                          "disambiguation_margin": DISAMBIGUATION_MARGIN,
                          "all_intent_scores_raw": {k: round(v, 4) for k, v in all_intents_scores.items()},
                      }
                      end_time = time.time()
                      debug_info["processing_time_ms"] = round((end_time - start_time) * 1000)
                      return jsonify({"answer": response_text, "debug_info": debug_info})
                 else:
                      # Jika karena suatu hal tidak bisa membuat 2 opsi valid (misal deskripsi hilang)
                      print(f"WARNING: Ambiguity detected but not enough valid descriptions ({valid_options_count} out of {len(ambiguous_intents)}). Proceeding with top intent.")
                      needs_disambiguation = False # Batalkan klarifikasi, lanjutkan dengan intent teratas
                      # top_intent and top_score are already set from nlu_result at the beginning of Bagian 2

            # --- 4. Jika TIDAK Ambigu (atau klarifikasi dibatalkan) ---
            # top_intent dan top_score sudah diambil dari nlu_result
            entities = nlu_result.get('entities', {})
            # Assign value after process_nlu has successfully run
            extracted_name_person_ner = entities.get("PERSON") # <<<--- variabel ini sudah diinisialisasi di atas
            detected_prodi_list = entities.get("PRODI", [])
            detected_lab_list = entities.get("LAB", [])
            # Ambil entitas pertama yang terdeteksi jika ada
            detected_prodi = detected_prodi_list[0] if detected_prodi_list else None
            detected_lab = detected_lab_list[0] if detected_lab_list else None


            # Jika intent tidak terdeteksi sama sekali atau skor terlalu rendah (dan bukan OOS explicit)
            # Cek juga jika hanya 'neutral' yang terdeteksi dengan skor rendah
            is_low_confidence = not top_intent or top_score < CONFIDENCE_THRESHOLD
            # Memberi sedikit kelonggaran pada intent 'neutral' agar tidak selalu dianggap low confidence
            is_only_neutral_low_conf = (top_intent == "neutral" and top_score < CONFIDENCE_THRESHOLD + 0.15 and len(all_intents_scores) <= 1)


            if is_low_confidence or is_only_neutral_low_conf:
                 print(f"INFO: Intent low confidence or not detected for '{text}'. Top Intent: {top_intent}, Score: {top_score}")
                 # Berikan respons fallback generik
                 fallback_responses = [
                     "Maaf, saya kurang mengerti maksud pertanyaan Anda. Bisa coba gunakan kalimat lain?",
                     "Hmm, saya belum bisa memahami pertanyaan itu. Mungkin bisa diperjelas?",
                     "Maaf, bisa coba tanyakan dengan cara berbeda? Saya masih belajar.",
                     "Saya di sini untuk membantu seputar Fakultas Teknik UNANDA. Ada pertanyaan lain?"
                 ]
                 safe_user_fallback = escape(user_name_from_session) if user_name_from_session else None
                 if safe_user_fallback:
                      fallback_responses = [f"Maaf {safe_user_fallback}, saya kurang mengerti...", f"Hmm {safe_user_fallback}, bisa diperjelas?"] + fallback_responses

                 response_text = random.choice(fallback_responses)
                 final_intent_category = "fallback_low_confidence"
                 debug_info = {
                     "user_text": text, "final_intent_category": final_intent_category,
                     "top_intent_raw_model": top_intent, "intent_score": round(top_score, 4),
                     "all_intent_scores": {k: round(v, 4) for k, v in all_intents_scores.items()},
                     "entities_ner_model": {"PERSON": extracted_name_person_ner}, # variabel sudah diinisialisasi
                     "entities_rules": {"PRODI": detected_prodi_list, "LAB": detected_lab_list},
                     "user_name_in_session": user_name_from_session,
                     "oos_detection_result": (is_oos, oos_reason),
                     "confidence_threshold": CONFIDENCE_THRESHOLD,
                 }
                 end_time = time.time()
                 debug_info["processing_time_ms"] = round((end_time - start_time) * 1000)
                 return jsonify({"answer": response_text, "debug_info": debug_info})


            # --- 5. Handle Interaksi Nama ---
            # Inisialisasi variabel terkait nama (sudah diinisialisasi di awal fungsi)
            # rule_extracted_name = None
            # name_source = "unknown"
            # user_name_to_save = None
            # response_generated_by_name_logic = False

            is_short_input = len(text.split()) <= 5 # Cek apakah input pendek
            # Kondisi user kemungkinan memberikan nama:
            # 1. Intent 'provide_name' terdeteksi dengan skor cukup
            # 2. ATAU input pendek, ada entitas PERSON dari NER, belum ada nama di sesi, DAN bukan intent 'goodbye'
            # Tambahkan kondisi jika teks input mengandung frasa "nama saya" dll.
            contains_name_phrase = bool(re.search(r'\b(?:nama|panggilan)\s+(?:saya|aku|ku)\b|\bpanggil(?:\s+(?:saya|aku|ku))?\b', text_lower_stripped))
            likely_providing_name = (top_intent == "provide_name" and top_score >= CONFIDENCE_THRESHOLD) or \
                                    (is_short_input and extracted_name_person_ner is not None and not user_name_from_session and top_intent != 'goodbye_ft') or \
                                    (extracted_name_person_ner is not None and contains_name_phrase and not user_name_from_session)


            # --- 6. Alur Logika Utama (Nama & Intent Handler) ---

            # Kasus 1: Belum ada nama di sesi DAN user tidak sedang memberikan nama -> Minta Nama (jika intent relevan & bukan sekadar salam)
            if not user_name_from_session and not likely_providing_name:
                # Hanya minta nama jika intent utama cukup jelas (bukan salam generik/tanya identitas bot/thankyou/goodbye/neutral)
                ask_for_name = False
                if top_intent and top_intent not in ["greeting_ft", "ask_bot_identity", "thankyou_ft", "goodbye_ft", "neutral"] and top_score >= CONFIDENCE_THRESHOLD:
                    ask_for_name = True

                if ask_for_name:
                    final_intent_category = "prompt_for_name"
                    prompt_options = [
                        f"Tentu, saya coba bantu jawab. Tapi agar lebih akrab, boleh saya tahu nama Anda? (Contoh: 'nama saya Budi')",
                        f"Oke, sebelum masuk ke detailnya, Anda ingin dipanggil siapa? (Contoh: 'nama aku Citra')",
                        f"Siap! Untuk mempermudah komunikasi, boleh perkenalkan diri dulu? (Contoh: 'nama ku Doni' atau 'panggil saja Eka')"
                    ]
                    response_text = random.choice(prompt_options)
                    response_generated_by_name_logic = True
                # else: Jika tidak minta nama, lanjut ke intent handler (Kasus 3)

            # Kasus 2: User kemungkinan memberikan nama -> Proses Nama
            elif likely_providing_name:
                print(f"DEBUG: Likely providing name detected for input: '{text}'")
                # Prioritaskan nama dari NER jika ada
                if extracted_name_person_ner:
                    user_name_to_save = extracted_name_person_ner
                    name_source = "ner"
                    print(f"DEBUG: Nama '{user_name_to_save}' valid dari NER.")

                # Jika NER tidak ada ATAU intent provide_name sangat kuat, coba rules regex
                # Rules regex ini hanya dijalankan jika nama belum berhasil didapat dari NER
                if not user_name_to_save:
                    print(f"DEBUG: Nama dari NER tidak ada. Mencoba ekstraksi nama dengan rules...")
                    # Pola regex dari yang paling spesifik ke paling umum
                    # Menangkap grup nama setelah frasa pengantar
                    extraction_patterns = [
                        r"^(?:nama|panggilan)\s+(?:saya|aku|ku)\s+(?:adalah|yaitu)\s+([\w\s'-]+)", # nama saya adalah Budi
                        r"^(?:nama|panggilan)\s+(?:saya|aku|ku)\s+([\w\s'-]+)",             # nama saya Budi
                        r"^(?:saya|aku|ku)\s+(?:adalah|yaitu)\s+([\w\s'-]+)",             # saya adalah Budi (kurang reliable)
                        r"^panggil(?:\s+(?:saya|aku|ku))?\s+([\w\s'-]+)",                   # panggil saya Budi / panggil Budi
                        r"^(?:namaku|nama ku|panggilanku|panggilan ku)\s+([\w\s'-]+)",    # namaku Budi
                        r"^(?:nama|panggilan)\s+([\w\s'-]+)",                            # nama Budi (agak ambigu)
                        # Pola tangkap semua di akhir, hanya jika input sangat pendek
                    ]
                    potential_name_rule = None
                    pattern_that_matched = "None"

                    # Coba pola yang lebih spesifik dulu
                    for pattern in extraction_patterns:
                         match = re.search(pattern, text, flags=re.IGNORECASE)
                         if match and match.lastindex is not None and match.lastindex > 0:
                                extracted_part = match.group(match.lastindex).strip(' .,?!')
                                print(f"DEBUG: Pola Regex '{pattern}' cocok. Ekstraksi: '{extracted_part}'")
                                # Validasi hasil ekstraksi (panjang, bukan kata umum, tidak mengandung kata ganti)
                                if extracted_part and 1 < len(extracted_part) <= 30 and len(extracted_part.split()) <= 5 and \
                                   extracted_part.lower() not in ["iya", "ya", "oke", "ok", "baik", "siap", "bisa", "terima kasih", "thank you"]:
                                     # Pastikan tidak mengandung kata ganti di dalamnya
                                     if not any(pronoun in f" {extracted_part.lower()} " for pronoun in [" saya ", " aku ", " ku "]):
                                         potential_name_rule = extracted_part
                                         pattern_that_matched = pattern
                                         break # Berhenti jika menemukan kecocokan valid dari pola spesifik

                    # Jika pola spesifik tidak cocok dan input pendek, coba pola tangkap semua
                    # Gunakan threshold panjang yang sangat rendah untuk catch-all ini
                    if not potential_name_rule and is_short_input and len(text.split()) >= 1 and len(text) > 1:
                        short_input_name_candidate = text.strip(' .,?!')
                        # Validasi catch-all: sangat pendek, bukan kata umum/salam, tidak mengandung kata ganti
                        if 1 < len(short_input_name_candidate) <= 15 and len(short_input_name_candidate.split()) <= 2 and \
                            short_input_name_candidate.lower() not in ["iya", "ya", "oke", "ok", "baik", "siap", "bisa", "halo", "hai", "permisi", "admin", "bot", "chatbot", "makasih", "terima kasih", "thank you"]:
                             if not any(pronoun in f" {short_input_name_candidate.lower()} " for pronoun in [" saya ", " aku ", " ku "]):
                                potential_name_rule = short_input_name_candidate
                                pattern_that_matched = "short_input_catch_all"
                                print(f"DEBUG: Pola short input catch-all cocok. Ekstraksi: '{potential_name_rule}'")


                    # Jika nama dari NER tidak ada, gunakan hasil dari rules jika valid
                    if potential_name_rule: # Jika potential_name_rule berhasil mendapatkan nama
                         user_name_to_save = potential_name_rule
                         name_source = f"rule_{pattern_that_matched}"
                         rule_extracted_name = user_name_to_save # Simpan juga nama hasil rule ke variabel terpisah
                         print(f"INFO: Nama '{user_name_to_save}' disimpan dari rule (pola: {pattern_that_matched}).")
                    else:
                         print("DEBUG: Tidak ada nama valid yang bisa diekstrak dari rules.")

                # Setelah mencoba NER dan Rules, cek apakah nama berhasil didapatkan
                if user_name_to_save:
                    session['user_name'] = user_name_to_save.strip().title() # Simpan ke sesi dengan kapitalisasi
                    safe_user_name = escape(session['user_name'])
                    final_intent_category = "provide_name_handled"
                    success_responses = [
                        f"Baik {safe_user_name}, senang berkenalan! Nama Anda sudah saya ingat. Anda bisa bertanya tentang:\n- Biaya kuliah (Contoh: 'berapa spp informatika?')\n- Jadwal (Contoh: 'jadwal ti hari senin')\n- Info prodi (Contoh: 'info prodi tambang')\nAtau topik lainnya seputar Fakultas Teknik?",
                        f"Oke {safe_user_name}, terima kasih informasinya! Sekarang, apa yang ingin Anda tanyakan tentang Fakultas Teknik? Misalnya:\n- 'Info pendaftaran mahasiswa baru'\n- 'Cara bayar spp'\n- 'Fasilitas lab sipil'",
                        f"Siap {safe_user_name}! Silakan ajukan pertanyaan Anda mengenai Fakultas Teknik. Anda bisa tanya soal:\n- Biaya praktikum (Contoh: 'berapa biaya praktikum basis data?')\n- Kontak TU\n- Jadwal mata kuliah tertentu (Contoh: 'jadwal kalkulus')"
                    ]
                    response_text = random.choice(success_responses)
                    debug_info["name_extraction_source"] = name_source
                    debug_info["extracted_name_candidates"] = {"ner": extracted_name_person_ner, "rule": rule_extracted_name} # rule_extracted_name mungkin None
                else:
                    # Jika nama tidak berhasil diekstrak sama sekali
                    final_intent_category = "provide_name_failed"
                    failure_responses = [
                        "Hmm, sepertinya saya belum berhasil menangkap nama Anda dengan jelas. Bisa coba sebutkan nama panggilannya saja? (Contoh: 'panggil saja Budi')",
                        "Maaf, saya agak kesulitan mengenali namanya. Bisa diulangi? (Contoh: 'nama saya Citra')",
                        "Oke, tapi nama yang saya tangkap sepertinya kurang pas. Bisa tolong sebutkan lagi nama Anda? (Contoh: 'nama ku Doni')"
                    ]
                    response_text = random.choice(failure_responses)
                    debug_info["name_extraction_source"] = "failed"
                    debug_info["extracted_name_candidates"] = {"ner": extracted_name_person_ner, "rule": rule_extracted_name} # rule_extracted_name mungkin None

                response_generated_by_name_logic = True
            # Akhir dari blok 'likely_providing_name'

            # Kasus 3: Tidak minta nama DAN tidak proses nama -> Panggil Intent Logic Handler Utama
            if not response_generated_by_name_logic:
                try:
                    print(f"INFO: Calling intent logic handler for intent '{top_intent}' with score {top_score:.4f}")
                    # Pass the extracted entities to the logic handler
                    # Ensure the latest extracted name is in nlu_result for the handler
                    nlu_result['entities']['PERSON'] = extracted_name_person_ner

                    response_text, final_intent_category = intent_logic.get_response_for_intent(
                        nlu_result, user_name_from_session, text, APP_CONFIG
                    )
                except Exception as logic_err:
                     print(f"ERROR saat menjalankan intent logic utama: {logic_err}")
                     traceback.print_exc()
                     safe_user_name_temp = escape(user_name_from_session) if user_name_from_session else None
                     sapaan_temp = f"{safe_user_name_temp}, " if safe_user_name_temp else ""
                     response_text = f"Maaf {sapaan_temp}terjadi kesalahan saat memproses permintaan Anda tentang topik tersebut."
                     final_intent_category = "handler_error_main"

            # --- 7. Siapkan Debug Info Final & Kembalikan Respons ---
            # Ambil nama terbaru dari sesi setelah logic handler berjalan (jika nama baru disimpan)
            user_name_after_logic = session.get('user_name')

            # Rekonstruksi debug_info untuk mencakup semua skenario
            # Mulai dengan debug_info yang mungkin sudah diisi di Bagian 1 atau 2 (saat low confidence/OOS/name handling)
            # Jika belum ada, inisialisasi ulang
            if not debug_info:
                 debug_info = {"user_text": text} # Minimal user text

            debug_info.update({
                "final_intent_category": final_intent_category,
                "top_intent_raw_model": nlu_result.get('intent'), # Gunakan nlu_result yang didapat
                "intent_score": round(nlu_result.get('score', 0.0), 4),
                "all_intent_scores": {k: round(v, 4) for k, v in nlu_result.get('all_intents', {}).items()},
                # <<<--- PERBAIKAN TYPO DI SINI --->>>
                "entities_ner_model": {"PERSON": extract_model_person_name(nlu_result.get('doc')) if nlu_result.get('doc') else None}, # Re-extract safely using correct function name
                # <<<--- AKHIR PERBAIKAN --->>>
                "entities_rules": {"PRODI": nlu_result.get('entities', {}).get('PRODI', []), "LAB": nlu_result.get('entities', {}).get('LAB', [])}, # Ambil dari nlu_result
                "name_in_session_before_logic": user_name_from_session,
                "name_in_session_after_logic": user_name_after_logic,
                "rule_extracted_name_candidate": rule_extracted_name, # Variabel dari Bagian 2
                "name_saved_source": debug_info.get("name_extraction_source", "not_name_intent_flow"), # Ambil jika sudah diset, default jika tidak
                "confidence_threshold": CONFIDENCE_THRESHOLD,
                "likely_providing_name_flag": likely_providing_name, # Variabel dari Bagian 2
                "oos_detection_result": (is_oos, oos_reason), # Variabel dari Bagian 2
                "intent_disambiguation_triggered": needs_disambiguation, # Variabel dari Bagian 2
            })

            end_time = time.time()
            debug_info["processing_time_ms"] = round((end_time - start_time) * 1000)

            return jsonify({"answer": response_text, "debug_info": debug_info})
        # === END BAGIAN 2 ===

    # --- Exception Handling Global ---
    except Exception as e:
        print(f"FATAL ERROR in /predict endpoint: {e}")
        traceback.print_exc()
        # Selalu coba bersihkan state dialog dan nama pengguna jika terjadi error tak terduga
        if 'dialogue_state' in session:
             session.pop('dialogue_state', None)
             session.pop('clarification_options', None)
             session.pop('original_ambiguous_nlu', None)
             print("ERROR: Dialogue state cleared due to unhandled exception.")
        if 'user_name' in session:
             # session.pop('user_name', None) # Jangan hapus nama di sesi saat error fatal, agar user tidak perlu memperkenalkan diri lagi
             print("INFO: User name preserved in session despite unhandled exception.")


        error_message = "Maaf, terjadi kendala teknis di sistem saya. Silakan coba beberapa saat lagi."
        user_name_on_error = "N/A"
        error_text_on_error = "N/A"
        try:
            # Coba dapatkan nama dari sesi sebelum dihapus (jika sempat)
            user_name_on_error = escape(session.get('user_name', 'N/A'))
            if user_name_on_error != "N/A":
                 error_message = f"Maaf {user_name_on_error}, terjadi kendala teknis di sistem saya. Silakan coba beberapa saat lagi."
            # Coba dapatkan teks input saat error terjadi
            if 'data' in locals() and isinstance(data, dict):
                 error_text_on_error = data.get("text", "N/A")
        except Exception as inner_e:
             print(f"Error during exception handling itself: {inner_e}")

        error_debug_info = {
            "error_type": type(e).__name__,
            "error_message_detail": str(e),
            "user_text_on_error": error_text_on_error,
            "final_intent_category": "internal_server_error",
            "user_name_in_session_on_error": user_name_on_error,
            "traceback": traceback.format_exc() # Sertakan traceback lengkap di debug info
        }
        # Tambahkan waktu proses jika memungkinkan
        if 'start_time' in locals():
            end_time = time.time()
            error_debug_info["processing_time_ms"] = round((end_time - start_time) * 1000)

        return jsonify({
            "answer": error_message,
            "error": "Internal Server Error",
            "debug_info": error_debug_info
        }), 500

# --- Route Lupa Nama ---
@app.route("/forget_name", methods=["POST"])
def forget_name():
    """Hapus nama pengguna dari sesi dan bersihkan state dialog."""
    # Bersihkan state dialog apapun saat lupa nama
    if 'dialogue_state' in session:
        session.pop('dialogue_state', None)
        session.pop('clarification_options', None)
        session.pop('original_ambiguous_nlu', None)
        print("INFO: Dialogue state cleared on forget_name request.")

    user_name = session.get('user_name')
    if user_name:
        safe_removed_name = escape(user_name)
        session.pop('user_name', None)
        # Verifikasi bahwa nama benar-benar hilang dari sesi
        if 'user_name' not in session:
            print(f"INFO: User name '{safe_removed_name}' removed from session.")
            return jsonify({
                "status": "success",
                "message": f"Baik {safe_removed_name}, nama Anda sudah tidak saya simpan lagi. Kita mulai dari awal ya."
            })
        else:
            # Kasus aneh jika pop gagal
            print("WARNING: Session pop 'user_name' failed unexpectedly.")
            return jsonify({
                "status": "error",
                "message": "Maaf, terjadi sedikit masalah saat mencoba melupakan nama Anda."
            }), 500
    else:
        # Jika memang belum ada nama di sesi
        print("INFO: /forget_name called but no user_name was in session.")
        return jsonify({
            "status": "no_name",
            "message": "Tidak masalah, saya memang belum menyimpan nama Anda sebelumnya."
        })


# --- Jalankan Server ---
if __name__ == "__main__":
    print("\n" + "="*60)
    print("      CHATBOT FAKULTAS TEKNIK SERVER (UNANDA) - Cleaned Version")
    print("="*60)
    print(f"[*] Base Directory      : '{BASE_DIR}'")
    print(f"[*] Model Dimuat dari   : '{MODEL_DIR}'")
    print(f"[*] Folder Data         : '{DATA_DIR}'")
    print(f"[*] Logic Handler File  : intent_logic.py")
    print(f"[*] Conf. Threshold     : {CONFIDENCE_THRESHOLD}")
    print(f"[*] OOS Keywords        : Loaded ({len(DOMAIN_KEYWORDS)} domain, {len(OOS_KEYWORDS)} explicit OOS)")
    print(f"[*] Intent Disambiguation: {'ENABLED' if ENABLE_INTENT_DISAMBIGUATION else 'DISABLED'} (Margin: {DISAMBIGUATION_MARGIN})")
    print(f"[*] Mode Debug Flask    : {app.debug}")
    secret_key_status = "Default (TIDAK AMAN!)" if 'ganti-ini-dengan-kunci-rahasia' in app.secret_key else "Custom/Env Var (Lebih Aman)"
    print(f"[*] Status Secret Key   : {secret_key_status}")

    print("\n--- Status Model & Matcher ---")
    print(f"[*] Model spaCy ({os.path.basename(MODEL_DIR)}) : {'Loaded' if nlp else 'FAILED'}")
    # Berikan status matcher berdasarkan nlp dan entity_details
    matcher_status = 'Not Initialized'
    if nlp and matcher and entity_details and (len(matcher) > 0 or len(entity_details) > 0): matcher_status = f'Initialized ({len(matcher)} patterns, {len(entity_details)} entity details)'
    elif nlp and matcher: matcher_status = f'Initialized ({len(matcher)} patterns, BUT entity_details empty/invalid!)'
    elif not nlp: matcher_status = 'Skipped (Model Failed)'
    print(f"[*] PhraseMatcher         : {matcher_status}")
    if nlp and matcher and entity_details and (len(matcher) > 0 or len(entity_details) > 0):
        prodi_count = len([k for k in entity_details if k.startswith('PRODI_')])
        lab_count = len([k for k in entity_details if k.startswith('LAB_')])
        print(f"    - Pola Prodi: {prodi_count}, Pola Lab: {lab_count}")
    elif nlp:
         print("    - Tidak ada pola Prodi atau Lab yang berhasil ditambahkan.")


    print("\n--- Status Data Eksternal (via APP_CONFIG) ---")
    data_keys_to_check=['FT_FEES','PMB_INFO','LEARNING_CONTENT','SPP_DATA','TERMS_DATA','JADWAL_TI_DATA','JADWAL_SIPIL_DATA','JADWAL_TAMBANG_DATA','KRS_SEVIMA_GUIDE','PAYMENT_SEVIMA_TOKOPEDIA_GUIDE']
    all_data_loaded_check = True # Use a different variable name to avoid conflict
    for key in data_keys_to_check:
        data = APP_CONFIG.get(key)
        status = 'MISSING/ERROR'
        # Check if data is loaded and not empty (for dict/list) or not an error string (for text)
        if data is not None: # Check if key exists
             if isinstance(data, (dict, list)) and len(data) > 0:
                  status = 'OK'
             # Also check for string data that is not an error message and is not empty
             elif isinstance(data, str) and ('tidak ditemukan' not in data.lower() and 'terjadi kesalahan' not in data.lower() and data.strip()): # Case-insensitive check for error strings
                  status = 'OK'
             else: # Data is empty dict/list or an error string or empty string or None
                  status = 'EMPTY/ERROR'
                  all_data_loaded_check = False
        else: # Key is missing from APP_CONFIG (shouldn't happen with .get) or data is None
             status = 'MISSING/NONE'
             all_data_loaded_check = False

        print(f"[*] Config Key: {key.ljust(30)}: {status}")

    if not nlp:
        print("\n" + "!"*20 + " ERROR KRITIS: Model spaCy gagal dimuat. Chatbot tidak dapat berfungsi penuh. " + "!"*20)
    # Check against the new variable name
    elif not all_data_loaded_check:
         print("\n" + "!"*15 + " PERHATIAN: Beberapa data eksternal gagal dimuat atau kosong. Fungsi chatbot mungkin terbatas. " + "!"*15)
    else:
        print("\n" + "="*25 + " PERHATIAN PENTING " + "="*25)
        print(">> Pastikan placeholder [GANTI ...] di config/logic sudah diisi dengan benar.")
        print(">> Pastikan file data di folder 'data/' (JSON, TXT) adalah versi terbaru.")
        print(">> Pastikan model spaCy relevan dengan data training dan intent.")
        print(">> Tinjau ulang DOMAIN_KEYWORDS, OOS_KEYWORDS, INTENT_DESCRIPTIONS di app.py.")
        print("="*70 + "\n")
        print("--- Server Siap Dijalankan ---")


    app.run(debug=True, host='0.0.0.0', port=5000)

# --- END OF CLEANED FILE app.py ---