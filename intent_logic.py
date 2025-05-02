# --- START OF FILE intent_logic.py ---

import random
import re
from markupsafe import escape

# --- Helper Functions ---
def format_idr(amount):
    """Memformat angka menjadi string Rupiah."""
    if amount is None or amount == "N/A": return "Informasi belum tersedia"
    try:
        numeric_amount = float(amount)
        # Gunakan locale atau manual format untuk memisahkan ribuan dengan titik
        # Mengganti , menjadi . untuk pemisah ribuan adalah format umum di Indonesia
        return f"Rp {numeric_amount:,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        print(f"WARNING: Gagal memformat '{amount}' sebagai Rupiah.")
        return str(amount) # Kembalikan sebagai string jika gagal

def get_safe_user_name(user_name):
    """Mengembalikan nama pengguna yang sudah di-escape atau None."""
    # Pastikan user_name adalah string sebelum escape
    if user_name is None or not isinstance(user_name, str):
        return None
    # Filter nama yang terlalu pendek atau generic
    if len(user_name.strip()) < 2 or user_name.strip().lower() in ["saya", "aku", "admin", "bot"]:
         return None
    return escape(user_name.strip())

def get_sapaan(user_name, awal_kalimat=False):
    """Menghasilkan sapaan yang sesuai (sudah di-escape)."""
    safe_name = get_safe_user_name(user_name)
    if safe_name:
        # Konsisten: Jika awal kalimat, gunakan "Baik Nama,". Jika tidak, "Nama,".
        # Tambahkan koma setelah nama jika di tengah kalimat
        return f"Baik {safe_name}" if awal_kalimat else f"{safe_name}, "
    else:
        # Jika tidak ada nama, gunakan "Baik" di awal, atau string kosong di tengah.
        return "Baik" if awal_kalimat else ""

# --- Helper Function Spesifik Jadwal (Gabungan TI, Sipil, Tambang) ---
# Menggunakan satu helper function untuk semua prodi yang datanya ada
def _get_jadwal_prodi_response(original_text_lower, prodi_name, user_name, config):
    """ Mencari dan memformat jadwal untuk prodi spesifik (TI, Sipil, Tambang)."""
    sapaan_tengah = get_sapaan(user_name)
    sapaan_awal_kalimat = get_sapaan(user_name, awal_kalimat=True)

    # Tentukan key data dan link berdasarkan nama prodi
    # Mapping nama prodi kanonikal ke key config dan short name
    prodi_mapping = {
        "Teknik Informatika": {"data_key": "JADWAL_TI_DATA", "link_key": "LINK_JADWAL_TI", "short_name": "TI"},
        "Teknik Sipil": {"data_key": "JADWAL_SIPIL_DATA", "link_key": "LINK_JADWAL_SIPIL", "short_name": "sipil"},
        "Teknik Pertambangan": {"data_key": "JADWAL_TAMBANG_DATA", "link_key": "LINK_JADWAL_TAMBANG", "short_name": "TP"}
    }

    prodi_info = prodi_mapping.get(prodi_name)

    if not prodi_info:
        # Ini seharusnya tidak terjadi jika dipanggil dari intent_logic yang sudah memfilter prodi
        # Tapi sebagai fallback safety
        return f"Maaf {sapaan_tengah}, prodi '{escape(prodi_name)}' tidak dikenali untuk pencarian jadwal spesifik.", "fallback_jadwal_unknown_prodi"

    data_key = prodi_info["data_key"]
    link_key = prodi_info["link_key"]
    prodi_short_name = prodi_info["short_name"]

    jadwal_prodi_data = config.get(data_key, {})
    link_jadwal_prodi = config.get(link_key, '')
    periode = "2024-2025" # <<-- KONFIGURASI PERIODE JADWAL DI SINI -->>

    # Check if the main data structure exists and contains the prodi's data
    if not jadwal_prodi_data or not isinstance(jadwal_prodi_data.get("jadwal_kuliah"), dict) or prodi_short_name not in jadwal_prodi_data["jadwal_kuliah"]:
        fallback_msg = ""
        if link_jadwal_prodi and "[GANTI" not in link_jadwal_prodi:
             fallback_msg = f"Anda bisa cek link ini sebagai alternatif: {link_jadwal_prodi}"
        else:
             fallback_msg = f"Silakan cek pengumuman resmi dari prodi {prodi_name}."
        return (f"Maaf {sapaan_tengah}, data jadwal kuliah **{escape(prodi_name)}** tidak dapat dimuat atau kosong saat ini. {fallback_msg}"), "fallback_jadwal_prodi_no_data"

    # Get schedule data for the specific period and prodi
    schedule_data = jadwal_prodi_data["jadwal_kuliah"].get(prodi_short_name, {}).get(periode)

    if not schedule_data or not isinstance(schedule_data, dict):
         fallback_msg = ""
         if link_jadwal_prodi and "[GANTI" not in link_jadwal_prodi:
             fallback_msg = f"Coba cek link ini: {link_jadwal_prodi}"
         else:
             fallback_msg = f"Silakan cek pengumuman resmi dari prodi {prodi_name}."
         return (f"Maaf {sapaan_tengah}, data jadwal kuliah **{escape(prodi_name)}** untuk periode {periode} belum tersedia di data saya. {fallback_msg}"), "fallback_jadwal_prodi_no_period_data"

    found_schedule = []
    search_term = None
    matched_course = None
    # Ambil nama mata kuliah dari data jadwal (keys)
    available_courses = list(schedule_data.keys())
    available_courses_lower = [name.lower() for name in available_courses]


    # 1. Cek Matkul Spesifik (dengan word boundary)
    # Iterasi melalui nama mata kuliah yang tersedia (kasus asli)
    for real_course_name in available_courses:
        course_name_lower = real_course_name.lower()
        # Cari whole word match atau frasa parsial yang signifikan
        # Gunakan regex untuk mencocokkan kata utuh atau frasa penting
        patterns_to_match = [
            r'\b' + re.escape(course_name_lower) + r'\b', # Full match
            # r'\b' + re.escape(course_name_lower.split()[0]) + r'\b.*\b' + re.escape(course_name_lower.split()[-1]) + r'\b', # First and last word
            # Tambahkan pola regex lain jika perlu untuk variasi
        ]
        if any(re.search(pattern, original_text_lower) for pattern in patterns_to_match):
             matched_course = real_course_name
             search_term = matched_course
             found_schedule.append((real_course_name, schedule_data[real_course_name]))
             break # Found the specific course


    # 2. Cek Hari Spesifik (jika tidak cari matkul)
    if not found_schedule:
        days_map = {"senin": "Senin", "selasa": "Selasa", "rabu": "Rabu",
                    "kamis": "Kamis", "jumat": "Jumat", "sabtu": "Sabtu"}
        matched_day_key = None
        # Cari pola seperti "hari senin", "jadwal senin", atau hanya "senin"
        for day_key, day_proper in days_map.items():
            # Adjusted regex to allow "jadwal senin", "senin jadwal", "hari senin", or just "senin"
             if re.search(r'\b(' + re.escape(day_key) + r'|hari\s+' + re.escape(day_key) + r'|' + re.escape(day_key) + r'\s+jadwal)\b', original_text_lower):
                matched_day_key = day_key
                search_term = f"Hari {day_proper}"
                break
        if matched_day_key:
            day_proper_case = days_map[matched_day_key]
            for course_name, details in schedule_data.items():
                # Ensure 'hari' key exists and is a string before lowercasing
                if isinstance(details.get("hari"), str) and details["hari"].lower() == day_proper_case.lower():
                    found_schedule.append((course_name, details))
            # Urutkan berdasarkan jam jika ditemukan berdasarkan hari
            found_schedule.sort(key=lambda item: item[1].get("jam", "99:99"))

    # 3. Buat Respons
    response_parts = []
    final_category = "jadwal_kuliah_ft_handled" # Default category if successful

    if found_schedule:
        if search_term:
            response_parts.append(f"{sapaan_awal_kalimat}, berikut jadwal yang saya temukan untuk **{escape(search_term)}** ({escape(prodi_name)} - Periode {periode}):\n")
        else:
             # Fallback jika ditemukan jadwal tapi search_term tidak terdeteksi (kasus jarang)
             response_parts.append(f"{sapaan_awal_kalimat}, berikut jadwal yang saya temukan ({escape(prodi_name)} - Periode {periode}):\n")


        for course_name, details in found_schedule:
            jam = details.get("jam", "N/A")
            ruang = details.get("ruang", "N/A")
            dosen = details.get("dosen", "N/A")
            hari = details.get("hari", "N/A")
            semester = details.get("semester", "N/A")
            kelas = details.get("kelas", "N/A")

            # Format berbeda jika mencari matkul spesifik vs hari
            if matched_course: # Jika mencari matkul spesifik
                 response_parts.append(f"- **{escape(course_name)}**:")
                 response_parts.append(f"  - Hari/Jam: {hari}, {jam}") # Hari dan jam tidak perlu escape jika sudah dari data terpercaya
                 response_parts.append(f"  - Ruang: {escape(str(ruang))}") # Ruang mungkin perlu escape
                 response_parts.append(f"  - Dosen: {escape(str(dosen))}") # Dosen mungkin perlu escape
                 # Hanya tampilkan kelas/semester jika ada dan valid
                 kelas_sem_info = []
                 if kelas is not None and str(kelas).strip(): kelas_sem_info.append(f"Kelas: {escape(str(kelas))}")
                 if semester is not None and str(semester).strip(): kelas_sem_info.append(f"Sem: {escape(str(semester))}")
                 if kelas_sem_info: response_parts.append(f"  - {' / '.join(kelas_sem_info)}")

            else: # Jika mencari berdasarkan hari
                 # Tampilkan info lengkap dalam satu baris atau format ringkas
                 details_parts = [f"({hari}, {jam})"] # Hari dan jam tidak perlu escape
                 if ruang is not None and str(ruang).strip(): details_parts.append(f"di R.{escape(str(ruang))}")
                 if dosen is not None and str(dosen).strip(): details_parts.append(f"Dosen: {escape(str(dosen))}")
                 # Tambahkan kelas/semester jika ada
                 kelas_sem_info = []
                 if kelas is not None and str(kelas).strip(): kelas_sem_info.append(f"Kelas: {escape(str(kelas))}")
                 if semester is not None and str(semester).strip(): kelas_sem_info.append(f"Sem: {escape(str(semester))}")
                 if kelas_sem_info: details_parts.append(f"({' / '.join(kelas_sem_info)})")

                 response_parts.append(f"- **{escape(course_name)}** {' '.join(details_parts)}") # Nama matkul perlu escape


        response_parts.append("\n*Jadwal dapat berubah, selalu konfirmasi ke prodi/dosen.*")
    else:
        # Jika tidak ada jadwal ditemukan DAN tidak ada search term (tidak cari hari/matkul)
        # Maka minta klarifikasi (implicit disambiguation / slot filling prompt)
        response_parts.append(f"{sapaan_awal_kalimat}, saya bisa bantu cek jadwal kuliah **{escape(prodi_name)}** untuk periode {periode}.")
        response_parts.append("Mohon lebih spesifik, apakah Anda ingin tahu jadwal untuk:")

        # Tawarkan contoh matkul jika ada di data (ambil 1-2 contoh)
        if available_courses:
             sample_courses = random.sample(available_courses, min(len(available_courses), 2))
             # Escape contoh mata kuliah
             response_parts.append(f"- **Mata kuliah tertentu?** (Contoh: 'jadwal {escape(random.choice(sample_courses))}')")
        else:
             response_parts.append("- **Mata kuliah tertentu?**") # Tanpa contoh jika data kosong

        response_parts.append("- **Hari tertentu?** (Contoh: 'jadwal kuliah hari senin')")

        # Tampilkan link jika tersedia dan bukan placeholder
        if link_jadwal_prodi and "[GANTI" not in link_jadwal_prodi:
            response_parts.append(f"\nAtau Anda bisa cek link jadwal lengkap (jika tersedia) di sini: {link_jadwal_prodi}")
        else:
             response_parts.append(f"\nSilakan cek juga pengumuman resmi dari prodi {prodi_name} untuk jadwal lengkap.")
        final_category = "prompt_for_jadwal_spec" # Set kategori spesifik

    return "\n".join(response_parts), final_category


