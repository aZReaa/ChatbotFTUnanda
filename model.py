# model.py (Versi Lengkap dengan Perbaikan AttributeError)

import spacy
from spacy.training.example import Example
from spacy.util import minibatch, compounding
import random
import warnings
import os
import traceback

# --- PILIH MODEL DASAR ---
nlp = spacy.blank("id")
print("Menggunakan model spaCy: blank 'id'")
# -------------------------

# --- TAMBAHKAN PIPE TEXTCAT DAN NER ---
print("Memastikan pipe 'textcat' dan 'ner' ada...")
if "textcat" not in nlp.pipe_names:
    textcat_pipe = nlp.add_pipe("textcat", last=True)
    print("Komponen 'textcat' berhasil ditambahkan.")
else:
    textcat_pipe = nlp.get_pipe("textcat")
    print("Komponen 'textcat' sudah ada.")

if "ner" not in nlp.pipe_names:
    ner_pipe = nlp.add_pipe("ner", last=True)
    print("Komponen 'ner' berhasil ditambahkan.")
else:
    ner_pipe = nlp.get_pipe("ner")
    print("Komponen 'ner' sudah ada.")


# --- DEFINISIKAN LABEL INTENT (TEXTCAT) ---
labels_intent = [
    "greeting_ft", "provide_name", "goodbye_ft", "thankyou_ft",
    "info_spp_ft", "cara_bayar_spp_ft",
    "jadwal_kuliah_ft",
    "fasilitas_umum_ft",
    "info_lab_sipil", "info_lab_informatika", "info_lab_pertambangan", # Info umum lab
    "info_prodi_sipil", "info_prodi_informatika", "info_prodi_pertambangan", # Info umum prodi
    "kontak_ft",
    "tanya_biaya_praktikum",
    "info_pmb_umum", "info_jalur_pmb", "info_biaya_pmb", "cara_daftar_pmb",
    # --- INTENT BARU UNTUK PEMBELAJARAN ---
    "tanya_pembelajaran_prodi", # Tanya apa yang dipelajari di PRODI
    "tanya_pembelajaran_lab"    # Tanya apa yang dipelajari di LAB
]

# --- DEFINISIKAN LABEL ENTITAS (NER) ---
labels_ner = ["PERSON"] # Hanya PERSON

# --- Helper function untuk membuat cats dictionary ---
def create_cats_combined(target_label, all_labels):
    if target_label not in all_labels:
        print(f"PERINGATAN: Target label '{target_label}' tidak ditemukan dalam daftar labels_intent. Pastikan tidak ada typo.")
    return {label: (1.0 if label == target_label else 0.0) for label in all_labels}

# --- Menambahkan label ke pipes ---
print("Menambahkan label ke pipes...")
current_labels_textcat = set(textcat_pipe.labels)
for label in labels_intent:
    if label not in current_labels_textcat:
        textcat_pipe.add_label(label)
print(f"Label textcat: {list(textcat_pipe.labels)}") # Cetak sebagai list agar lebih rapi
current_labels_ner = set(ner_pipe.labels)
for label in labels_ner:
     if label not in current_labels_ner:
          ner_pipe.add_label(label)
print(f"Label NER: {list(ner_pipe.labels)}")


