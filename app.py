# app.py (Versi Gabungan: NER Rules + Fee + Tanya Nama + PMB + Info Pembelajaran)

import spacy
from flask import Flask, request, jsonify, render_template, session
from markupsafe import escape
import random
import os
import secrets
from spacy.matcher import PhraseMatcher
import traceback

# --- Konfigurasi ---
MODEL_DIR = "intent_model_ft_v2"
CONFIDENCE_THRESHOLD = 0.5

# --- Inisialisasi Aplikasi Flask ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'ganti-ini-dengan-kunci-rahasia-acak-yang-aman-' + secrets.token_hex(16))

# --- DATA BIAYA FAKULTAS TEKNIK ---
FT_FEES = {
    "praktikum": {
        "Lab Software": {"amount": 250000, "ujian_akhir_praktikum_amount": 100000, "notes": "Dibayarkan per praktikum melalui Asisten Lab TI."},
        "Lab Hardware": {"amount": 250000, "ujian_akhir_praktikum_amount": 100000, "notes": "Dibayarkan per praktikum melalui Asisten Lab TI."},
        "Lab Mekanika Tanah": {"amount": 250000, "ujian_akhir_praktikum_amount": 100000, "notes": "Dibayarkan per praktikum melalui Asisten Lab Sipil/Tambang."}, # Catatan mungkin perlu spesifik
        "Lab Perkerasan Jalan Raya & Aspal": {"amount": 250000, "ujian_akhir_praktikum_amount": 100000, "notes": "Dibayarkan per praktikum melalui Asisten Lab Sipil."},
        "Lab Hidrolika": {"amount": 250000, "ujian_akhir_praktikum_amount": 100000, "notes": "Dibayarkan per praktikum melalui Asisten Lab Sipil."},
        "Lab Struktur & Bahan": {"amount": 250000, "ujian_akhir_praktikum_amount": 100000, "notes": "Dibayarkan per praktikum melalui Asisten Lab Sipil."},
        "Lab Gambar Rekayasa": {"amount": 200000, "ujian_akhir_praktikum_amount": 50000, "notes": "Biasanya via Aslab Sipil, konfirmasi ulang."}, # Contoh biaya beda
        "Lab Geologi Fisik": {"amount": 250000, "ujian_akhir_praktikum_amount": 100000, "notes": "Dibayarkan per praktikum melalui Asisten Lab Tambang."},
        "Lab Perpetaan": {"amount": 250000, "ujian_akhir_praktikum_amount": 100000, "notes": "Dibayarkan per praktikum melalui Asisten Lab Tambang."},
        "Lab Mineralogi dan Petrologi": {"amount": 250000, "ujian_akhir_praktikum_amount": 100000, "notes": "Dibayarkan per praktikum melalui Asisten Lab Tambang."},
        "Lab Geologi Struktur": {"amount": 250000, "ujian_akhir_praktikum_amount": 100000, "notes": "Dibayarkan per praktikum melalui Asisten Lab Tambang."},
        # << LENGKAPI SEMUA LAB DENGAN BIAYA DAN CATATAN >>
        "_default": {
             "amount": 250000, # Asumsi biaya umum
             "ujian_akhir_praktikum_amount": 100000, # Asumsi biaya umum
             "notes": "Biaya dapat bervariasi per lab. Pembayaran biasanya melalui Asisten Lab. Mohon konfirmasi ke lab/prodi terkait."
         }
    }
}

# --- DATA PENERIMAAN MAHASISWA BARU (PMB) ---
PMB_INFO = {
    "website": "https://pmb.unanda.ac.id/home", # << GANTI JIKA PERLU
    "jalur": {
        "Mandiri": {"name": "Mandiri", "description": "Jalur pendaftaran umum untuk lulusan SMA/SMK/Sederajat."},
        "RPL": {"name": "Rekognisi Pembelajaran Lampau (RPL)", "description": "Jalur khusus bagi calon mahasiswa yang memiliki pengalaman kerja atau pendidikan sebelumnya yang relevan."}
    },
    "fees": {
        "formulir": {"name": "Biaya Formulir/Pendaftaran", "amount": 175000, "notes": "Dibayarkan saat pendaftaran awal."}, # << GANTI JIKA PERLU
        "etika_pembekalan": {"name": "Biaya Etika/Pembekalan Mahasiswa Baru", "amount": 500000, "notes": "Biasanya dibayarkan setelah lulus seleksi."} # << GANTI JIKA PERLU
    },
    "general_steps": [  
        "Kunjungi Website PMB resmi: https://pmb.unanda.ac.id/home", # << GANTI JIKA PERLU
        "Pilih jalur pendaftaran.", "Buat akun dan lengkapi formulir online.", "Lakukan pembayaran biaya formulir.",
        "Unggah berkas persyaratan.", "Ikuti tahapan seleksi (jika ada).", "Pantau pengumuman kelulusan.",
        "Jika lulus, lakukan daftar ulang dan pembayaran biaya lainnya."
    ]
}