def _get_spp_response(original_text_lower, detected_prodi_canonical, user_name, config):
    """Membuat respons spesifik untuk pertanyaan SPP/UKT, meminta prodi jika tidak ada."""
    spp_data = config.get('SPP_DATA', {})
    sapaan = get_sapaan(user_name, awal_kalimat=True)
    safe_user_name = get_safe_user_name(user_name)
    sapaan_tengah = get_sapaan(user_name) # Untuk ditengah kalimat

    # === LANGKAH DISAMBIGUASI / SLOT FILLING ENTITAS ===
    if not detected_prodi_canonical:
        # Prodi tidak terdeteksi, minta klarifikasi
        prodi_options = list(spp_data.keys()) # Ambil prodi yang ada di data SPP
        # Filter prodi internal seperti "_default" jika ada dan pastikan ada data di dalamnya
        prodi_display_options = [p for p in prodi_options if not p.startswith('_') and isinstance(spp_data.get(p), dict) and spp_data.get(p)]

        if prodi_display_options:
            response_text = (f"{sapaan}, untuk memberikan info SPP yang tepat, mohon sebutkan nama program studinya. "
                             f"Pilihan yang ada di data saya: **{', '.join(map(escape, prodi_display_options))}**.\n"
                             f"Contoh: 'berapa spp {escape(random.choice(prodi_display_options))}'")
            # Kembalikan tuple (respons, kategori_intent_final)
            return response_text, "prompt_for_prodi_spp"
        else:
            # Tidak ada opsi prodi di data SPP, fallback
            response_text = f"Maaf {sapaan_tengah}data SPP tidak dapat dimuat atau belum terisi dengan prodi yang valid. Mohon hubungi bagian akademik/keuangan."
            return response_text, "fallback_spp_no_data"
    # =====================================================

    # --- Lanjutkan jika prodi sudah ada ---
    if not spp_data or not isinstance(spp_data, dict):
        return f"Maaf {sapaan_tengah}data SPP tidak dapat dimuat saat ini. Mohon coba lagi nanti atau hubungi TU.", "fallback_spp_data_error"


    # Cek apakah prodi yang terdeteksi ada di data SPP
    if detected_prodi_canonical not in spp_data or not isinstance(spp_data[detected_prodi_canonical], dict):
        response_text = f"{sapaan}, mohon maaf, data SPP spesifik untuk prodi '{escape(detected_prodi_canonical)}' belum tersedia atau tidak valid di data saya. "
        # Coba berikan ringkasan prodi lain jika ada
        response_text += "\nBerikut adalah ringkasan biaya SPP (UKT) per semester Fakultas Teknik yang berlaku saat ini (periode 2023-2024) untuk prodi lain:\n"
        found_any = False
        for prodi, data in spp_data.items():
             if prodi.startswith('_') or not isinstance(data, dict): continue # Skip kunci internal atau data tidak valid
             spp_terbaru = data.get("2023-2024")
             if spp_terbaru is not None:
                 response_text += f"\n- **{escape(prodi)}**: {format_idr(spp_terbaru)}"
                 found_any = True
        if not found_any:
            response_text = f"Maaf {sapaan_tengah}saya belum memiliki informasi detail biaya SPP saat ini untuk prodi manapun. Silakan hubungi bagian akademik/keuangan."
        else:
            response_text += "\n\nUntuk info SPP prodi lain, silakan sebutkan nama prodinya."
        return response_text, "fallback_spp_prodi_not_found"

    # --- Logika utama _get_spp_response (jika prodi ada di data) ---
    response = ""
    periode_terdeteksi = None
    keywords_lama = ["angkatan 2018", "angkatan 2019", "angkatan 2020", "angkatan 2021", "angkatan 2022", "spp lama", "spp dulu"]
    keywords_baru = ["angkatan 2023", "angkatan 2024", "spp terbaru", "spp sekarang", "spp saat ini", "biaya berlaku"]
    periode_2023_2024_kws = ["2023", "2024", "terbaru", "sekarang", "saat ini"]
    periode_2018_2022_kws = ["2018", "2019", "2020", "2021", "2022", "lama", "dulu"]


    # Deteksi periode berdasarkan keyword
    if any(k in original_text_lower for k in periode_2023_2024_kws):
        periode_terdeteksi = "2023-2024"
    elif any(k in original_text_lower for k in periode_2018_2022_kws):
        periode_terdeteksi = "2018-2022"

    spp_prodi = spp_data[detected_prodi_canonical]
    target_periode = periode_terdeteksi if periode_terdeteksi else "2023-2024" # Default ke terbaru
    amount = spp_prodi.get(target_periode)

    if amount is not None:
        response = f"{sapaan}, biaya SPP/UKT untuk prodi **{escape(detected_prodi_canonical)}** periode **{target_periode}** adalah **{format_idr(amount)}** per semester."
        if not periode_terdeteksi and target_periode == "2023-2024":
            response += " (Ini adalah biaya SPP yang berlaku saat ini)."
        elif periode_terdeteksi == "2018-2022" and "2023-2024" in spp_prodi:
                amount_baru = spp_prodi.get("2023-2024")
                if amount_baru is not None: # Pastikan amount_baru ada
                    response += f"\nSebagai info, biaya SPP terbaru (periode 2023-2024) untuk prodi ini adalah **{format_idr(amount_baru)}** per semester."
    else:
        response = f"Maaf {sapaan_tengah}saya tidak memiliki data SPP untuk prodi **{escape(detected_prodi_canonical)}** pada periode **{target_periode}**. "
        spp_terbaru = spp_prodi.get("2023-2024")
        if spp_terbaru is not None: # Pastikan spp_terbaru ada
            response += f"Biaya SPP yang berlaku saat ini (periode 2023-2024) untuk **{escape(detected_prodi_canonical)}** adalah **{format_idr(spp_terbaru)}** per semester."
        else:
            response += f"Informasi SPP terbaru untuk **{escape(detected_prodi_canonical)}** juga belum tersedia di data saya."

    return response.strip(), "info_spp_ft_handled" # Kembalikan kategori asli jika berhasil