# --- DATASET PELATIHAN GABUNGAN (INTENT & NER) ---
# !! TAMBAHKAN LEBIH BANYAK CONTOH !!
TRAIN_DATA = [
    # === Tanya Biaya Praktikum ===
    ("Berapa biaya praktikum di FT?", {"cats": create_cats_combined("tanya_biaya_praktikum", labels_intent), "entities": []}),
    ("Uang praktikum lab berapa ya?", {"cats": create_cats_combined("tanya_biaya_praktikum", labels_intent), "entities": []}),
    ("Ada biaya tambahan buat praktikum?", {"cats": create_cats_combined("tanya_biaya_praktikum", labels_intent), "entities": []}),
    ("Praktikum pemrograman web bayar berapa?", {"cats": create_cats_combined("tanya_biaya_praktikum", labels_intent), "entities": []}),
    ("Biaya praktikum lab software?", {"cats": create_cats_combined("tanya_biaya_praktikum", labels_intent), "entities": []}),
    ("Info uang lab", {"cats": create_cats_combined("tanya_biaya_praktikum", labels_intent), "entities": []}),
    ("Ujian akhir praktikum bayar berapa?", {"cats": create_cats_combined("tanya_biaya_praktikum", labels_intent), "entities": []}),
    ("Biaya seminar lab hardware?", {"cats": create_cats_combined("tanya_biaya_praktikum", labels_intent), "entities": []}),
    ("Praktikum di teknik bayar lagi ga?", {"cats": create_cats_combined("tanya_biaya_praktikum", labels_intent), "entities": []}),
    ("Berapa bayar buat ikut praktikum?", {"cats": create_cats_combined("tanya_biaya_praktikum", labels_intent), "entities": []}),

    # === Greeting ===
    ("Hai", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),
    ("Assalamualaikum", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),
    ("Halo", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),
    ("Selamat pagi", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),
    ("Selamat Malam", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),
    ("Hai admin FT", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),
    ("Permisi", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),
    ("Pagi", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),
    ("Siang", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),
    ("Sore", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),
    ("Malam", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),
    ("Halo bot", {"cats": create_cats_combined("greeting_ft", labels_intent), "entities": []}),

    # === Provide Name (Intent + NER) ===
    ("Nama saya Budi", {"cats": create_cats_combined("provide_name", labels_intent), "entities": [(10, 14, "PERSON")]}),
    ("Panggil saja saya Citra", {"cats": create_cats_combined("provide_name", labels_intent), "entities": [(18, 23, "PERSON")]}),
    ("Saya Andi", {"cats": create_cats_combined("provide_name", labels_intent), "entities": [(5, 9, "PERSON")]}),
    ("Kenalkan, nama saya Rahmat Hidayat", {"cats": create_cats_combined("provide_name", labels_intent), "entities": [(20, 34, "PERSON")]}),
    ("Budi", {"cats": create_cats_combined("provide_name", labels_intent), "entities": [(0, 4, "PERSON")]}),
    ("Citra", {"cats": create_cats_combined("provide_name", labels_intent), "entities": [(0, 5, "PERSON")]}),
    ("Karin", {"cats": create_cats_combined("provide_name", labels_intent), "entities": [(0, 5, "PERSON")]}),
    ("Dewi", {"cats": create_cats_combined("provide_name", labels_intent), "entities": [(0, 4, "PERSON")]}),
    ("Nama saya adalah Karin", {"cats": create_cats_combined("provide_name", labels_intent), "entities": [(17, 22, "PERSON")]}),
    ("Saya Budi Haryanto", {"cats": create_cats_combined("provide_name", labels_intent), "entities": [(5, 18, "PERSON")]}),

    # === Goodbye ===
    ("Oke makasih, sampai jumpa", {"cats": create_cats_combined("goodbye_ft", labels_intent), "entities": []}),
    ("Dadah", {"cats": create_cats_combined("goodbye_ft", labels_intent), "entities": []}),
    ("Cukup sekian", {"cats": create_cats_combined("goodbye_ft", labels_intent), "entities": []}),
    ("Sampai jumpa lagi", {"cats": create_cats_combined("goodbye_ft", labels_intent), "entities": []}),
    ("Sudah cukup infonya", {"cats": create_cats_combined("goodbye_ft", labels_intent), "entities": []}),
    ("Itu saja, terima kasih", {"cats": create_cats_combined("goodbye_ft", labels_intent), "entities": []}),
    ("Oke, saya pamit", {"cats": create_cats_combined("goodbye_ft", labels_intent), "entities": []}),

    # === Thank You ===
    ("Terima kasih infonya", {"cats": create_cats_combined("thankyou_ft", labels_intent), "entities": []}),
    ("Makasih banyak bantuannya", {"cats": create_cats_combined("thankyou_ft", labels_intent), "entities": []}),
    ("Oke, thanks", {"cats": create_cats_combined("thankyou_ft", labels_intent), "entities": []}),
    ("Oke, thanks ya", {"cats": create_cats_combined("thankyou_ft", labels_intent), "entities": []}),
    ("Sangat membantu, terima kasih", {"cats": create_cats_combined("thankyou_ft", labels_intent), "entities": []}),
    ("Makasih banyak!", {"cats": create_cats_combined("thankyou_ft", labels_intent), "entities": []}),
    ("Mantap infonya, makasih", {"cats": create_cats_combined("thankyou_ft", labels_intent), "entities": []}),

    # === Info SPP ===
    ("Berapa biaya SPP teknik?", {"cats": create_cats_combined("info_spp_ft", labels_intent), "entities": []}),
    ("UKT fakultas teknik berapa ya?", {"cats": create_cats_combined("info_spp_ft", labels_intent), "entities": []}),
    ("info uang kuliah teknik", {"cats": create_cats_combined("info_spp_ft", labels_intent), "entities": []}),
    ("Biaya per semester di FT?", {"cats": create_cats_combined("info_spp_ft", labels_intent), "entities": []}),
    ("Biaya kuliah di FT berapa?", {"cats": create_cats_combined("info_spp_ft", labels_intent), "entities": []}),
    ("Mau tanya biaya pendidikan FT", {"cats": create_cats_combined("info_spp_ft", labels_intent), "entities": []}),
    ("SPP prodi informatika berapa?", {"cats": create_cats_combined("info_spp_ft", labels_intent), "entities": []}),
    ("Berapa UKT teknik sipil?", {"cats": create_cats_combined("info_spp_ft", labels_intent), "entities": []}),
    ("Rincian biaya kuliah di teknik ada?", {"cats": create_cats_combined("info_spp_ft", labels_intent), "entities": []}),

    # === Cara Bayar SPP ===
    ("Bagaimana cara bayar UKT FT?", {"cats": create_cats_combined("cara_bayar_spp_ft", labels_intent), "entities": []}),
    ("Bayar SPP teknik lewat apa?", {"cats": create_cats_combined("cara_bayar_spp_ft", labels_intent), "entities": []}),
    ("Prosedur pembayaran uang kuliah?", {"cats": create_cats_combined("cara_bayar_spp_ft", labels_intent), "entities": []}),
    ("Bayarnya kemana ya?", {"cats": create_cats_combined("cara_bayar_spp_ft", labels_intent), "entities": []}),
    ("Minta tutorial bayar SPP dong", {"cats": create_cats_combined("cara_bayar_spp_ft", labels_intent), "entities": []}),
    ("Bisa bayar lewat bank apa saja?", {"cats": create_cats_combined("cara_bayar_spp_ft", labels_intent), "entities": []}),
    ("Info rekening pembayaran FT", {"cats": create_cats_combined("cara_bayar_spp_ft", labels_intent), "entities": []}),
    ("Kapan batas waktu pembayaran?", {"cats": create_cats_combined("cara_bayar_spp_ft", labels_intent), "entities": []}),

    # === Jadwal Kuliah (PDF) ===
    ("Minta jadwal kuliah fakultas teknik", {"cats": create_cats_combined("jadwal_kuliah_ft", labels_intent), "entities": []}),
    ("Jadwal FT semester ini mana?", {"cats": create_cats_combined("jadwal_kuliah_ft", labels_intent), "entities": []}),
    ("Saya butuh jadwal pdf teknik", {"cats": create_cats_combined("jadwal_kuliah_ft", labels_intent), "entities": []}),
    ("Lihat jadwal kuliah dimana?", {"cats": create_cats_combined("jadwal_kuliah_ft", labels_intent), "entities": []}),
    ("Lihat jadwal kuliah FT dimana?", {"cats": create_cats_combined("jadwal_kuliah_ft", labels_intent), "entities": []}),
    ("Jadwal kuliah prodi informatika ada?", {"cats": create_cats_combined("jadwal_kuliah_ft", labels_intent), "entities": []}),
    ("Tolong kirim jadwal sipil", {"cats": create_cats_combined("jadwal_kuliah_ft", labels_intent), "entities": []}),
    ("Jadwal teknik pertambangan semester genap", {"cats": create_cats_combined("jadwal_kuliah_ft", labels_intent), "entities": []}),
    ("Roster kuliah FT", {"cats": create_cats_combined("jadwal_kuliah_ft", labels_intent), "entities": []}),

    # === Fasilitas Umum FT ===
    ("Fasilitas umum di fakultas teknik apa saja?", {"cats": create_cats_combined("fasilitas_umum_ft", labels_intent), "entities": []}),
    ("Apakah ada wifi di gedung FT?", {"cats": create_cats_combined("fasilitas_umum_ft", labels_intent), "entities": []}),
    ("Di FT ada kantin?", {"cats": create_cats_combined("fasilitas_umum_ft", labels_intent), "entities": []}),
    ("Gedung teknik fasilitasnya apa aja?", {"cats": create_cats_combined("fasilitas_umum_ft", labels_intent), "entities": []}),
    ("Gedung FT ada fasilitas apa aja?", {"cats": create_cats_combined("fasilitas_umum_ft", labels_intent), "entities": []}),
    ("Apa saja yang ada di gedung teknik?", {"cats": create_cats_combined("fasilitas_umum_ft", labels_intent), "entities": []}),
    ("Mushola FT dimana?", {"cats": create_cats_combined("fasilitas_umum_ft", labels_intent), "entities": []}),
    ("Perpustakaan fakultas teknik ada?", {"cats": create_cats_combined("fasilitas_umum_ft", labels_intent), "entities": []}),
    ("Tempat parkir FT luas?", {"cats": create_cats_combined("fasilitas_umum_ft", labels_intent), "entities": []}),

    # === Info Lab Umum (Sipil) ===
    ("Lab untuk prodi teknik sipil apa saja?", {"cats": create_cats_combined("info_lab_sipil", labels_intent), "entities": []}),
    ("Sebutkan laboratorium di teknik sipil", {"cats": create_cats_combined("info_lab_sipil", labels_intent), "entities": []}),
    ("Apa saja lab di sipil?", {"cats": create_cats_combined("info_lab_sipil", labels_intent), "entities": []}),
    ("Teknik sipil punya lab apa?", {"cats": create_cats_combined("info_lab_sipil", labels_intent), "entities": []}),
    ("Info lab basah sipil", {"cats": create_cats_combined("info_lab_sipil", labels_intent), "entities": []}),
    ("Lab komputer sipil ada?", {"cats": create_cats_combined("info_lab_sipil", labels_intent), "entities": []}),
    ("Mau tanya tentang lab struktur sipil", {"cats": create_cats_combined("info_lab_sipil", labels_intent), "entities": []}),
    ("Daftar lab prodi sipil", {"cats": create_cats_combined("info_lab_sipil", labels_intent), "entities": []}),
    ("Lab mektan dimana?", {"cats": create_cats_combined("info_lab_sipil", labels_intent), "entities": []}),

    # === Info Lab Umum (Informatika) ===
    ("Lab di teknik informatika ada apa aja?", {"cats": create_cats_combined("info_lab_informatika", labels_intent), "entities": []}),
    ("Saya mau tanya lab TI", {"cats": create_cats_combined("info_lab_informatika", labels_intent), "entities": []}),
    ("Lab informatika apa saja?", {"cats": create_cats_combined("info_lab_informatika", labels_intent), "entities": []}),
    ("Laboratorium untuk prodi informatika", {"cats": create_cats_combined("info_lab_informatika", labels_intent), "entities": []}),
    ("Sebutkan lab TI", {"cats": create_cats_combined("info_lab_informatika", labels_intent), "entities": []}),
    ("Info lab jaringan komputer", {"cats": create_cats_combined("info_lab_informatika", labels_intent), "entities": []}),
    ("Lab RPL teknik informatika", {"cats": create_cats_combined("info_lab_informatika", labels_intent), "entities": []}),
    ("Fasilitas laboratorium TI", {"cats": create_cats_combined("info_lab_informatika", labels_intent), "entities": []}),

    # === Info Lab Umum (Pertambangan) ===
    ("Laboratorium teknik pertambangan", {"cats": create_cats_combined("info_lab_pertambangan", labels_intent), "entities": []}),
    ("Info lab prodi tambang", {"cats": create_cats_combined("info_lab_pertambangan", labels_intent), "entities": []}),
    ("Fasilitas lab pertambangan?", {"cats": create_cats_combined("info_lab_pertambangan", labels_intent), "entities": []}),
    ("Teknik pertambangan punya lab apa?", {"cats": create_cats_combined("info_lab_pertambangan", labels_intent), "entities": []}),
    ("Lab geologi tambang", {"cats": create_cats_combined("info_lab_pertambangan", labels_intent), "entities": []}),
    ("Lab mekanika batuan dimana?", {"cats": create_cats_combined("info_lab_pertambangan", labels_intent), "entities": []}),
    ("Daftar laboratorium tambang", {"cats": create_cats_combined("info_lab_pertambangan", labels_intent), "entities": []}),
    ("Lab komputasi tambang ada?", {"cats": create_cats_combined("info_lab_pertambangan", labels_intent), "entities": []}),

    # === Info Prodi Umum (Sipil) ===
    ("Jelaskan tentang teknik sipil", {"cats": create_cats_combined("info_prodi_sipil", labels_intent), "entities": []}),
    ("Info prodi sipil", {"cats": create_cats_combined("info_prodi_sipil", labels_intent), "entities": []}),
    ("Prospek kerja teknik sipil?", {"cats": create_cats_combined("info_prodi_sipil", labels_intent), "entities": []}),
    ("Mau tahu kurikulum sipil", {"cats": create_cats_combined("info_prodi_sipil", labels_intent), "entities": []}),
    ("Deskripsi jurusan teknik sipil", {"cats": create_cats_combined("info_prodi_sipil", labels_intent), "entities": []}),

    # === Info Prodi Umum (Informatika) ===
    ("Info prodi informatika", {"cats": create_cats_combined("info_prodi_informatika", labels_intent), "entities": []}),
    ("Teknik informatika itu gimana?", {"cats": create_cats_combined("info_prodi_informatika", labels_intent), "entities": []}),
    ("Jelaskan tentang TI", {"cats": create_cats_combined("info_prodi_informatika", labels_intent), "entities": []}),
    ("Prospek kerja TI?", {"cats": create_cats_combined("info_prodi_informatika", labels_intent), "entities": []}),
    ("Kurikulum informatika seperti apa?", {"cats": create_cats_combined("info_prodi_informatika", labels_intent), "entities": []}),
    ("Bedanya TI sama SI apa?", {"cats": create_cats_combined("info_prodi_informatika", labels_intent), "entities": []}),

    # === Info Prodi Umum (Pertambangan) ===
    ("Saya tertarik dengan teknik pertambangan", {"cats": create_cats_combined("info_prodi_pertambangan", labels_intent), "entities": []}),
    ("Jelaskan tentang prodi tambang", {"cats": create_cats_combined("info_prodi_pertambangan", labels_intent), "entities": []}),
    ("Jelaskan prodi tambang", {"cats": create_cats_combined("info_prodi_pertambangan", labels_intent), "entities": []}),
    ("Info teknik pertambangan", {"cats": create_cats_combined("info_prodi_pertambangan", labels_intent), "entities": []}),
    ("Prospek kerja lulusan tambang?", {"cats": create_cats_combined("info_prodi_pertambangan", labels_intent), "entities": []}),
    ("Gambaran jurusan teknik pertambangan", {"cats": create_cats_combined("info_prodi_pertambangan", labels_intent), "entities": []}),

    # === Kontak FT ===
    ("Bagaimana menghubungi fakultas teknik?", {"cats": create_cats_combined("kontak_ft", labels_intent), "entities": []}),
    ("Nomor telepon TU FT berapa?", {"cats": create_cats_combined("kontak_ft", labels_intent), "entities": []}),
    ("Kontak fakultas teknik?", {"cats": create_cats_combined("kontak_ft", labels_intent), "entities": []}),
    ("Kontak admin FT", {"cats": create_cats_combined("kontak_ft", labels_intent), "entities": []}),
    ("Email fakultas teknik apa?", {"cats": create_cats_combined("kontak_ft", labels_intent), "entities": []}),
    ("Mau tanya ke TU FT", {"cats": create_cats_combined("kontak_ft", labels_intent), "entities": []}),
    ("Alamat fakultas teknik", {"cats": create_cats_combined("kontak_ft", labels_intent), "entities": []}),
    ("Nomor WA admin FT ada?", {"cats": create_cats_combined("kontak_ft", labels_intent), "entities": []}),
    ("Kontak akademik FT", {"cats": create_cats_combined("kontak_ft", labels_intent), "entities": []}),

    # === Info PMB ===
    ("Info pendaftaran mahasiswa baru", {"cats": create_cats_combined("info_pmb_umum", labels_intent), "entities": []}),
    ("Bagaimana cara daftar kuliah di FT?", {"cats": create_cats_combined("info_pmb_umum", labels_intent), "entities": []}),
    ("Website PMB Unanda apa?", {"cats": create_cats_combined("info_pmb_umum", labels_intent), "entities": []}),
    ("Penerimaan mahasiswa baru kapan dibuka?", {"cats": create_cats_combined("info_pmb_umum", labels_intent), "entities": []}),
    ("Saya mau daftar jadi mahasiswa teknik", {"cats": create_cats_combined("info_pmb_umum", labels_intent), "entities": []}),
    ("Info pendaftaran FT", {"cats": create_cats_combined("info_pmb_umum", labels_intent), "entities": []}),
    ("PMB Fakultas Teknik", {"cats": create_cats_combined("info_pmb_umum", labels_intent), "entities": []}),
    ("Jalur masuk FT apa saja?", {"cats": create_cats_combined("info_jalur_pmb", labels_intent), "entities": []}),
    ("Apakah ada jalur mandiri?", {"cats": create_cats_combined("info_jalur_pmb", labels_intent), "entities": []}),
    ("Info jalur RPL", {"cats": create_cats_combined("info_jalur_pmb", labels_intent), "entities": []}),
    ("Bedanya jalur mandiri sama RPL apa?", {"cats": create_cats_combined("info_jalur_pmb", labels_intent), "entities": []}),
    ("Saya sudah kerja, bisa daftar lewat jalur apa?", {"cats": create_cats_combined("info_jalur_pmb", labels_intent), "entities": []}),
    ("Pendaftaran ada berapa jalur?", {"cats": create_cats_combined("info_jalur_pmb", labels_intent), "entities": []}),
    ("Jalur RPL itu apa?", {"cats": create_cats_combined("info_jalur_pmb", labels_intent), "entities": []}),
    ("Berapa biaya pendaftaran mahasiswa baru?", {"cats": create_cats_combined("info_biaya_pmb", labels_intent), "entities": []}),
    ("Uang formulir berapa?", {"cats": create_cats_combined("info_biaya_pmb", labels_intent), "entities": []}),
    ("Bayar apa saja waktu daftar?", {"cats": create_cats_combined("info_biaya_pmb", labels_intent), "entities": []}),
    ("Biaya pembekalan mahasiswa baru berapa?", {"cats": create_cats_combined("info_biaya_pmb", labels_intent), "entities": []}),
    ("Ada biaya etika?", {"cats": create_cats_combined("info_biaya_pmb", labels_intent), "entities": []}),
    ("Total biaya awal pendaftaran?", {"cats": create_cats_combined("info_biaya_pmb", labels_intent), "entities": []}),
    ("Rincian biaya PMB", {"cats": create_cats_combined("info_biaya_pmb", labels_intent), "entities": []}),
    ("Bagaimana langkah-langkah pendaftarannya?", {"cats": create_cats_combined("cara_daftar_pmb", labels_intent), "entities": []}),
    ("Prosedur daftar online gimana?", {"cats": create_cats_combined("cara_daftar_pmb", labels_intent), "entities": []}),
    ("Tata cara pendaftaran mahasiswa baru", {"cats": create_cats_combined("cara_daftar_pmb", labels_intent), "entities": []}),
    ("Setelah isi formulir ngapain?", {"cats": create_cats_combined("cara_daftar_pmb", labels_intent), "entities": []}),
    ("Alur pendaftaran FT", {"cats": create_cats_combined("cara_daftar_pmb", labels_intent), "entities": []}),
    ("Minta tutorial daftar", {"cats": create_cats_combined("cara_daftar_pmb", labels_intent), "entities": []}),
    ("Gimana cara apply jadi mahasiswa?", {"cats": create_cats_combined("cara_daftar_pmb", labels_intent), "entities": []}),

    # === DATA LATIH BARU: Tanya Pembelajaran Prodi ===
    ("Apa saja yang dipelajari di teknik informatika?", {"cats": create_cats_combined("tanya_pembelajaran_prodi", labels_intent), "entities": []}),
    ("Teknik sipil belajar apa aja?", {"cats": create_cats_combined("tanya_pembelajaran_prodi", labels_intent), "entities": []}),
    ("Kalau masuk tambang, kuliahnya tentang apa?", {"cats": create_cats_combined("tanya_pembelajaran_prodi", labels_intent), "entities": []}),
    ("Di prodi TI fokusnya apa?", {"cats": create_cats_combined("tanya_pembelajaran_prodi", labels_intent), "entities": []}),
    ("Gambaran kuliah jurusan sipil?", {"cats": create_cats_combined("tanya_pembelajaran_prodi", labels_intent), "entities": []}),
    ("Jelaskan materi kuliah informatika", {"cats": create_cats_combined("tanya_pembelajaran_prodi", labels_intent), "entities": []}),
    ("Mata kuliah inti teknik pertambangan?", {"cats": create_cats_combined("tanya_pembelajaran_prodi", labels_intent), "entities": []}),
    ("Apa fokus utama prodi sipil?", {"cats": create_cats_combined("tanya_pembelajaran_prodi", labels_intent), "entities": []}),
    ("Belajar apa di jurusan teknik informatika?", {"cats": create_cats_combined("tanya_pembelajaran_prodi", labels_intent), "entities": []}),

    # === DATA LATIH BARU: Tanya Pembelajaran Lab ===
    ("Di lab software belajar apa?", {"cats": create_cats_combined("tanya_pembelajaran_lab", labels_intent), "entities": []}),
    ("Apa yang dilakukan di lab mekanika tanah?", {"cats": create_cats_combined("tanya_pembelajaran_lab", labels_intent), "entities": []}),
    ("Lab hidrolika itu ngapain aja?", {"cats": create_cats_combined("tanya_pembelajaran_lab", labels_intent), "entities": []}),
    ("Apa itu lab hardware?", {"cats": create_cats_combined("tanya_pembelajaran_lab", labels_intent), "entities": []}),
    ("Fokus lab geologi fisik apa?", {"cats": create_cats_combined("tanya_pembelajaran_lab", labels_intent), "entities": []}),
    ("Pembelajaran di lab struktur dan bahan?", {"cats": create_cats_combined("tanya_pembelajaran_lab", labels_intent), "entities": []}),
    ("Kegiatan di lab perpetaan tambang?", {"cats": create_cats_combined("tanya_pembelajaran_lab", labels_intent), "entities": []}),
    ("Lab mineralogi dan petrologi belajar apa?", {"cats": create_cats_combined("tanya_pembelajaran_lab", labels_intent), "entities": []}),
    ("Jelaskan tentang lab gambar rekayasa", {"cats": create_cats_combined("tanya_pembelajaran_lab", labels_intent), "entities": []}),
    ("Apa saja yang diajarkan di lab geologi struktur?", {"cats": create_cats_combined("tanya_pembelajaran_lab", labels_intent), "entities": []}),
    ("Apa fungsi lab mekanika tanah untuk sipil?", {"cats": create_cats_combined("tanya_pembelajaran_lab", labels_intent), "entities": []}),
]