# --- DATA PEMBELAJARAN PRODI DAN LAB ---
LEARNING_CONTENT = {
    "Teknik Sipil": {
        "_prodi_summary": (
            "Prodi Teknik Sipil berfokus pada perancangan, konstruksi, dan pemeliharaan infrastruktur fisik "
            "seperti gedung, jembatan, jalan raya, bendungan, dan sistem pengelolaan air. Mahasiswa belajar "
            "prinsip-prinsip rekayasa struktur, geoteknik (tanah), hidrolika (air), transportasi, dan manajemen konstruksi."
        ),
        "Lab Perkerasan Jalan Raya & Aspal": (
            "Di lab ini, mahasiswa mempelajari material (terutama aspal) dan teknik yang digunakan dalam konstruksi perkerasan jalan. "
            "Fokusnya pada pengujian sifat dan kekuatan aspal, campuran beraspal, pengaruh beban lalu lintas, "
            "serta aspek lingkungan terkait konstruksi jalan."
        ),
        "Lab Hidrolika": (
            "Mahasiswa mendalami prinsip-prinsip mekanika fluida dan aliran air. Praktikum mencakup pengujian dan analisis "
            "aliran pada saluran terbuka (sungai, drainase), aliran dalam pipa, serta aplikasinya dalam desain bangunan air, "
            "irigasi, pengendalian banjir, dan sistem perpipaan."
        ),
        "Lab Mekanika Tanah": (
            "Lab ini fokus pada studi sifat fisik dan mekanik tanah serta perilakunya saat menerima beban. Mahasiswa melakukan "
            "serangkaian pengujian untuk menentukan parameter tanah seperti kepadatan, kuat geser, permeabilitas (kemampuan air meresap), "
            "dan konsolidasi (penurunan tanah), yang krusial untuk desain pondasi yang aman dan stabil."
        ),
        "Lab Struktur & Bahan": (
            "Mahasiswa mengkaji karakteristik dan perilaku material konstruksi utama seperti beton, baja, kayu, dan material komposit lainnya. "
            "Mereka melakukan pengujian kekuatan tarik, tekan, lentur, dan durabilitas material, serta mempelajari analisis dan desain "
            "elemen struktur dasar (balok, kolom) untuk memastikan keamanan dan kinerja bangunan."
        ),
        "Lab Gambar Rekayasa": (
            "Di sini, mahasiswa belajar keterampilan fundamental dalam komunikasi visual teknik, yaitu membuat dan membaca gambar teknik "
            "yang presisi. Mereka mempelajari standar penggambaran, proyeksi ortogonal, gambar detail, gambar rakitan, "
            "serta penggunaan perangkat lunak CAD (Computer-Aided Design) untuk merancang dan mendokumentasikan struktur."
        )
        # << TAMBAHKAN DESKRIPSI LAB SIPIL LAIN JIKA ADA >>
    },
    "Teknik Informatika": {
        "_prodi_summary": (
            "Prodi Teknik Informatika mempelajari dasar-dasar ilmu komputer dan teknologi informasi. Fokus utamanya meliputi "
            "pengembangan perangkat lunak (pemrograman, rekayasa perangkat lunak), jaringan komputer, sistem basis data, "
            "kecerdasan buatan (AI), keamanan siber, dan pengembangan aplikasi web/mobile."
        ),
        "Lab Software": (
            "Lab ini menjadi pusat pengembangan keterampilan rekayasa perangkat lunak. Mahasiswa fokus pada seluruh siklus hidup "
            "pengembangan software, mulai dari analisis kebutuhan, desain arsitektur aplikasi, implementasi (coding) dengan berbagai bahasa pemrograman, "
            "pengujian (debugging), hingga manajemen proyek perangkat lunak menggunakan metodologi modern."
        ),
        "Lab Hardware": (
            "Mahasiswa mendalami komponen fisik sistem komputer dan perangkat elektronik. Kegiatan praktikum meliputi perakitan dan troubleshooting PC, "
            "pemahaman arsitektur komputer, pengujian fungsionalitas perangkat keras, dasar-dasar sistem digital, serta pemrograman "
            "mikrokontroler (seperti Arduino/Raspberry Pi) dan interfacenya dengan sensor atau aktuator."
        )
        # << TAMBAHKAN DESKRIPSI LAB INFORMATIKA LAIN JIKA ADA >>
    },
    "Teknik Pertambangan": {
        "_prodi_summary": (
            "Prodi Teknik Pertambangan fokus pada ilmu dan teknologi yang berkaitan dengan eksplorasi (pencarian), evaluasi, "
            "ekstraksi (penambangan), dan pengolahan sumber daya mineral (logam, batubara, industri) secara efisien, "
            "aman, dan berwawasan lingkungan. Topik meliputi geologi, mekanika batuan, metode penambangan, dan pengolahan bahan galian."
        ),
        "Lab Geologi Fisik": ( # Nama disesuaikan dari input
            "Di lab ini, mahasiswa mempelajari identifikasi dan sifat-sifat fisik batuan dan mineral pembentuk kerak bumi. "
            "Mereka juga mengamati dan menganalisis proses-proses geologi dasar yang membentuk permukaan bumi (pelapukan, erosi, sedimentasi) "
            "dan fenomena seperti pergerakan tanah, yang relevan untuk memahami lingkungan deposit mineral."
        ),
        "Lab Perpetaan": (
            "Mahasiswa belajar teknik pengukuran dan pembuatan peta topografi serta peta situasi area pertambangan. Ini mencakup "
            "penggunaan alat ukur lapangan (seperti Theodolite, Total Station, GPS Geodetik) dan pengolahan datanya menggunakan "
            "perangkat lunak pemetaan dan Sistem Informasi Geografis (SIG/GIS) untuk perencanaan tambang."
        ),
        "Lab Mekanika Tanah": ( # Deskripsi spesifik Tambang
            "Lab ini mempelajari sifat mekanik tanah dan batuan lunak, namun dengan penekanan pada aplikasi di bidang pertambangan. "
            "Fokusnya meliputi analisis kestabilan lereng (slope stability) pada tambang terbuka, daya dukung tanah untuk infrastruktur tambang, "
            "serta pengelolaan dan pemindahan tanah (overburden) secara efisien dan aman."
        ),
        "Lab Mineralogi dan Petrologi": (
            "Mahasiswa belajar mengidentifikasi berbagai jenis mineral (pembawa bijih dan pengotor) serta batuan (beku, sedimen, metamorf) "
            "menggunakan sifat fisik dan optik (dengan mikroskop polarisasi). Pemahaman ini penting untuk eksplorasi mineral, "
            "karakterisasi cebakan, dan menentukan metode pengolahan yang tepat."
        ),
        "Lab Geologi Struktur": (
            "Fokus lab ini adalah pada pemahaman struktur geologi skala besar seperti lipatan (folds), sesar (faults), dan kekar (joints) "
            "yang mengontrol pembentukan dan lokasi deposit mineral. Mahasiswa belajar interpretasi data geologi (peta, data bor) "
            "untuk memodelkan struktur bawah permukaan dan memprediksi potensi sumber daya."
        )
        # << TAMBAHKAN DESKRIPSI LAB TAMBANG LAIN JIKA ADA >>
    }
    # << TAMBAHKAN PRODI LAIN JIKA ADA >>
}