# def _get_jadwal_ti_response(...): <-- REMOVED, USING _get_jadwal_prodi_response INSTEAD

# --- Main Intent Logic Function ---

def get_response_for_intent(nlu_result, user_name, original_text, config):
    """
    Menghasilkan teks respons berdasarkan intent yang terdeteksi.
    Menggunakan data dari dictionary 'config'.
    Meminta klarifikasi jika entitas wajib hilang.
    Mengembalikan tuple: (response_text, final_intent_category)
    """
    intent = nlu_result.get('intent')
    score = nlu_result.get('score', 0.0)
    entities = nlu_result.get('entities', {})
    detected_prodi_list = entities.get("PRODI", [])
    detected_lab_list = entities.get("LAB", [])
    # Ambil yang pertama jika ada, jika tidak None
    detected_prodi = detected_prodi_list[0] if detected_prodi_list else None
    detected_lab = detected_lab_list[0] if detected_lab_list else None

    sapaan_untuk_user = get_sapaan(user_name) # Sapaan tengah kalimat
    sapaan_awal_kalimat = get_sapaan(user_name, awal_kalimat=True)
    safe_user_name = get_safe_user_name(user_name)

    # Ambil data dan konfigurasi
    confidence_threshold = config.get('CONFIDENCE_THRESHOLD', 0.5)
    link_jadwal_ti = config.get('LINK_JADWAL_TI', '')
    link_jadwal_sipil = config.get('LINK_JADWAL_SIPIL', '')
    link_jadwal_tambang = config.get('LINK_JADWAL_TAMBANG', '')
    link_jadwal_umum_ft = config.get('LINK_JADWAL_UMUM_FT', '')
    link_prodi_sipil = config.get('LINK_PRODI_SIPIL', '')
    link_prodi_informatika = config.get('LINK_PRODI_INFORMATIKA', '')
    link_prodi_tambang = config.get('LINK_PRODI_TAMBANG', '')
    kontak_tu_info = config.get('KONTAK_TU_INFO', 'Informasi kontak TU belum tersedia.')
    krs_sevima_guide = config.get('KRS_SEVIMA_GUIDE', '')
    payment_sevima_tokopedia_guide = config.get('PAYMENT_SEVIMA_TOKOPEDIA_GUIDE', '')
    ft_fees = config.get('FT_FEES', {})
    pmb_info = config.get('PMB_INFO', {})
    learning_content = config.get('LEARNING_CONTENT', {})
    # spp_data sudah diambil di helper spp
    # jadwal_ti_data, jadwal_sipil_data, jadwal_tambang_data diambil di helper jadwal
    lab_terms = config.get('TERMS_DATA', {}).get('lab', {}) # Ambil terms jika perlu
    prodi_terms = config.get('TERMS_DATA', {}).get('prodi', {}) # Ambil terms jika perlu

    # Default response
    response_text = f"Maaf {sapaan_untuk_user}saya belum bisa memproses permintaan terkait '{intent}' saat ini. Mungkin bisa coba tanyakan dengan cara lain?"
    final_intent_category = intent if intent else "unhandled_intent" # Default kategori


    # --- Logika Respons per Intent ---
    # Hanya proses intent yang dikenali dengan skor di atas threshold
    if intent and score >= confidence_threshold:
        # Set kategori default berdasarkan intent yang terdeteksi (akan di-override jika perlu)
        final_intent_category = intent

        # --- Intent Handling ---
        if intent == "greeting_ft":
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
            final_intent_category = "greeting_ft_handled"

        elif intent == "goodbye_ft":
            response_text = random.choice([
                f"{sapaan_awal_kalimat}, sampai jumpa!",
                "Sampai jumpa!",
                "Senang bisa membantu. Jika ada lagi, jangan ragu bertanya.",
                "Terima kasih telah bertanya!"
                ])
            final_intent_category = "goodbye_ft_handled"

        elif intent == "thankyou_ft":
            response_text = random.choice([
                f"Sama-sama, {safe_user_name}!" if safe_user_name else "Sama-sama!",
                "Dengan senang hati!",
                "Tidak masalah!",
                "Senang bisa membantu!"
                ])
            final_intent_category = "thankyou_ft_handled"

        elif intent == "ask_bot_identity":
             response_text = ("Saya adalah chatbot Fakultas Teknik Universitas Andi Djemma. "
                              "Saya dirancang untuk membantu memberikan informasi seputar fakultas, "
                              "Penerimaan Mahasiswa Baru (PMB), biaya kuliah (SPP, praktikum), "
                              "informasi prodi & lab, jadwal kuliah, panduan KRS dan pembayaran, serta kontak. "
                              "Ada yang bisa saya bantu?")
             final_intent_category = "ask_bot_identity_handled"

        elif intent == "info_biaya_umum":
            # Ini sudah merupakan bentuk disambiguasi, tidak perlu diubah
            final_intent_category = "disambiguate_cost" # Override kategori
            response_text = (f"{sapaan_awal_kalimat}. Saya bisa bantu informasi biaya di Fakultas Teknik. "
                             "Jenis biaya apa yang spesifik Anda maksud?\n\n"
                             "1. **SPP** (Biaya kuliah per semester)\n"
                             "2. **Praktikum/Laboratorium** (Biaya kegiatan di lab)\n"
                             "3. **Pendaftaran Mahasiswa Baru (PMB)** (Biaya formulir, tes, orientasi awal, dll.)\n\n"
                             "Silakan sebutkan jenisnya (misal: 'info SPP', 'biaya praktikum', atau 'biaya PMB').")

        elif intent == "info_spp_ft":
            # Panggil helper yang sudah dimodifikasi untuk slot filling
            response_text, final_intent_category = _get_spp_response(
                original_text.lower(), detected_prodi, user_name, config
            )

        elif intent == "cara_bayar_spp_ft":
             response_text = (f"{sapaan_awal_kalimat}. Untuk pembayaran SPP/UKT (setelah Anda resmi menjadi mahasiswa), "
                              "biasanya dilakukan melalui sistem akademik online Sevima/SIAKAD Cloud. "
                              "Apakah Anda ingin tahu:\n"
                              "1. **Panduan bayar via Tokopedia** (jika tersedia)?\n"
                              "2. **Informasi metode pembayaran lain** (misal transfer bank)?\n"
                              "3. **Batas waktu pembayaran** semester ini?\n\n"
                              "Mohon konfirmasi ke bagian keuangan atau cek pengumuman resmi fakultas/universitas "
                              "untuk detail metode pembayaran yang valid dan jadwalnya.")
             if payment_sevima_tokopedia_guide and "tidak ditemukan" not in payment_sevima_tokopedia_guide:
                 response_text += "\n\nJika ingin panduan pembayaran via Tokopedia, ketik 'cara bayar sevima tokopedia'."
             final_intent_category = "cara_bayar_spp_ft_prompt"


        elif intent == "cara_bayar_sevima_tokopedia":
             if payment_sevima_tokopedia_guide and "tidak ditemukan" not in payment_sevima_tokopedia_guide:
                  response_text = (f"{sapaan_awal_kalimat}, ini panduan umum membayar uang kuliah melalui Sevima Pay "
                                   f"di platform Tokopedia:\n\n{payment_sevima_tokopedia_guide}\n\n"
                                   "**Penting:** Pastikan Anda mengikuti langkah-langkah ini dengan benar, "
                                   "memilih tagihan yang sesuai, dan membayar sebelum batas waktu yang ditentukan. "
                                   "Simpan bukti pembayaran Anda.")
                  final_intent_category = "cara_bayar_sevima_tokopedia_handled"
             else:
                 response_text = (f"Maaf {sapaan_untuk_user}, panduan spesifik pembayaran via Tokopedia belum tersedia di data saya. "
                                  "Silakan cek pengumuman resmi dari bagian keuangan atau universitas mengenai metode pembayaran yang tersedia.")
                 final_intent_category = "fallback_payment_guide_missing"

        elif intent == "info_krs_sevima":
             if krs_sevima_guide and "tidak ditemukan" not in krs_sevima_guide:
                  response_text = (f"{sapaan_awal_kalimat}, berikut panduan umum pengisian Kartu Rencana Studi (KRS) "
                                   f"di sistem Sevima/SIAKAD Cloud:\n\n{krs_sevima_guide}\n\n"
                                   "**Ingat:** Selalu perhatikan **jadwal resmi pengisian KRS** yang dikeluarkan oleh fakultas/universitas. "
                                   "Jika ada mata kuliah yang tidak muncul, error, atau Anda ragu, segera konsultasikan "
                                   "dengan **Dosen Pembimbing Akademik (PA)** Anda atau bagian akademik.")
                  final_intent_category = "info_krs_sevima_handled"
             else:
                 response_text = (f"Maaf {sapaan_untuk_user}, panduan pengisian KRS via Sevima belum tersedia di data saya. "
                                  "Secara umum, Anda perlu login ke sistem SIAKAD/Sevima pada jadwal yang ditentukan, "
                                  "memilih mata kuliah yang akan diambil sesuai dengan semester dan kurikulum Anda, "
                                  "lalu menyimpannya. Pastikan status KRS Anda disetujui oleh Dosen PA. "
                                  "Untuk panduan detail, silakan cek sumber informasi resmi dari kampus.")
                 final_intent_category = "fallback_krs_guide_missing"


        elif intent == "jadwal_kuliah_ft":
            # Mapping prodi yang didukung untuk pencarian jadwal spesifik
            supported_jadwal_prodi = {
                 "Teknik Informatika": config.get('JADWAL_TI_DATA'),
                 "Teknik Sipil": config.get('JADWAL_SIPIL_DATA'),
                 "Teknik Pertambangan": config.get('JADWAL_TAMBANG_DATA'),
            }
            # Filter prodi yang datanya benar-benar ada dan tidak kosong
            # Check if data exists, is a dictionary, contains "jadwal_kuliah", and that key is also a dictionary
            available_jadwal_prodi = {
                p: data for p, data in supported_jadwal_prodi.items()
                if data and isinstance(data, dict) and isinstance(data.get("jadwal_kuliah"), dict) and data["jadwal_kuliah"]
            }


            if detected_prodi and detected_prodi in available_jadwal_prodi:
                # Panggil helper jadwal umum untuk prodi yang terdeteksi
                response_text, final_intent_category = _get_jadwal_prodi_response(
                    original_text.lower(), detected_prodi, user_name, config
                )
            else:
                # Logika untuk prodi lain atau jika prodi tidak terdeteksi ATAU data jadwalnya tidak ada
                base_response = f"{sapaan_awal_kalimat}. Untuk jadwal kuliah Fakultas Teknik semester ini, "
                links_found = []
                specific_prodi_link_handled = False # Flag untuk menandai jika sudah menawarkan link spesifik prodi yang terdeteksi

                # Coba cari link prodi yang terdeteksi (jika ada)
                if detected_prodi:
                    base_response += f"khususnya untuk **{escape(detected_prodi)}**, "
                    prodi_link_key = f"LINK_JADWAL_{detected_prodi.replace('Teknik ', '').upper()}"
                    prodi_specific_link = config.get(prodi_link_key)
                    # Pastikan link bukan placeholder
                    if prodi_specific_link and "[GANTI" not in prodi_specific_link and "http" in prodi_specific_link:
                        links_found.append(f"- **{escape(detected_prodi)}**: {prodi_specific_link}")
                        specific_prodi_link_handled = True

                    if not specific_prodi_link_handled:
                         base_response += "saya belum punya link jadwal spesifiknya. "
                    else:
                         base_response += "berikut link yang mungkin relevan:\n"

                # Jika tidak ada prodi terdeteksi ATAU link spesifik tidak ketemu, tawarkan semua link
                if not detected_prodi or not specific_prodi_link_handled:
                    if not detected_prodi:
                        base_response += "berikut link jadwal yang mungkin relevan untuk beberapa prodi:\n"
                    else: # Link spesifik prodi tidak ada, tawarkan yang lain
                         base_response += "Namun, Anda bisa cek link prodi lain atau link umum berikut:\n"

                    # Tambahkan link untuk prodi yang didukung, kecuali yang sudah ditambahkan
                    # Pastikan link bukan placeholder
                    if detected_prodi != "Teknik Informatika" and link_jadwal_ti and "[GANTI" not in link_jadwal_ti and "http" in link_jadwal_ti: links_found.append(f"- **Teknik Informatika**: {link_jadwal_ti}")
                    if detected_prodi != "Teknik Sipil" and link_jadwal_sipil and "[GANTI" not in link_jadwal_sipil and "http" in link_jadwal_sipil: links_found.append(f"- **Teknik Sipil**: {link_jadwal_sipil}")
                    if detected_prodi != "Teknik Pertambangan" and link_jadwal_tambang and "[GANTI" not in link_jadwal_tambang and "http" in link_jadwal_tambang: links_found.append(f"- **Teknik Pertambangan**: {link_jadwal_tambang}")
                    if link_jadwal_umum_ft and "[GANTI" not in link_jadwal_umum_ft and "http" in link_jadwal_umum_ft: links_found.append(f"- **Umum Fakultas**: {link_jadwal_umum_ft}")


                if links_found:
                    response_text = base_response + "\n".join(links_found)
                    response_text += "\n\nJadwal biasanya dibagikan oleh masing-masing prodi. Anda juga bisa cek pengumuman di grup mahasiswa atau sistem Sevima/SIAKAD."
                    # Tawarkan bantuan untuk prodi jika datanya ada (menggunakan helper _get_jadwal_prodi_response)
                    offer_detail_help_prodi = [p for p in available_jadwal_prodi.keys()]
                    if offer_detail_help_prodi:
                         response_text += f"\nUntuk {' atau '.join(map(escape, offer_detail_help_prodi))}, saya bisa coba bantu cek jadwal mata kuliah atau hari tertentu jika Anda bertanya lebih spesifik."

                    final_intent_category = "jadwal_kuliah_ft_links_provided"
                else:
                    # Tidak ada link sama sekali DAN tidak ada data jadwal spesifik
                    response_text = (f"Maaf {sapaan_untuk_user}, saya belum memiliki data atau link jadwal kuliah yang bisa dibagikan saat ini. "
                                     "Silakan cek pengumuman resmi dari prodi Anda, grup mahasiswa, atau sistem Sevima/SIAKAD. "
                                     "Jadwal biasanya keluar mendekati awal semester.")
                    # Tawarkan bantuan untuk prodi jika datanya ada (walaupun tidak ada link)
                    offer_detail_help_prodi = [p for p in available_jadwal_prodi.keys()]
                    if offer_detail_help_prodi:
                         response_text += f"\nJika Anda mahasiswa {' atau '.join(map(escape, offer_detail_help_prodi))}, saya bisa coba bantu cek jadwal mata kuliah atau hari tertentu jika Anda bertanya lebih spesifik."

                    final_intent_category = "fallback_jadwal_links_missing"


        elif intent == "fasilitas_umum_ft":
            response_text = (f"{sapaan_awal_kalimat}. Fasilitas umum yang tersedia di lingkungan Fakultas Teknik UNANDA antara lain:\n"
                             "- Ruang kuliah yang dilengkapi AC dan LCD Proyektor.\n"
                             "- Jaringan WiFi di beberapa area kampus.\n"
                             "- Perpustakaan fakultas/universitas.\n"
                             "- Laboratorium komputer dan laboratorium spesifik per prodi.\n"
                             "- Area diskusi mahasiswa.\n"
                             "- Kantin atau area jajan terdekat.\n"
                             "- Mushola/Tempat ibadah.\n"
                             "- Toilet.\n\n"
                             "Untuk detail fasilitas laboratorium spesifik prodi, Anda bisa tanyakan misalnya 'info lab informatika'.")
            final_intent_category = "fasilitas_umum_ft_handled"

        elif intent.startswith("info_lab_") or (detected_lab and intent not in ["tanya_pembelajaran_lab", "tanya_biaya_praktikum"]):
            # Mapping intent spesifik lab ke nama prodi kanonikal
            intent_prodi_mapping = {
                 "info_lab_sipil": "Teknik Sipil",
                 "info_lab_informatika": "Teknik Informatika",
                 "info_lab_pertambangan": "Teknik Pertambangan"
            }
            target_prodi_from_intent = intent_prodi_mapping.get(intent)
            target_prodi = detected_prodi or target_prodi_from_intent # Prioritaskan prodi dari NLU

            response_parts = [f"{sapaan_awal_kalimat}. Mengenai laboratorium di Fakultas Teknik:"]
            has_learning_data = bool(learning_content and isinstance(learning_content, dict)) # Check if learning_content is a non-empty dict
            has_fee_data = bool(ft_fees and isinstance(ft_fees.get("praktikum"), dict) and ft_fees["praktikum"]) # Check if praktikum key exists and is a non-empty dict

            if not has_learning_data and not has_fee_data and not detected_lab:
                 response_parts.append("Maaf, informasi detail mengenai laboratorium (materi atau biaya) tidak dapat dimuat saat ini.")
                 final_intent_category = "fallback_lab_data_missing"
            else:
                # Jika tanya spesifik LAB tapi tidak terdeteksi PRODI, coba cari prodi pemilik lab
                if detected_lab and not target_prodi and has_learning_data:
                    for p, labs in learning_content.items():
                        if isinstance(labs, dict) and detected_lab in labs:
                             target_prodi = p # Assign the first prodi found owning this lab
                             break

                if target_prodi:
                    response_parts.append(f"\n**Untuk Prodi {escape(target_prodi)}:**")
                    labs_in_prodi = []
                    if has_learning_data and target_prodi in learning_content and isinstance(learning_content[target_prodi], dict):
                        # Ambil nama lab yang valid (bukan _*)
                        labs_in_prodi = [lab for lab in learning_content[target_prodi] if not lab.startswith("_")]

                    if detected_lab and detected_lab in labs_in_prodi:
                        # Info spesifik LAB yang diminta
                        response_parts.append(f"- Fokus pada: **{escape(detected_lab)}**.")
                        # Tambahkan info biaya jika ada
                        if has_fee_data:
                             biaya_praktikum_info = ft_fees.get("praktikum", {})
                             fee_info = biaya_praktikum_info.get(detected_lab, biaya_praktikum_info.get("_default"))
                             if fee_info and isinstance(fee_info, dict):
                                 biaya_partisipasi = fee_info.get('amount')
                                 biaya_ujian = fee_info.get('ujian_akhir_praktikum_amount')
                                 notes = fee_info.get('notes', '')
                                 biaya_text_parts = []
                                 if biaya_partisipasi is not None: biaya_text_parts.append(f"Biaya partisipasi sekitar **{format_idr(biaya_partisipasi)}**")
                                 if biaya_ujian is not None and biaya_ujian != 0: biaya_text_parts.append(f"biaya ujian akhir sekitar **{format_idr(biaya_ujian)}**")

                                 if biaya_text_parts: response_parts.append(f"  Biaya praktikum: {', ditambah '.join(biaya_text_parts)}.")
                                 else: response_parts.append("  Informasi komponen biaya praktikum ini belum tersedia.")

                                 if notes: response_parts.append(f"  *Catatan: {notes}*")
                             else: response_parts.append("  Informasi biaya spesifik lab ini belum tersedia.")

                        # Tambahkan ajakan tanya pembelajaran jika ada datanya
                        if has_learning_data and detected_lab in learning_content.get(target_prodi, {}) and learning_content[target_prodi][detected_lab] and isinstance(learning_content[target_prodi][detected_lab], str) and learning_content[target_prodi][detected_lab].strip():
                            response_parts.append(f"  Anda bisa tanya 'apa yang dipelajari di {escape(detected_lab)}?'")
                        final_intent_category = "info_lab_specific_handled"

                    elif labs_in_prodi:
                        # Info umum LAB untuk PRODI yang diminta (karena lab spesifik tidak diminta/ditemukan)
                        response_parts.append(f"  Terdapat beberapa laboratorium utama, antara lain: **{', '.join(map(escape, labs_in_prodi))}**.")
                        # Tampilkan biaya umum jika ada
                        if has_fee_data:
                             biaya_praktikum_info = ft_fees.get("praktikum", {})
                             fee_info = biaya_praktikum_info.get("_default")
                             if fee_info and isinstance(fee_info, dict):
                                 biaya_partisipasi = fee_info.get('amount')
                                 biaya_ujian = fee_info.get('ujian_akhir_praktikum_amount')
                                 notes = fee_info.get('notes', '')
                                 biaya_text_parts = []
                                 if biaya_partisipasi is not None: biaya_text_parts.append(f"biaya partisipasi sekitar **{format_idr(biaya_partisipasi)}**")
                                 if biaya_ujian is not None and biaya_ujian != 0: biaya_text_parts.append(f"biaya ujian akhir sekitar **{format_idr(biaya_ujian)}**")

                                 if biaya_text_parts: response_parts.append(f"  Biaya praktikum umumnya sekitar {', ditambah '.join(biaya_text_parts)}.")
                                 else: response_parts.append("  Informasi komponen biaya praktikum umum belum tersedia.")

                                 if notes: response_parts.append(f"  *Catatan umum: {notes}*")

                        response_parts.append("  Anda bisa tanya info lebih detail tentang lab spesifik (misal: 'info lab software' atau 'biaya lab hidrolika').")
                        final_intent_category = "info_lab_prodi_list_handled"
                    else:
                        response_parts.append(f"  Maaf, daftar laboratorium spesifik untuk Prodi {escape(target_prodi)} belum tersedia di data saya.")
                        final_intent_category = "fallback_lab_list_missing"
                else:
                    # Tidak ada prodi terdeteksi sama sekali (baik dari intent atau NLU)
                    # Ambil dari terms di config dan pastikan terms_data valid
                    all_labs_options = list(lab_terms.keys()) if lab_terms and isinstance(lab_terms, dict) else []
                    if all_labs_options:
                       response_parts.append("\nFakultas Teknik memiliki berbagai laboratorium untuk mendukung pembelajaran.")
                       display_count = min(len(all_labs_options), 5)
                       contoh_labs = random.sample(all_labs_options, display_count)
                       response_parts.append(f"Beberapa di antaranya: **{', '.join(map(escape, contoh_labs))}**{ '...' if len(all_labs_options) > display_count else '.'}")

                       # Tampilkan biaya umum jika ada
                       if has_fee_data:
                            biaya_praktikum_info = ft_fees.get("praktikum", {})
                            fee_info = biaya_praktikum_info.get("_default")
                            if fee_info and isinstance(fee_info, dict):
                                 biaya_partisipasi = fee_info.get('amount')
                                 biaya_ujian = fee_info.get('ujian_akhir_praktikum_amount')
                                 notes = fee_info.get('notes', '')
                                 biaya_text_parts = []
                                 if biaya_partisipasi is not None: biaya_text_parts.append(f"Biaya partisipasi sekitar **{format_idr(biaya_partisipasi)}**")
                                 if biaya_ujian is not None and biaya_ujian != 0: biaya_text_parts.append(f"biaya ujian akhir sekitar **{format_idr(biaya_ujian)}**")

                                 if biaya_text_parts: response_parts.append(f"\nBiaya praktikum umumnya sekitar {', ditambah '.join(biaya_text_parts)}.")
                                 else: response_parts.append("\nInformasi komponen biaya praktikum umum belum tersedia.")

                                 if notes: response_parts.append(f"*Catatan umum: {notes}*")

                       response_parts.append("\nApakah ada laboratorium spesifik atau dari prodi tertentu yang ingin Anda ketahui lebih lanjut? (Contoh: 'info lab sipil' atau 'lab software')")
                       final_intent_category = "info_lab_general_prompt"
                    else:
                       response_parts.append("\nMaaf, informasi umum mengenai laboratorium belum tersedia saat ini.")
                       final_intent_category = "fallback_lab_terms_missing"


            response_text = "\n".join(response_parts)


        elif intent.startswith("info_prodi_"):
            # Mapping intent spesifik prodi ke nama prodi kanonikal
            intent_prodi_mapping = {
                 "info_prodi_sipil": "Teknik Sipil",
                 "info_prodi_informatika": "Teknik Informatika",
                 "info_prodi_pertambangan": "Teknik Pertambangan"
            }
            target_prodi_intent = intent_prodi_mapping.get(intent)
            target_prodi = detected_prodi or target_prodi_intent # Prioritaskan NLU

            prodi_links = {
                 "Teknik Sipil": link_prodi_sipil,
                 "Teknik Informatika": link_prodi_informatika,
                 "Teknik Pertambangan": link_prodi_tambang
            }
            # Deskripsi singkat bisa ditaruh di config atau data tersendiri nanti
            # Menggunakan data dari learning_content jika ada summary prodi
            prodi_general_info = {
                 "Teknik Sipil": learning_content.get("Teknik Sipil", {}).get("_prodi_summary", "Fokus pada perancangan, pembangunan, dan pemeliharaan infrastruktur seperti gedung, jembatan, jalan, dan sistem air."),
                 "Teknik Informatika": learning_content.get("Teknik Informatika", {}).get("_prodi_summary", "Mempelajari dasar-dasar ilmu komputer, pengembangan perangkat lunak (software), jaringan komputer, kecerdasan buatan, dan manajemen data."),
                 "Teknik Pertambangan": learning_content.get("Teknik Pertambangan", {}).get("_prodi_summary", "Berkaitan dengan eksplorasi, penambangan (ekstraksi), dan pengolahan sumber daya mineral dan batubara secara efisien dan aman.")
            }


            # Ambil daftar prodi yang tersedia di terms data (atau prodi_links jika terms kosong)
            available_prodi_list = list(prodi_terms.keys()) if prodi_terms and isinstance(prodi_terms, dict) else list(prodi_links.keys())


            if target_prodi and target_prodi in available_prodi_list: # Check if detected prodi is in our known list
                link = prodi_links.get(target_prodi)
                info = prodi_general_info.get(target_prodi, "") # Gunakan .get() untuk default jika tidak ada

                response_text = f"{sapaan_awal_kalimat}. Berikut informasi umum mengenai **Prodi {escape(target_prodi)}**:"
                if info: response_text += f"\n\n- **Fokus Utama**: {escape(info)}" # Escape info
                if link and "[GANTI" not in link and "http" in link:
                    response_text += f"\n- **Website/Info Lengkap**: {link}"
                else:
                     response_text += f"\n- Website Prodi: (Link belum tersedia atau belum diganti)"

                # Cek apakah ada data SPP untuk prodi ini
                if config.get('SPP_DATA') and isinstance(config['SPP_DATA'], dict) and target_prodi in config['SPP_DATA']:
                     response_text += f"\n\nUntuk biaya kuliah, Anda bisa tanya 'berapa spp {escape(target_prodi)}?'."
                # Cek apakah ada data jadwal spesifik untuk prodi ini
                jadwal_prodi_key = f"JADWAL_{target_prodi.replace('Teknik ', '').upper()}_DATA"
                # Check if data exists, is a dictionary, contains "jadwal_kuliah", and that key is also a dictionary
                if config.get(jadwal_prodi_key) and isinstance(config.get(jadwal_prodi_key), dict) and isinstance(config.get(jadwal_prodi_key).get("jadwal_kuliah"), dict) and config.get(jadwal_prodi_key).get("jadwal_kuliah"):
                     response_text += f"\nUntuk jadwal kuliah, saya bisa coba cek detail mata kuliah atau hari tertentu jika Anda bertanya lebih spesifik (misal: 'jadwal {escape(target_prodi.replace('Teknik ', ''))} hari senin')."


                # Cek apakah ada data pembelajaran lab spesifik untuk prodi ini
                labs_in_prodi_with_learning = []
                if learning_content and isinstance(learning_content, dict) and target_prodi in learning_content and isinstance(learning_content[target_prodi], dict):
                     labs_in_prodi_with_learning = [lab for lab in learning_content[target_prodi] if not lab.startswith("_") and learning_content[target_prodi].get(lab) and isinstance(learning_content[target_prodi].get(lab), str) and learning_content[target_prodi].get(lab).strip()]

                if labs_in_prodi_with_learning:
                     response_text += f"\n\nAnda juga bisa tanya informasi mengenai lab spesifik di prodi ini (misal: 'info lab {escape(random.choice(labs_in_prodi_with_learning))}') atau materi pembelajarannya ('apa yang dipelajari di lab {escape(random.choice(labs_in_prodi_with_learning))}?')."


                final_intent_category = f"info_prodi_{target_prodi.split()[1].lower()}_handled" # e.g., info_prodi_informatika_handled

            elif target_prodi: # Detected prodi but not in our list of available info
                 response_text = f"{sapaan_untuk_user}Maaf, informasi umum untuk Prodi {escape(target_prodi)} belum tersedia lengkap di data saya. "
                 if link_prodi_informatika or link_prodi_sipil or link_prodi_tambang:
                      response_text += "Anda bisa coba cek langsung di website Fakultas Teknik UNANDA atau bertanya tentang topik lain."
                 else:
                      response_text += "Anda bisa coba cek langsung di website resmi UNANDA atau bertanya tentang topik lain."

                 final_intent_category = "fallback_prodi_info_missing"

            else: # No prodi detected or intent was just info_prodi_
                if available_prodi_list:
                     response_text = f"{sapaan_awal_kalimat}. Fakultas Teknik UNANDA saat ini memiliki program studi: **{', '.join(map(escape, available_prodi_list))}**. Prodi mana yang spesifik ingin Anda ketahui informasinya? (Contoh: 'info prodi sipil')"
                     final_intent_category = "prompt_for_prodi_general"
                else:
                     response_text = f"{sapaan_untuk_user}Maaf, daftar program studi di Fakultas Teknik belum tersedia di data saya."
                     final_intent_category = "fallback_prodi_list_missing"


            response_text = "\n".join(filter(None, response_text.split('\n'))) # Clean up empty lines


        elif intent == "tanya_biaya_praktikum":
            # === DISAMBIGUASI / SLOT FILLING ===
            # Ambil daftar lab yang memiliki info biaya (spesifik atau default)
            labs_with_fee_info = []
            if ft_fees and isinstance(ft_fees.get("praktikum"), dict) and ft_fees["praktikum"]:
                 praktikum_fees_data = ft_fees["praktikum"]
                 labs_with_fee_info = [lab for lab in praktikum_fees_data.keys() if not lab.startswith("_")]
                 # Tambahkan "_default" jika ada info default
                 if "_default" in praktikum_fees_data and isinstance(praktikum_fees_data["_default"], dict) and praktikum_fees_data["_default"]:
                     labs_with_fee_info.append("umum/default") # Representasi untuk info umum

            if not detected_lab:
                 if labs_with_fee_info:
                     # Gunakan set untuk unik, lalu kembali ke list untuk random sample
                     contoh_lab_list = list(set(labs_with_fee_info))
                     contoh_display = random.sample(contoh_lab_list, min(len(contoh_lab_list), 3))
                     response_text = (f"{sapaan_awal_kalimat}, untuk memberikan informasi biaya praktikum yang lebih akurat, "
                                      f"mohon sebutkan nama laboratorium spesifiknya.\n"
                                      f"Beberapa lab yang ada info biayanya (atau info umum): **{', '.join(map(escape, contoh_display))}**{ '...' if len(labs_with_fee_info) > len(contoh_display) else '.'}"
                                      f"\nContoh pertanyaan: 'biaya praktikum {escape(random.choice(contoh_display))}'")
                     final_intent_category = "prompt_for_lab_fee"
                 else:
                     response_text = f"{sapaan_untuk_user}Maaf, saya belum punya daftar laboratorium dengan informasi biaya praktikum. Silakan hubungi bagian akademik/lab terkait."
                     final_intent_category = "fallback_lab_terms_missing_for_fee"
            # =====================================
            elif not ft_fees or not isinstance(ft_fees.get("praktikum"), dict) or not ft_fees["praktikum"]:
                response_text = f"Maaf {sapaan_untuk_user}, informasi biaya praktikum tidak dapat dimuat saat ini. Silakan hubungi laboratorium terkait atau bagian akademik."
                final_intent_category = "fallback_fee_data_missing"
            else:
                # Logika asli jika lab terdeteksi dan data biaya ada
                biaya_praktikum_info = ft_fees["praktikum"]
                response_parts = [f"{sapaan_awal_kalimat}, terkait biaya praktikum di Fakultas Teknik:"]
                info = None
                lab_name = detected_lab # Lab sudah pasti ada karena sudah melewati cek `if not detected_lab`

                # Cari info spesifik lab, fallback ke default jika tidak ada
                info = biaya_praktikum_info.get(lab_name, biaya_praktikum_info.get("_default"))

                if info and isinstance(info, dict): # Pastikan info yang ditemukan adalah dictionary
                    if lab_name in biaya_praktikum_info: response_parts.append(f"\nUntuk praktikum **{escape(lab_name)}**:")
                    elif "_default" in biaya_praktikum_info and info is biaya_praktikum_info["_default"]: response_parts.append(f"\nUntuk praktikum **{escape(lab_name)}** (menggunakan info biaya umum):")
                    else: response_parts.append(f"\nInformasi biaya untuk **{escape(lab_name)}** ditemukan, tetapi tidak spesifik lab ini."); # Fallback jika ada info tapi bukan spesifik/default
                    # Kalaupun tidak ada info spesifik atau default, akan masuk sini jika info tidak None (kasus aneh)

                    details = []
                    biaya_partisipasi = info.get('amount')
                    biaya_ujian = info.get('ujian_akhir_praktikum_amount')
                    notes = info.get('notes', 'Biaya dapat berubah, mohon konfirmasi ke lab/akademik.')

                    biaya_text_parts = []
                    if biaya_partisipasi is not None: biaya_text_parts.append(f"Biaya partisipasi/modul utama: **{format_idr(biaya_partisipasi)}**")
                    if biaya_ujian is not None and biaya_ujian != 0: biaya_text_parts.append(f"biaya ujian akhir praktikum (jika ada): **{format_idr(biaya_ujian)}**")

                    if biaya_text_parts: response_parts.append(f"- {', ditambah '.join(biaya_text_parts)}.")
                    else: response_parts.append("- Detail komponen biaya (partisipasi/ujian) belum tersedia.")

                    if notes: response_parts.append(f"- *Catatan: {notes}*")
                    final_intent_category = "tanya_biaya_praktikum_handled"
                else:
                     # Jika info tidak ketemu atau formatnya salah
                     response_parts.append(f"\nMaaf, informasi detail biaya praktikum untuk **{escape(lab_name)}** belum tersedia atau tidak valid di data saya.")
                     final_intent_category = "fallback_lab_fee_details_missing"


                response_text = "\n".join(filter(None, response_parts))


        elif intent == "kontak_ft":
             if "[GANTI" in kontak_tu_info:
                 response_text = (f"{sapaan_untuk_user}Informasi kontak Tata Usaha (TU) belum lengkap di data saya. "
                                  "Anda bisa coba cek langsung di website resmi Fakultas Teknik UNANDA untuk informasi kontak terbaru.")
                 final_intent_category = "fallback_kontak_placeholder"
             else:
                  response_text = f"{sapaan_awal_kalimat}. {kontak_tu_info}" # Mulai dengan Baik Nama, ...
                  final_intent_category = "kontak_ft_handled"


        # --- Handler PMB (Tidak perlu disambiguasi entitas utama di sini) ---
        elif intent == "info_pmb_umum":
            if not pmb_info or not isinstance(pmb_info, dict):
                response_text = f"Maaf {sapaan_untuk_user}, informasi Penerimaan Mahasiswa Baru (PMB) tidak dapat dimuat saat ini. Silakan cek website resmi UNANDA."
                final_intent_category = "fallback_pmb_data_missing"
            else:
                website = pmb_info.get('website', '')
                kontak = pmb_info.get('contact_person', '')
                response_text = f"{sapaan_awal_kalimat}. Informasi lengkap mengenai Penerimaan Mahasiswa Baru (PMB) UNANDA, termasuk untuk Fakultas Teknik, "
                if website and 'http' in website: response_text += f"biasanya dapat diakses melalui website resmi PMB di: **{website}**\n\n"
                else: response_text += "biasanya dapat diakses melalui website resmi PMB UNANDA.\n\n"
                response_text += ("Di sana Anda bisa menemukan informasi tentang:\n"
                                  "- Jadwal pendaftaran\n- Jalur seleksi yang tersedia\n- Persyaratan pendaftaran\n"
                                  "- Rincian biaya awal\n- Alur dan prosedur pendaftaran online\n\n")
                if kontak and str(kontak).strip(): response_text += f"Jika ada pertanyaan lebih lanjut mengenai PMB, Anda juga bisa menghubungi kontak panitia PMB: **{escape(str(kontak))}**.\n\n" # Escape kontak person
                response_text += "Apakah ada informasi spesifik terkait PMB yang ingin Anda tanyakan kepada saya? (misalnya tentang jalur, biaya awal, atau cara daftar)"
                final_intent_category = "info_pmb_umum_handled"

        elif intent == "info_jalur_pmb":
            if not pmb_info or not isinstance(pmb_info, dict) or not isinstance(pmb_info.get('jalur'), dict) or not pmb_info.get('jalur'):
                 response_text = f"Maaf {sapaan_untuk_user}, informasi detail mengenai jalur pendaftaran PMB tidak dapat dimuat. Silakan cek website PMB resmi."
                 final_intent_category = "fallback_pmb_jalur_missing"
            else:
                response_parts = [f"{sapaan_awal_kalimat}, berikut adalah jalur pendaftaran yang umumnya tersedia (berdasarkan data terakhir):"]
                jalur_data = pmb_info.get('jalur', {})
                website = pmb_info.get('website', '')
                if not jalur_data: response_parts.append("- Informasi jalur pendaftaran belum tersedia.")
                else:
                    for key, info in jalur_data.items():
                        if not isinstance(info, dict): continue # Skip jika format data salah
                        name = info.get('name', key.replace('_', ' ').title())
                        desc = info.get('description', 'Informasi detail belum tersedia.')
                        response_parts.append(f"\n- **{escape(name)}**: {escape(desc)}") # Escape nama dan deskripsi
                response_parts.append("\n\n**Penting:** Persyaratan detail, kuota, dan jadwal spesifik untuk setiap jalur dapat berubah setiap tahun.")
                if website and 'http' in website: response_parts.append(f"Pastikan Anda selalu memeriksa informasi terbaru dan paling akurat di website PMB resmi: **{website}**")
                else: response_parts.append("Pastikan Anda selalu memeriksa informasi terbaru dan paling akurat di website PMB UNANDA.")
                response_text = "\n".join(response_parts)
                final_intent_category = "info_jalur_pmb_handled"

        elif intent == "info_biaya_pmb":
            if not pmb_info or not isinstance(pmb_info, dict) or not isinstance(pmb_info.get('fees'), dict) or not pmb_info.get('fees'):
                response_text = f"Maaf {sapaan_untuk_user}, informasi rincian biaya awal PMB tidak dapat dimuat. Silakan cek website PMB resmi."
                final_intent_category = "fallback_pmb_fee_missing"
            else:
                response_parts = [f"{sapaan_awal_kalimat}, berikut adalah perkiraan komponen biaya awal yang terkait dengan Pendaftaran Mahasiswa Baru (berdasarkan data terakhir):"]
                fees_data = pmb_info.get('fees', {})
                website = pmb_info.get('website', '')
                found_fee = False
                if not fees_data: response_parts.append("- Rincian biaya pendaftaran belum tersedia.")
                else:
                    for key, info in fees_data.items():
                        if not isinstance(info, dict): continue # Skip jika format data salah
                        name = info.get('name', key.replace('_', ' ').title())
                        amount = info.get('amount')
                        notes = info.get('notes', '')
                        if amount is not None:
                            response_parts.append(f"\n- **{escape(name)}**: **{format_idr(amount)}**")
                            if notes and str(notes).strip(): response_parts.append(f"  *({escape(str(notes))})*") # Escape notes
                            found_fee = True
                        elif name != key: # Tampilkan nama meski amount tidak ada
                             response_parts.append(f"\n- **{escape(name)}**: Informasi biaya belum tersedia")
                             if notes and str(notes).strip(): response_parts.append(f"  *({escape(str(notes))})*") # Escape notes
                if found_fee:
                    response_parts.append("\n\n**Penting:**")
                    response_parts.append("- Ini adalah **biaya awal** yang terkait pendaftaran dan mungkin kegiatan orientasi/pembekalan.")
                    response_parts.append("- Biaya ini **umumnya belum termasuk** biaya SPP/UKT untuk semester pertama dan biaya variabel lainnya (seperti praktikum jika ada di semester 1).")
                    response_parts.append("- Jumlah dan komponen biaya dapat berubah. Selalu konfirmasi rincian biaya terbaru.")
                if website and 'http' in website: response_parts.append(f"Cek rincian biaya resmi dan terbaru di website PMB: **{website}**")
                else: response_parts.append("Cek rincian biaya resmi dan terbaru di website PMB UNANDA.")
                response_text = "\n".join(response_parts)
                final_intent_category = "info_biaya_pmb_handled"

        elif intent == "cara_daftar_pmb":
            if not pmb_info or not isinstance(pmb_info, dict) or not isinstance(pmb_info.get('general_steps'), list) or not pmb_info.get('general_steps'):
                 response_text = f"Maaf {sapaan_untuk_user}, panduan umum langkah pendaftaran PMB tidak dapat dimuat. Silakan cek alur pendaftaran di website PMB resmi."
                 final_intent_category = "fallback_pmb_steps_missing"
            else:
                # Ganti sapaan agar lebih pas
                response_parts = [f"{sapaan_awal_kalimat}! Berikut adalah gambaran umum langkah-langkah mendaftar sebagai mahasiswa baru secara online (berdasarkan prosedur umum):"]
                steps_data = pmb_info.get('general_steps', [])
                website = pmb_info.get('website', '')
                if not steps_data: response_parts.append("- Langkah-langkah pendaftaran belum tersedia.")
                else:
                    for i, step in enumerate(steps_data):
                        if isinstance(step, str): response_parts.append(f"{i+1}. {escape(step)}") # Escape step
                        else: response_parts.append(f"{i+1}. (Langkah tidak valid)")

                response_parts.append("\n\n**Mohon Diperhatikan:**")
                response_parts.append("- Ini adalah alur umum, langkah spesifik mungkin sedikit berbeda tergantung jalur pendaftaran dan sistem yang digunakan.")
                response_parts.append("- Pastikan Anda membaca **semua petunjuk** dengan teliti di portal pendaftaran.")
                response_parts.append("- Siapkan **semua dokumen** yang diperlukan dalam format digital (scan/foto) sesuai persyaratan.")
                response_parts.append("- Perhatikan **jadwal dan batas waktu** setiap tahapan.")
                if website and 'http' in website: response_parts.append(f"\nUntuk panduan paling akurat dan memulai pendaftaran, kunjungi website PMB resmi: **{website}**")
                else: response_parts.append("\nUntuk panduan paling akurat dan memulai pendaftaran, kunjungi website PMB resmi UNANDA.")
                response_text = "\n".join(response_parts)
                final_intent_category = "cara_daftar_pmb_handled"


        # --- Handler Tanya Pembelajaran (dengan Slot Filling) ---
        elif intent == "tanya_pembelajaran_prodi":
            # === DISAMBIGUASI / SLOT FILLING ===
            # Dapatkan daftar prodi yang memiliki ringkasan pembelajaran di data
            prodi_options_with_learning_summary = []
            if learning_content and isinstance(learning_content, dict):
                 for prodi, content in learning_content.items():
                      # Check if prodi is not an internal key and has a non-empty string summary
                      if not prodi.startswith("_") and isinstance(content, dict) and content.get("_prodi_summary") and isinstance(content.get("_prodi_summary"), str) and content["_prodi_summary"].strip():
                           prodi_options_with_learning_summary.append(prodi)

            if not detected_prodi:
                if prodi_options_with_learning_summary:
                    response_text = (f"{sapaan_awal_kalimat}, Anda ingin mengetahui gambaran pembelajaran di program studi mana? "
                                     f"Pilihan yang ada di data saya: **{', '.join(map(escape, prodi_options_with_learning_summary))}**.")
                    final_intent_category = "prompt_for_prodi_learning"
                else:
                    response_text = f"{sapaan_untuk_user}Maaf, informasi pembelajaran untuk program studi belum tersedia di data saya."
                    final_intent_category = "fallback_learning_prodi_list_missing"
            # =====================================
            elif not learning_content or not isinstance(learning_content, dict):
                response_text = f"Maaf {sapaan_untuk_user}, informasi materi pembelajaran prodi tidak dapat dimuat saat ini."
                final_intent_category = "fallback_learning_data_missing"
            else:
                 # Logika asli jika prodi terdeteksi
                prodi_info = learning_content.get(detected_prodi)
                prodi_summary = None
                # Check if prodi_info exists, is a dictionary, and has a non-empty string summary
                if prodi_info and isinstance(prodi_info, dict) and prodi_info.get("_prodi_summary") and isinstance(prodi_info.get("_prodi_summary"), str):
                     prodi_summary = prodi_info.get("_prodi_summary").strip()

                if prodi_summary:
                    response_text = (f"{sapaan_awal_kalimat}. Secara garis besar, di **Prodi {escape(detected_prodi)}**, mahasiswa akan mempelajari berbagai hal terkait bidangnya. "
                                        f"Berikut adalah ringkasan fokus pembelajarannya:\n\n{escape(prodi_summary)}\n\n" # Escape summary
                                        "Tentu saja ini gambaran umum. Mata kuliah spesifik akan dipelajari per semester sesuai kurikulum. "
                                        f"Anda bisa cek detail kurikulum di website prodi {escape(detected_prodi)} jika tersedia.")
                    final_intent_category = "tanya_pembelajaran_prodi_handled"
                else:
                    response_text = (f"Maaf {sapaan_untuk_user}, ringkasan materi pembelajaran untuk **Prodi {escape(detected_prodi)}** belum tersedia secara spesifik di data saya. "
                                        "Secara umum, prodi ini akan membahas topik-topik yang relevan dengan bidangnya. "
                                        f"Anda bisa mencari silabus atau kurikulum di website resmi Prodi {escape(detected_prodi)} untuk detail mata kuliah.")
                    final_intent_category = "fallback_learning_prodi_summary_missing"

        elif intent == "tanya_pembelajaran_lab":
            # === DISAMBIGUASI / SLOT FILLING ===
            # Ambil daftar lab yang memiliki deskripsi pembelajaran
            all_labs_with_desc = []
            if learning_content and isinstance(learning_content, dict):
                for prodi, content in learning_content.items():
                     if isinstance(content, dict):
                          # Ambil lab yang punya deskripsi (string non-kosong)
                          all_labs_with_desc.extend([lab for lab in content.keys() if not lab.startswith("_") and content.get(lab) and isinstance(content.get(lab), str) and content.get(lab).strip()]) # Use .keys() and .get() safely

            if not detected_lab:
                 if all_labs_with_desc:
                     # Gunakan set untuk unik, lalu kembali ke list untuk random sample
                     contoh_lab_list = list(set(all_labs_with_desc))
                     contoh_display = random.sample(contoh_lab_list, min(len(contoh_lab_list), 3))
                     response_text = (f"{sapaan_awal_kalimat}, Anda ingin tahu materi pembelajaran di laboratorium mana? "
                                      "Mohon sebutkan nama laboratorium spesifiknya. "
                                      f"Contohnya: 'apa yang dipelajari di {escape(random.choice(contoh_display))}?'")
                     final_intent_category = "prompt_for_lab_learning"
                 else:
                     response_text = (f"{sapaan_awal_kalimat}. Anda ingin tahu materi pembelajaran di laboratorium mana? "
                                      "Mohon sebutkan nama laboratorium spesifiknya. (Maaf, daftar lab dengan deskripsi belum tersedia di data saya untuk diberikan contoh).")
                     final_intent_category = "prompt_for_lab_learning_no_examples"
            # =====================================
            elif not learning_content or not isinstance(learning_content, dict):
                 response_text = f"Maaf {sapaan_untuk_user}, informasi materi pembelajaran laboratorium tidak dapat dimuat saat ini."
                 final_intent_category = "fallback_learning_data_missing"
            else:
                 # Logika asli jika lab terdeteksi
                possible_prodi_owners = []
                lab_description = None
                target_prodi_for_lab = None # Prodi yang deskripsi labnya diambil
                for prodi, content in learning_content.items():
                    # Check if content is a dictionary before checking for lab
                    if isinstance(content, dict) and detected_lab in content:
                        desc = content.get(detected_lab)
                        # Pastikan deskripsi valid (string non-kosong)
                        if desc and isinstance(desc, str) and desc.strip():
                            possible_prodi_owners.append(prodi)
                            # Prioritaskan prodi yang terdeteksi dari NLU jika ada
                            if detected_prodi and detected_prodi == prodi:
                                lab_description = desc.strip()
                                target_prodi_for_lab = prodi
                                break # Sudah ketemu deskripsi dari prodi yang relevan
                            elif not lab_description: # Ambil deskripsi pertama yang ditemukan jika prodi tidak terdeteksi
                                lab_description = desc.strip()
                                target_prodi_for_lab = prodi

                if lab_description:
                     if len(possible_prodi_owners) > 1 and not detected_prodi:
                         # Lab ada di >1 prodi, dan pengguna tidak spesifik prodi
                         response_text = (f"{sapaan_awal_kalimat}. Laboratorium **{escape(detected_lab)}** relevan untuk beberapa prodi "
                                          f"(misalnya {', '.join(map(escape, possible_prodi_owners))}).\n\n"
                                          f"Secara umum, di lab ini fokus pembelajarannya adalah:\n{escape(lab_description)}\n\n" # Escape deskripsi
                                          f"Materi spesifik mungkin disesuaikan tergantung kebutuhan prodi.")
                         final_intent_category = "tanya_pembelajaran_lab_multi_prodi"
                     else:
                         # Lab spesifik atau hanya di 1 prodi
                         prodi_konteks = f" (Prodi {escape(target_prodi_for_lab)})" if target_prodi_for_lab else ""
                         response_text = (f"{sapaan_awal_kalimat}. Di laboratorium **{escape(detected_lab)}**{prodi_konteks}, "
                                          f"fokus materi pembelajaran dan praktikumnya meliputi:\n\n{escape(lab_description)}") # Escape deskripsi
                         final_intent_category = "tanya_pembelajaran_lab_handled"
                else:
                    response_text = (f"Maaf {sapaan_untuk_user}, deskripsi detail mengenai apa yang dipelajari di laboratorium "
                                     f"**{escape(detected_lab)}** belum tersedia di data saya. "
                                     "Biasanya lab ini mendukung mata kuliah praktikum terkait.")
                    final_intent_category = "fallback_learning_lab_desc_missing"

        # --- Intent tidak ada handler spesifik di atas ---
        # Ini adalah fallback jika intent dikenali tapi tidak ada logika di if/elif blocks di atas
        else:
            final_intent_category = "unhandled_valid_intent" # Override kategori
            # Periksa apakah intent yang tidak terhandle ini adalah salah satu intent yang diharapkan
            # Misalnya, jika ada intent baru di model tapi belum ada handler di sini
            known_intents_without_handlers = [
                 # Daftarkan intent yang ada di model tapi belum ditangani spesifik di atas
                 # Contoh: "info_dosen", "info_kurikulum"
            ]
            # Use get('intent') safely as it might be None
            if intent and intent in known_intents_without_handlers:
                 response_text = (f"Saya mengerti Anda bertanya tentang '{escape(intent.replace('_', ' '))}' ({score*100:.1f}%). "
                                  f"Namun, saya belum memiliki informasi detail atau tindakan spesifik untuk topik tersebut saat ini. "
                                  "Mungkin Anda bisa bertanya tentang topik lain seperti biaya, pendaftaran, jadwal, atau prodi?")
            else:
                # Ini kasus sangat jarang, intent tidak umum atau salah deteksi
                response_text = (f"Saya mendeteksi niat '{escape(intent.replace('_', ' ')) if intent else 'Tidak Dikenali'}' ({score*100:.1f}%) dari pertanyaan Anda, " # Use ternary for intent
                                 "tapi saya belum diprogram untuk menjawab topik tersebut. "
                                 "Mohon ajukan pertanyaan lain yang terkait Fakultas Teknik UNANDA.")


    # --- Skor rendah atau tidak ada intent (sudah ditangani di app.py) ---
    # Logika ini sudah dipindahkan ke app.py sebelum memanggil get_response_for_intent

    # Kembalikan teks respons dan kategori intent final
    # Pastikan final_intent_category sudah di-set dengan benar di setiap cabang logika
    return response_text, final_intent_category

# --- END OF FILE intent_logic.py ---