# --- Fungsi Pelatihan (Dengan Perbaikan AttributeError) ---
def train_spacy(nlp_model, train_data, n_iter=30, dropout=0.35):
    if "textcat" not in nlp_model.pipe_names or "ner" not in nlp_model.pipe_names:
        print("Error: Pipe 'textcat' atau 'ner' tidak ditemukan.")
        return nlp_model

    pipes_to_train = ["textcat", "ner"]
    other_pipes = [pipe for pipe in nlp_model.pipe_names if pipe not in pipes_to_train]

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module='spacy')
        print(f"Nonaktifkan pipes: {other_pipes} selama pelatihan...")
        with nlp_model.disable_pipes(*other_pipes):
            print("Memulai pelatihan untuk pipes:", pipes_to_train)

            # Selalu gunakan begin_training() karena kita memulai dari model blank
            print("Menginisialisasi optimizer dengan begin_training().")
            optimizer = nlp_model.begin_training()

            print("\nMemulai loop pelatihan...")
            for epoch in range(n_iter):
                losses = {}
                random.shuffle(train_data)
                batches = minibatch(train_data, size=compounding(4., 32., 1.001))

                for i, batch in enumerate(batches):
                    examples = []
                    for text, annotations in batch:
                        if not isinstance(annotations, dict):
                             print(f"Batch {i}, Peringatan: Format anotasi salah untuk '{text}'. Melewati.")
                             continue
                        try:
                            doc = nlp_model.make_doc(text)
                            example = Example.from_dict(doc, annotations)
                            examples.append(example)
                        except Exception as e_ex:
                             print(f"Batch {i}, Error membuat Example untuk '{text}': {e_ex}")
                             print(f"  Anotasi bermasalah: {annotations}")
                             # traceback.print_exc()
                             continue

                    if examples:
                        try:
                            nlp_model.update(examples, sgd=optimizer, drop=dropout, losses=losses)
                        except Exception as update_err:
                            print(f"Epoch {epoch+1}, Batch {i}, Error selama nlp.update: {update_err}")
                            # traceback.print_exc()
                            continue

                loss_textcat = losses.get('textcat', 0.0)
                loss_ner = losses.get('ner', 0.0)
                print(f"Epoch {epoch+1}/{n_iter} selesai. Loss Textcat: {loss_textcat:.3f}, Loss NER: {loss_ner:.3f}")

    print("Pelatihan Selesai.")
    return nlp_model