# Helper function format Rupiah
def format_idr(amount):
    if amount is None: return "N/A"
    try:
        return f"Rp {amount:,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        return str(amount)

# --- Memuat Model spaCy ---
try:
    nlp = spacy.load(MODEL_DIR)
    print(f"Model spaCy '{MODEL_DIR}' berhasil dimuat.")
except OSError:
    print(f"ERROR: Tidak dapat menemukan model di '{MODEL_DIR}'. Pastikan path benar dan model sudah dilatih ulang.")
    exit()
except Exception as e:
    print(f"ERROR lain saat memuat model: {e}")
    exit()

# --- Inisialisasi PhraseMatcher untuk PRODI dan LAB ---
matcher = PhraseMatcher(nlp.vocab, attr='LOWER')

# --- DEFINISIKAN ISTILAH ENTITAS (LENGKAPI DAFTAR INI!) ---
# Nama kanonis di sini HARUS SAMA dengan kunci di LEARNING_CONTENT dan FT_FEES jika relevan
PRODI_TERMS = {
    "Teknik Sipil": ["teknik sipil", "sipil", "prodi sipil", "jurusan sipil"],
    "Teknik Informatika": ["teknik informatika", "informatika", "ti", "inf", "prodi informatika", "jurusan ti", "ilmu komputer"],
    "Teknik Pertambangan": ["teknik pertambangan", "pertambangan", "tambang", "prodi pertambangan", "jurusan tambang"]
    # << TAMBAHKAN PRODI LAIN JIKA ADA >>
}
LAB_TERMS = {
    # Sipil
    "Lab Perkerasan Jalan Raya & Aspal": ["lab perkerasan jalan", "lab aspal", "lab jalan raya"],
    "Lab Hidrolika": ["lab hidrolika", "lab aliran air", "lab mekanika fluida sipil"],
    "Lab Mekanika Tanah": ["lab mekanika tanah", "lab mektan", "lab tanah"], # Nama ini dipakai di Sipil & Tambang
    "Lab Struktur & Bahan": ["lab struktur dan bahan", "lab struktur", "lab bahan", "lab beton", "lab baja"],
    "Lab Gambar Rekayasa": ["lab gambar rekayasa", "lab gambar teknik", "lab cad sipil"],
    # Informatika
    "Lab Software": ["lab software", "lab perangkat lunak", "lab pemrograman", "lab rpl"],
    "Lab Hardware": ["lab hardware", "lab perangkat keras", "lab jaringan", "lab mikrokontroler", "lab sistem digital"],
    # Pertambangan
    "Lab Geologi Fisik": ["lab geologi fisik", "lab geofis"], # Sesuaikan nama jika perlu
    "Lab Perpetaan": ["lab perpetaan", "lab pemetaan", "lab survei", "lab gis tambang"],
    # "Lab Mekanika Tanah": --> Sudah ada di atas, akan dideteksi oleh matcher
    "Lab Mineralogi dan Petrologi": ["lab mineralogi dan petrologi", "lab miner", "lab petro", "lab batuan tambang", "lab mineragrafi"],
    "Lab Geologi Struktur": ["lab geologi struktur", "lab geostruk"]
    # << TAMBAHKAN LAB LAIN JIKA ADA... PASTIKAN NAMA KANONIS KONSISTEN >>
}

# --- Tambahkan Pola ke PhraseMatcher ---
entity_details = {}
# Tambahkan Pola PRODI
for canonical, variations in PRODI_TERMS.items():
    patterns = [nlp.make_doc(text) for text in variations]
    match_id = f"PRODI_{canonical.replace(' ', '_')}"
    matcher.add(match_id, patterns)
    entity_details[match_id] = {"label": "PRODI", "canonical": canonical}
# Tambahkan Pola LAB
for canonical, variations in LAB_TERMS.items():
    patterns = [nlp.make_doc(text) for text in variations]
    # Pastikan ID unik dan konsisten, tangani '&'
    match_id = f"LAB_{canonical.replace(' ', '_').replace('&', 'and')}"
    matcher.add(match_id, patterns)
    entity_details[match_id] = {"label": "LAB", "canonical": canonical}

print(f"PhraseMatcher diinisialisasi dengan {len(matcher)} pola.")

# --- Helper: Ekstraksi Nama Person dari Entitas Model NER ---
def extract_model_person_name(doc):
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            return ent.text
    return None

# --- Route Utama ---
@app.route("/")
def index():
    return render_template("index.html")