# --- Latih Model ---
print("Memvalidasi data latih...")
valid_train_data = []
labels_in_pipe_textcat = set(textcat_pipe.labels)
labels_in_pipe_ner = set(ner_pipe.labels)
required_labels_found = {"textcat": False, "ner": False}

for i, (text, annots) in enumerate(TRAIN_DATA):
    is_valid = True
    if not isinstance(annots, dict):
        print(f"Data #{i+1} Invalid: Anotasi bukan dictionary. Teks: '{text}'")
        is_valid = False
        continue
    cats = annots.get("cats")
    if cats is not None:
        if not isinstance(cats, dict):
            print(f"Data #{i+1} Invalid: 'cats' bukan dictionary. Teks: '{text}'")
            is_valid = False
        else:
            required_labels_found["textcat"] = True
            unknown_cats = set(cats.keys()) - labels_in_pipe_textcat
            if unknown_cats:
                 print(f"Data #{i+1} Warning: Label 'cats' tidak dikenal di pipe: {unknown_cats}. Teks: '{text}'")
    entities = annots.get("entities")
    if entities is not None:
        if not isinstance(entities, list):
             print(f"Data #{i+1} Invalid: 'entities' bukan list. Teks: '{text}'")
             is_valid = False
        else:
            required_labels_found["ner"] = True
            for j, ent in enumerate(entities):
                if not (isinstance(ent, (tuple, list)) and len(ent) == 3 and isinstance(ent[0], int) and isinstance(ent[1], int) and isinstance(ent[2], str)):
                    print(f"Data #{i+1}, Entity #{j+1} Invalid: Format entitas salah ({ent}). Teks: '{text}'")
                    is_valid = False
                    break
                if ent[2] not in labels_in_pipe_ner:
                     print(f"Data #{i+1}, Entity #{j+1} Warning: Label NER '{ent[2]}' tidak dikenal di pipe. Teks: '{text}'")

    if is_valid:
        valid_train_data.append((text, annots))

print("-" * 30)
if not required_labels_found["textcat"]:
     print("PERINGATAN: Tidak ada data latih valid yang ditemukan untuk Textcat ('cats'). Komponen Textcat tidak akan terlatih.")
if not required_labels_found["ner"]:
     print("PERINGATAN: Tidak ada data latih valid yang ditemukan untuk NER ('entities'). Komponen NER tidak akan terlatih dengan baik.")

if not valid_train_data:
     print("ERROR: Tidak ada data latih valid yang bisa digunakan. Pelatihan dibatalkan.")
     exit()

print(f"Jumlah data latih valid: {len(valid_train_data)} dari {len(TRAIN_DATA)}")
print("Memulai pelatihan...")

nlp = train_spacy(nlp, valid_train_data, n_iter=30, dropout=0.35) # Latih dengan data valid

# --- Simpan Model ---
output_dir = "intent_model_ft_v2" # Pastikan nama direktori sama
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
try:
    nlp.to_disk(output_dir)
    print(f"Model disimpan ke direktori: '{output_dir}'")
except Exception as e:
    print(f"Gagal menyimpan model ke '{output_dir}': {e}")

# --- Uji Model ---
print("\nMenguji model yang baru disimpan:")
try:
    nlp_test = spacy.load(output_dir)
    test_texts = [
        "Halo", "Nama saya Karin", "Karin",
        "Jadwal kuliah informatika ada?", "Cara bayar spp gimana?",
        "Lab sipil ada apa?", "Makasih infonya", "Gedung FT dimana?",
        "Citra", "Saya Budi Haryanto",
        "Berapa biaya praktikum lab software?",
        "Uang ujian akhir praktikum berapa?",
        "Info PMB", "Jalur RPL itu apa?", "Berapa biaya formulir?", "Cara daftar gimana?",
        "Apa yang dipelajari di teknik sipil?", # Test intent baru
        "Belajar apa di lab hardware?", # Test intent baru
        "Lab mekanika tanah ngapain?", # Test intent baru (ambigu)
        "Fokus lab mekanika tanah tambang apa?", # Test intent baru (spesifik)
    ]
    for text in test_texts:
        doc = nlp_test(text)
        print(f"\n>>> Teks: '{doc.text}'")
        cats = doc.cats
        if cats:
             sorted_cats = sorted(cats.items(), key=lambda item: item[1], reverse=True)
             print(f"  Intents (Top 3): {[ (cat, f'{score:.3f}') for cat, score in sorted_cats[:3] ]}")
        else:
             print("  Intents: Komponen Textcat tidak aktif atau tidak ada hasil.")
        ents = doc.ents
        if ents:
            print(f"  Entitas: {[(ent.text, ent.label_) for ent in ents]}")
        else:
            print("  Entitas: Tidak ada")

except Exception as e:
    print(f"Gagal memuat atau menguji model dari '{output_dir}': {e}")