# --- Route Prediksi Chat (Dengan Handler Pembelajaran) ---
@app.route("/predict", methods=["POST"])
def predict():
    try:
        text = request.json.get("text")
        if not text:
            return jsonify({"error": "Teks tidak ditemukan dalam request!"}), 400

        # 1. Proses teks
        doc = nlp(text)
        intents = doc.cats
        top_intent = max(intents, key=intents.get) if intents else None
        top_score = intents.get(top_intent, 0.0) if top_intent else 0.0
        extracted_name_person = extract_model_person_name(doc)

        # Jalankan PhraseMatcher
        matches = matcher(doc)
        extracted_rule_entities = {"PRODI": set(), "LAB": set()}
        # Gunakan list untuk menjaga urutan deteksi jika diperlukan, tapi set lebih mudah untuk cek keberadaan
        detected_prodi_list = []
        detected_lab_list = []
        for match_id_hash, start, end in matches:
            string_id = nlp.vocab.strings[match_id_hash]
            if string_id in entity_details:
                label = entity_details[string_id]["label"]
                canonical = entity_details[string_id]["canonical"]
                if label == "PRODI":
                    if canonical not in extracted_rule_entities["PRODI"]:
                         extracted_rule_entities["PRODI"].add(canonical)
                         detected_prodi_list.append(canonical)
                elif label == "LAB":
                     if canonical not in extracted_rule_entities["LAB"]:
                          extracted_rule_entities["LAB"].add(canonical)
                          detected_lab_list.append(canonical)
        # Ambil yang pertama terdeteksi untuk logika utama (bisa disesuaikan jika perlu multiple)
        detected_prodi = detected_prodi_list[0] if detected_prodi_list else None
        detected_lab = detected_lab_list[0] if detected_lab_list else None


        # --- Ambil Nama dari Session ---
        user_name_from_session = session.get('user_name')
        safe_user_name = escape(user_name_from_session) if user_name_from_session else None

        # --- Cek apakah user kemungkinan sedang memberikan nama ---
        is_short_input = len(text.split()) <= 3
        likely_providing_name = (top_intent == "provide_name" and top_score >= CONFIDENCE_THRESHOLD) or \
                                (is_short_input and extracted_name_person is not None and not top_intent)

        # --- Inisialisasi Variabel Respons ---
        response_text = "Maaf, terjadi kesalahan internal."
        final_intent_category = "internal_error_flow"

        # --- ALUR 1: Tanya Nama Jika Belum Ada ---
        if not user_name_from_session and not likely_providing_name:
            # ... (Logika tanya nama tetap sama) ...
            final_intent_category = "prompt_for_name"
            if top_intent and top_intent != "greeting_ft" and top_score >= CONFIDENCE_THRESHOLD:
                 prompt_options = [f"Tentu, saya bisa bantu soal itu. Tapi agar lebih akrab, boleh tahu nama Anda?", f"Oke, sebelum saya jawab, Anda ingin dipanggil siapa?", f"Siap! Boleh perkenalkan diri dulu?"]
            else:
                 prompt_options = ["Halo! Sebelum kita mulai, boleh tahu nama Anda?", "Hai! Supaya lebih enak ngobrolnya, Anda ingin dipanggil siapa?", "Selamat datang! Untuk memproses chat ini, boleh tahu nama panggilan Anda?"]
            response_text = random.choice(prompt_options)
            return jsonify({ "answer": response_text, "debug_info": { "user_text": text, "detected_intent": final_intent_category, "intent_score": round(top_score, 3) if top_intent else 0.0, "top_intent_raw": top_intent, "ner_person_model": extracted_name_person, "ner_prodi_rules": detected_prodi_list, "ner_lab_rules": detected_lab_list, "user_name_in_session": None } })

        # --- ALUR 2: Tangani Jika User Memberikan Nama ---
        elif likely_providing_name:
            # ... (Logika simpan nama tetap sama) ...
            user_name_to_save = extracted_name_person
            if not user_name_to_save and top_intent == "provide_name":
                 possible_name_parts = [word for word in text.split() if word and word[0].isupper()]
                 if possible_name_parts: user_name_to_save = " ".join(possible_name_parts).replace("Nama saya", "").replace("Panggil saya", "").strip(' .?!,')
            if user_name_to_save:
                user_name_to_save = user_name_to_save.replace("Nama saya", "").replace("Panggil saya", "").strip(' .?!,')
                session['user_name'] = user_name_to_save
                final_intent_category = "provide_name_handled"
                response_text = random.choice([ f"Baik {escape(session['user_name'])}, nama Anda sudah saya ingat. Ada yang bisa saya bantu terkait Fakultas Teknik?", f"Oke {escape(session['user_name'])}, terima kasih! Sekarang, apa yang ingin Anda tanyakan?", f"Siap {escape(session['user_name'])}! Silakan ajukan pertanyaan Anda tentang FT." ])
            else:
                final_intent_category = "provide_name_failed"
                response_text = random.choice([ "Oke, tapi sepertinya saya belum berhasil menangkap nama Anda. Bisa coba sebutkan nama Anda saja?", "Hmm, saya belum bisa mengenali namanya. Bisa ulangi nama Anda?" ])
            return jsonify({ "answer": response_text, "debug_info": { "user_text": text, "detected_intent": final_intent_category, "intent_score": round(top_score, 3) if top_intent else 0.0, "top_intent_raw": top_intent, "ner_person_model": extracted_name_person, "ner_prodi_rules": detected_prodi_list, "ner_lab_rules": detected_lab_list, "user_name_in_session": session.get('user_name') } })

        # --- ALUR 3: Proses Intent Lain (Jika Nama SUDAH DIKETAHUI) ---
        elif top_intent and top_score >= CONFIDENCE_THRESHOLD:
            final_intent_category = top_intent

            # --- Blok Respons per Intent ---
            if top_intent == "greeting_ft":
                response_text = random.choice([ f"Halo lagi {safe_user_name}! Ada lagi yang bisa saya bantu?", f"Hai {safe_user_name}! Senang bertemu Anda lagi.", f"Ya {safe_user_name}, ada keperluan apa lagi?" ])
            elif top_intent == "goodbye_ft":
                response_text = random.choice([f"Baik {safe_user_name}, sampai jumpa!", "Sampai jumpa!", "Senang bisa membantu."])
            elif top_intent == "thankyou_ft":
                response_text = random.choice([f"Sama-sama, {safe_user_name}!", "Sama-sama!", "Dengan senang hati!"])

            # == INFO SPP == (Sama seperti sebelumnya)
            elif top_intent == "info_spp_ft":
                 website_pmb = PMB_INFO.get('website', '[Website PMB belum diset]')
                 base_response = f"{safe_user_name}, info biaya SPP/UKT Fakultas Teknik untuk mahasiswa baru biasanya bisa dilihat di bagian rincian biaya pada website PMB: {website_pmb}"
                 note = " (Biaya ini mungkin belum termasuk biaya praktikum atau lainnya saat kuliah nanti)."
                 if detected_prodi: base_response += f" Detail untuk prodi {detected_prodi} mungkin ada di website PMB atau web prodi."
                 response_text = base_response + note

            # == CARA BAYAR SPP == (Sama seperti sebelumnya)
            elif top_intent == "cara_bayar_spp_ft":
                 response_text = f"{safe_user_name}, pembayaran SPP (setelah menjadi mahasiswa) dilakukan via sevima, Untuk pembayaran awal PMB, ikuti petunjuk di website PMB."

            # == JADWAL KULIAH == (Sama seperti sebelumnya, pastikan link diganti)
            elif top_intent == "jadwal_kuliah_ft":
                base_response = f"Untuk jadwal kuliah FT semester ini, {safe_user_name}: "
                links = []
                # << GANTI SEMUA LINK DI BAWAH INI >>
                if detected_prodi == "Teknik Informatika" or not detected_prodi: links.append("TI: [GANTI LINK JADWAL TI]")
                if detected_prodi == "Teknik Sipil" or not detected_prodi: links.append("Sipil: [GANTI LINK JADWAL SIPIL]")
                if detected_prodi == "Teknik Pertambangan" or not detected_prodi: links.append("Tambang: [GANTI LINK JADWAL TAMBANG]")
                if links: response_text = base_response + ", ".join(links) + "\nJadwal biasanya dibagikan oleh prodi menjelang awal semester."
                elif detected_prodi: response_text = f"Maaf {safe_user_name}, link jadwal spesifik untuk {detected_prodi} belum ada di sistem. Cek pengumuman prodi. [GANTI LINK UMUM FT JIKA ADA]"
                else: response_text = f"Maaf {safe_user_name}, jadwal prodi mana yang Anda maksud? Cek pengumuman dari prodi atau akademik FT. [GANTI LINK UMUM FT JIKA ADA]"

            # == FASILITAS UMUM == (Sama seperti sebelumnya)
            elif top_intent == "fasilitas_umum_ft":
                response_text = f"{safe_user_name}, fasilitas umum di FT antara lain: ruang kelas ber-AC, LCD, WiFi, perpustakaan fakultas, laboratorium (sesuai prodi), area diskusi, kantin terdekat, mushola."

            # == INFO LAB UMUM (Lokasi/Keberadaan/Biaya Awal) ==
            # (Logika ini tetap ada untuk info dasar, beda dengan tanya pembelajaran)
            elif top_intent == "info_lab_sipil" or top_intent == "info_lab_informatika" or top_intent == "info_lab_pertambangan":
                 # Menentukan target prodi berdasarkan intent atau deteksi
                 target_prodi = None
                 if detected_prodi: target_prodi = detected_prodi
                 elif top_intent == "info_lab_sipil": target_prodi = "Teknik Sipil"
                 elif top_intent == "info_lab_informatika": target_prodi = "Teknik Informatika"
                 elif top_intent == "info_lab_pertambangan": target_prodi = "Teknik Pertambangan"

                 response_parts = [f"Baik {safe_user_name}, mengenai laboratorium di Fakultas Teknik:"]
                 if target_prodi:
                     response_parts.append(f"Untuk Prodi {target_prodi}:")
                     labs_in_prodi = [lab for lab, details in LAB_TERMS.items() if lab in LEARNING_CONTENT.get(target_prodi, {})] # Cari lab yg ada deskripsinya di prodi target

                     if detected_lab and detected_lab in labs_in_prodi: # Jika lab spesifik disebut & valid untuk prodi itu
                         response_parts.append(f"- Lab utama yang relevan: {detected_lab}.")
                         # Tambah info biaya jika ada
                         fee_info = FT_FEES["praktikum"].get(detected_lab) or FT_FEES["praktikum"]["_default"]
                         response_parts.append(f"  Biaya partisipasi praktikumnya sekitar {format_idr(fee_info.get('amount'))} + {format_idr(fee_info.get('ujian_akhir_praktikum_amount'))} (ujian akhir).")
                         response_parts.append(f"  Catatan: {fee_info.get('notes')}")
                         response_parts.append(f"  Anda bisa tanya 'apa yang dipelajari di {detected_lab}?' untuk detail kegiatannya.")
                     elif labs_in_prodi: # Jika tidak ada lab spesifik disebut, list semua lab di prodi itu
                         response_parts.append(f"Terdapat beberapa laboratorium utama, antara lain: {', '.join(labs_in_prodi)}.")
                         # Info biaya umum
                         fee_info = FT_FEES["praktikum"]["_default"]
                         response_parts.append(f"Biaya praktikum umumnya sekitar {format_idr(fee_info.get('amount'))} per praktikum + {format_idr(fee_info.get('ujian_akhir_praktikum_amount'))} untuk ujian akhir.")
                         response_parts.append(f"Catatan: {fee_info.get('notes')}")
                         response_parts.append("Anda bisa tanya info spesifik per lab atau apa yang dipelajari di lab tersebut.")
                     else:
                         response_parts.append(f"Maaf, daftar laboratorium spesifik untuk {target_prodi} belum tersedia di sistem.")
                 else: # Jika tidak ada prodi terdeteksi sama sekali
                     all_labs = list(LAB_TERMS.keys())
                     response_parts.append("Fakultas Teknik memiliki berbagai laboratorium pendukung perkuliahan, seperti:")
                     response_parts.append(f"{', '.join(random.sample(all_labs, min(len(all_labs), 5)))}...") # Tampilkan beberapa contoh acak
                     response_parts.append("Lab mana atau dari prodi mana yang spesifik ingin Anda ketahui (Sipil, Informatika, Tambang)?")

                 response_text = "\n".join(response_parts)

            # == INFO PRODI UMUM (Web/Prospek) ==
            # (Logika ini tetap ada untuk info dasar, beda dengan tanya pembelajaran)
            elif top_intent == "info_prodi_sipil" or top_intent == "info_prodi_informatika" or top_intent == "info_prodi_pertambangan":
                 target_prodi = None
                 prodi_links = { # << GANTI SEMUA LINK INI >>
                      "Teknik Sipil": "[https://teknik.unanda.ac.id/teknik-sipil]",
                      "Teknik Informatika": "[https://teknik.unanda.ac.id/teknik-informatika]",
                      "Teknik Pertambangan": "[https://teknik.unanda.ac.id/teknik-pertambangan]"
                 }
                 prodi_general_info = { # Info singkat non-akademik
                      "Teknik Sipil": "Prodi ini menyiapkan lulusan untuk berkarir di bidang konstruksi, konsultan perencana/pengawas, pemerintahan (PUPR, Perhubungan), BUMN karya, dll.",
                      "Teknik Informatika": "Lulusan prodi ini banyak dicari sebagai software engineer, web developer, data scientist, network administrator, konsultan IT, dll.",
                      "Teknik Pertambangan": "Prospek kerja meliputi perusahaan pertambangan (batubara, mineral logam/industri), perusahaan jasa pertambangan, konsultan, dan instansi pemerintah (ESDM)."
                 }
                 if detected_prodi: target_prodi = detected_prodi
                 elif top_intent == "info_prodi_sipil": target_prodi = "Teknik Sipil"
                 elif top_intent == "info_prodi_informatika": target_prodi = "Teknik Informatika"
                 elif top_intent == "info_prodi_pertambangan": target_prodi = "Teknik Pertambangan"

                 if target_prodi and target_prodi in prodi_links:
                     link = prodi_links[target_prodi]
                     info = prodi_general_info.get(target_prodi, "")
                     response_text = f"{safe_user_name}, info umum Prodi {target_prodi}:\n"
                     response_text += f"- Website/Info Akademik: {link}\n"
                     if info: response_text += f"- Info Tambahan: {info}\n"
                     response_text += f"Anda bisa tanya 'apa yang dipelajari di {target_prodi}?' untuk gambaran materi kuliahnya."
                 elif target_prodi:
                     response_text = f"{safe_user_name}, maaf info umum (website/prospek) untuk Prodi {target_prodi} belum tersedia. Anda bisa cek langsung di website universitas."
                 else:
                     prodi_list = ", ".join(prodi_links.keys())
                     response_text = f"{safe_user_name}, info prodi mana yang Anda inginkan ({prodi_list})?"

            # == TANYA BIAYA PRAKTIKUM == (Logika sama seperti sebelumnya)
            elif top_intent == "tanya_biaya_praktikum":
                biaya_praktikum_info = FT_FEES.get("praktikum", {})
                response_parts = [f"Oke {safe_user_name}, terkait biaya praktikum:"]
                info = None
                lab_specified = False
                if detected_lab:
                    lab_name = detected_lab
                    lab_specified = True
                    info = biaya_praktikum_info.get(lab_name, biaya_praktikum_info.get("_default", {}))
                    response_parts.append(f"Untuk {lab_name}:")
                else:
                    info = biaya_praktikum_info.get("_default", {})
                    response_parts.append("Secara umum di Fakultas Teknik:")
                if info:
                    details = []
                    if 'amount' in info and info['amount'] is not None: details.append(f"- Biaya partisipasi utama: {format_idr(info.get('amount'))}.")
                    if 'ujian_akhir_praktikum_amount' in info and info['ujian_akhir_praktikum_amount'] is not None: details.append(f"- Biaya ujian akhir/seminar lab: {format_idr(info.get('ujian_akhir_praktikum_amount'))}.")
                    if details: response_parts.extend(details)
                    elif lab_specified: response_parts.append(f"Detail biaya spesifik untuk {lab_name} belum tersedia di sistem saya.")
                    else: response_parts.append("Detail biaya spesifik belum tersedia.")
                    response_parts.append(f"Catatan: {info.get('notes', 'Pembayaran via Aslab, konfirmasi biaya ke lab terkait.')}")
                else: response_parts.append("Maaf, info biaya praktikum belum tersedia.")
                if not lab_specified and info: response_parts.append("Anda bisa tanya biaya lab spesifik jika perlu.")
                response_text = "\n".join(filter(None, response_parts))

            # == KONTAK FT == (Sama seperti sebelumnya)
            elif top_intent == "kontak_ft":
                 response_text = f"{safe_user_name}, Anda bisa hubungi Tata Usaha (TU) Fakultas Teknik di Gedung [GANTI NAMA GEDUNG] Lantai [GANTI LANTAI]. Kontak telepon atau email bisa dicek di website resmi fakultas/universitas." # << GANTI PLACEHOLDER

            # == INFO PMB == (Handler sama seperti sebelumnya)
            elif top_intent == "info_pmb_umum":
                website = PMB_INFO.get('website', '[Website PMB belum diset]')
                response_text = (f"Informasi lengkap mengenai Penerimaan Mahasiswa Baru (PMB) Fakultas Teknik, {safe_user_name}, " f"bisa Anda akses di website resmi PMB: {website}\n\n" f"Di sana Anda bisa menemukan info jadwal, jalur pendaftaran, persyaratan, biaya, dan alur pendaftaran. " f"Apakah ada info spesifik tentang PMB yang ingin Anda tanyakan (misal: jalur, biaya awal, cara daftar)?")
            elif top_intent == "info_jalur_pmb":
                response_parts = [f"Baik {safe_user_name}, berikut jalur pendaftaran yang umumnya tersedia untuk masuk ke Fakultas Teknik:"]
                jalur_data = PMB_INFO.get('jalur', {})
                website = PMB_INFO.get('website', '[Website PMB belum diset]')
                if jalur_data:
                    for key, info in jalur_data.items(): response_parts.append(f"- **{info.get('name', key)}:** {info.get('description', 'Info detail belum tersedia.')}")
                    response_parts.append(f"\nPersyaratan detail, kuota, dan jadwal spesifik untuk tiap jalur bisa dicek langsung di website PMB: {website}")
                else: response_parts.append(f"Maaf, informasi detail mengenai jalur pendaftaran belum tersedia di sistem saya. Silakan cek langsung di {website}")
                response_text = "\n".join(response_parts)
            elif top_intent == "info_biaya_pmb":
                response_parts = [f"Oke {safe_user_name}, ini informasi biaya awal yang umumnya terkait pendaftaran mahasiswa baru (PMB):"]
                fees_data = PMB_INFO.get('fees', {})
                website = PMB_INFO.get('website', '[Website PMB belum diset]')
                if fees_data:
                    found_fee = False
                    for key, info in fees_data.items():
                        amount = info.get('amount')
                        if amount is not None:
                            response_parts.append(f"- **{info.get('name', key)}:** {format_idr(amount)}")
                            if info.get('notes'): response_parts.append(f"  *({info.get('notes')})*")
                            found_fee = True
                    if found_fee:
                        response_parts.append("\n**Penting:** Biaya ini adalah biaya awal pendaftaran dan pembekalan.")
                        response_parts.append("Biaya ini **belum termasuk** SPP/UKT semester pertama dan biaya variabel lain (seperti praktikum) yang akan dibayar setelah resmi menjadi mahasiswa.")
                        response_parts.append(f"Pastikan untuk memeriksa rincian biaya terbaru dan komponen biaya lainnya di website resmi PMB: {website}")
                    else: response_parts.append(f"Maaf, rincian biaya pendaftaran awal belum tersedia di sistem saya. Silakan cek di {website}")
                else: response_parts.append(f"Maaf, informasi biaya pendaftaran awal belum tersedia di sistem saya. Silakan cek di {website}")
                response_text = "\n".join(response_parts)
            elif top_intent == "cara_daftar_pmb":
                response_parts = [f"Siap {safe_user_name}! Berikut langkah-langkah umum untuk mendaftar sebagai mahasiswa baru Fakultas Teknik via online:"]
                steps_data = PMB_INFO.get('general_steps', [])
                website = PMB_INFO.get('website', '[Website PMB belum diset]')
                if steps_data:
                    for i, step in enumerate(steps_data): response_parts.append(f"{i+1}. {step}")
                    response_parts.append(f"\nPastikan Anda selalu memantau informasi, jadwal terbaru, dan panduan detail yang ada di website PMB resmi: {website}")
                else:
                    response_parts.append(f"Maaf, panduan langkah pendaftaran umum belum tersedia di sistem saya.")
                    response_parts.append(f"Silakan kunjungi website PMB: {website} untuk informasi dan alur pendaftaran terbaru.")
                response_text = "\n".join(response_parts)

            # === HANDLER BARU: TANYA PEMBELAJARAN PRODI ===
            elif top_intent == "tanya_pembelajaran_prodi":
                if detected_prodi:
                    prodi_info = LEARNING_CONTENT.get(detected_prodi)
                    if prodi_info and "_prodi_summary" in prodi_info:
                        response_text = f"Secara umum, di Prodi {detected_prodi}, mahasiswa akan mempelajari:\n\n{prodi_info['_prodi_summary']}"
                    else:
                        response_text = f"Maaf {safe_user_name}, deskripsi pembelajaran untuk Prodi {detected_prodi} belum tersedia secara detail di sistem saya. Anda bisa cek silabus atau kurikulum di website resmi prodi."
                else:
                    prodi_options = list(LEARNING_CONTENT.keys())
                    response_text = f"{safe_user_name}, Anda ingin tahu tentang pembelajaran di prodi mana? Pilihan yang ada: {', '.join(prodi_options)}."

            # === HANDLER BARU: TANYA PEMBELAJARAN LAB ===
            elif top_intent == "tanya_pembelajaran_lab":
                if detected_lab:
                    possible_prodi = []
                    lab_description = None
                    # Cari lab di semua prodi
                    for prodi, content in LEARNING_CONTENT.items():
                        if detected_lab in content:
                            possible_prodi.append(prodi)
                            # Jika prodi juga terdeteksi dan cocok, langsung gunakan deskripsi itu
                            if detected_prodi and detected_prodi == prodi:
                                lab_description = content[detected_lab]
                                break # Langsung pakai ini

                    if lab_description: # Deskripsi ditemukan (kasus spesifik atau unik)
                         response_text = f"Di {detected_lab} (Prodi {detected_prodi if detected_prodi in possible_prodi else possible_prodi[0]}), fokus pembelajarannya adalah:\n\n{lab_description}"
                    elif len(possible_prodi) > 1 and not detected_prodi: # Lab ditemukan di >1 prodi, tapi user tidak spesifik
                         response_text = (f"Lab '{detected_lab}' tersedia di beberapa prodi ({', '.join(possible_prodi)}). "
                                          f"Anda tertarik dengan lab ini untuk prodi mana, {safe_user_name}?")
                    elif len(possible_prodi) == 1: # Lab hanya ditemukan di 1 prodi
                         lab_description = LEARNING_CONTENT[possible_prodi[0]][detected_lab]
                         response_text = f"Di {detected_lab} (Prodi {possible_prodi[0]}), fokus pembelajarannya adalah:\n\n{lab_description}"
                    else: # Lab terdeteksi tapi tidak ada deskripsinya di LEARNING_CONTENT
                        response_text = f"Maaf {safe_user_name}, deskripsi detail tentang apa yang dipelajari di {detected_lab} belum tersedia di sistem saya. Lab ini biasanya mendukung praktikum mata kuliah terkait di prodinya."

                else: # Tidak ada lab spesifik terdeteksi
                    response_text = (f"{safe_user_name}, Anda ingin tahu tentang pembelajaran di laboratorium mana? "
                                     "Laboratorium adalah tempat praktikum untuk mendalami materi kuliah. "
                                     "Coba sebutkan nama lab spesifiknya, misalnya 'lab software' atau 'lab hidrolika'.")

            # =========================================

            else:
                # Intent dikenali tapi belum ada handler spesifik
                final_intent_category = "unhandled_valid_intent"
                response_text = f"Maaf {safe_user_name}, saya mengenali maksud Anda sebagai '{top_intent}' tapi belum punya jawaban terprogram untuk itu saat ini."

        # --- ALUR 4: Fallback (Jika Nama DIKETAHUI tapi Intent TIDAK JELAS) ---
        else:
            final_intent_category = "fallback_low_confidence"
            # Update saran fallback
            fallback_options = [
                 f"Maaf {safe_user_name}, saya masih belum mengerti maksud Anda. Bisa coba tanya tentang:\n"
                 f"- Info PMB (jalur, biaya, cara daftar)\n"
                 f"- Info Prodi (umum/pembelajaran)\n"
                 f"- Info Lab (umum/pembelajaran/biaya)\n"
                 f"- SPP, jadwal kuliah, fasilitas, kontak FT?",
                 f"Hmm {safe_user_name}, sepertinya saya kurang paham (skor: {top_score:.2f}). Bisa coba jelaskan dengan cara lain?",
                 f"Maaf {safe_user_name}, bisa diperjelas pertanyaannya tentang Fakultas Teknik, PMB, atau materi perkuliahan?",
            ]
            response_text = random.choice(fallback_options)

        # --- KEMBALIKAN HASIL (Untuk Alur 3 dan 4) ---
        return jsonify({
            "answer": response_text,
            "debug_info": {
                 "user_text": text,
                 "detected_intent": final_intent_category,
                 "intent_score": round(top_score, 3) if top_intent else 0.0,
                 "top_intent_raw": top_intent,
                 "ner_person_model": extracted_name_person,
                 "ner_prodi_rules": detected_prodi_list, # Kirim list
                 "ner_lab_rules": detected_lab_list,   # Kirim list
                 "user_name_in_session": user_name_from_session,
             }
        })

    except Exception as e:
        print(f"FATAL ERROR in /predict route: {e}")
        traceback.print_exc()
        error_message = "Maaf, sepertinya terjadi sedikit gangguan teknis di sistem saya. Silakan coba lagi beberapa saat lagi."
        user_name = session.get('user_name')
        safe_user_name_error = escape(user_name) if user_name else None
        if safe_user_name_error: error_message = f"Maaf {safe_user_name_error}, {error_message[5:]}" # Ganti 'Maaf,' dengan nama
        return jsonify({"answer": error_message, "error": "Internal Server Error"}), 500


# --- Route Lupa Nama --- (Tetap sama)
@app.route("/forget_name", methods=["POST"])
def forget_name():
    if 'user_name' in session:
        removed_name = session.pop('user_name')
        safe_removed_name = escape(removed_name)
        return jsonify({"status": "success", "message": f"Baik {safe_removed_name}, nama Anda sudah tidak saya simpan."})
    else:
        return jsonify({"status": "no_name", "message": "Saya memang belum menyimpan nama Anda."})

# --- Jalankan Server ---
if __name__ == "__main__":
    print("\n" + "="*40)
    print("       CHATBOT FAKULTAS TEKNIK SERVER")
    print(" (Tanya Nama + NER + Biaya + PMB + Pembelajaran)") # Update judul
    print("="*40)
    print(f"[*] Model Dimuat dari: '{MODEL_DIR}'")
    print(f"[*] Mode Debug: {app.debug}")
    secret_key_status = "Default (TIDAK AMAN!)" if 'ganti-ini-dengan-kunci-rahasia' in app.secret_key else "Custom/Env Var (Lebih Aman)"
    print(f"[*] Status Secret Key: {secret_key_status}")
    if 'ganti-ini-dengan-kunci-rahasia' in app.secret_key: print("    >> PERINGATAN: Ganti Flask secret_key!")

    # Perbarui pesan perhatian
    print("\n" + "!"*15 + " PERHATIAN " + "!"*15)
    print(">> PASTIKAN Anda telah mengganti SEMUA placeholder [GANTI ...]")
    print("   di dalam `app.py` (Link jadwal, web prodi, kontak, gedung, dll).")
    print(">> PASTIKAN Anda sudah melengkapi `PRODI_TERMS`, `LAB_TERMS`,")
    print("   biaya di `FT_FEES`, data `PMB_INFO`, dan deskripsi di `LEARNING_CONTENT`.") # Update ini
    print(">> PASTIKAN nama kanonis KONSISTEN antara TERMS, FT_FEES, dan LEARNING_CONTENT.")
    print(">> PASTIKAN Model sudah dilatih ulang (`python model.py`) setelah")
    print("   menambahkan/mengubah intent atau data latih (termasuk Pembelajaran).") # Update ini
    print("!"*50 + "\n")

    app.run(debug=True, port=5000)