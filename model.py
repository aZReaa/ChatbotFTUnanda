# --- START OF FILE model.py ---

import spacy
from spacy.training.example import Example
from spacy.util import minibatch, compounding
import random
import warnings
import os
import traceback
import json
import argparse



# --- Setup Argument Parser ---x
parser = argparse.ArgumentParser(description="Train spaCy model for intent and NER.")
parser.add_argument("--input-data", required=True, help="Path to the training data JSON file.")
parser.add_argument("--output-dir", default="intent_model_ft_v2", help="Directory to save the trained model.")
parser.add_argument("--n-iter", type=int, default=30, help="Number of training iterations.")
parser.add_argument("--dropout", type=float, default=0.35, help="Dropout rate during training.")
parser.add_argument("--base-model", default="id", help="Base spaCy model to start from (e.g., 'id' for blank, 'id_core_news_sm')")
args = parser.parse_args()
args = parser.parse_args()

# --- PILIH MODEL DASAR ---
print(f"Loading base spaCy model: '{args.base_model}'...")
nlp = None # Inisialisasi nlp sebelum try block
try:
    if args.base_model == "id":
        nlp = spacy.blank("id")
        print("Using model spaCy: blank 'id'")
    else:
        nlp = spacy.load(args.base_model)
        print(f"Using model spaCy: '{args.base_model}'")
except OSError:
    print(f"ERROR: Base model '{args.base_model}' not found. Try 'python -m spacy download {args.base_model}' or use 'id' for blank.")
    print("Falling back to blank 'id' model.")
    nlp = spacy.blank("id")


print("\nMencoba mengaktifkan GPU...")
gpu_activated = False
try:
    # Panggil melalui namespace spacy utama
    spacy.require_gpu() # <<<--- UBAH PEMANGGILAN DI SINI
    gpu_activated = True
    print(">>> GPU Berhasil Diaktifkan! Pelatihan akan menggunakan GPU.")
except Exception as e: # Tangkap error jika GPU tidak bisa diaktifkan
    print(f"--- PERINGATAN: Gagal mengaktifkan GPU: {e}")
    print("--- Pelatihan akan dilanjutkan menggunakan CPU.")
    print("--- Pastikan Prasyarat GPU (Driver, CUDA, cuDNN, spacy[cuda-XXX]) sudah terpenuhi.")
# <<<--- AKHIR BLOK AKTIVASI GPU --->>>
# <<<--- AKHIR BLOK AKTIVASI GPU --->>>
# Contoh pemrosesan teks
text = "SpaCy is great for Natural Language Processing!"
doc = nlp(text)

# Menampilkan hasil pemrosesan
for token in doc:
    print(token.text, token.pos_, token.dep_)
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
# Tetap definisikan di sini untuk menambahkan ke pipe
labels_intent = [
    "greeting_ft", "provide_name", "goodbye_ft", "thankyou_ft",
    "info_spp_ft", "cara_bayar_spp_ft",
    "jadwal_kuliah_ft",
    "fasilitas_umum_ft",
    "info_lab_sipil", "info_lab_informatika", "info_lab_pertambangan", # Info umum lab
    "info_prodi_sipil", "info_prodi_informatika", "info_prodi_pertambangan", # Info umum prodi
    "kontak_ft", "tanya_biaya_praktikum",
    "info_pmb_umum", "info_jalur_pmb", "info_biaya_pmb", "cara_daftar_pmb","ask_bot_identity",
    "tanya_pembelajaran_prodi", "tanya_pembelajaran_lab",
    "info_krs_sevima",
    "cara_bayar_sevima_tokopedia",
    "neutral"
]

# --- DEFINISIKAN LABEL ENTITAS (NER) ---
labels_ner = ["PERSON"] # Hanya PERSON

# --- Menambahkan label ke pipes ---
print("Menambahkan label ke pipes...")
current_labels_textcat = set(textcat_pipe.labels)
for label in labels_intent:
    if label not in current_labels_textcat:
        textcat_pipe.add_label(label)
print(f"Label textcat: {list(textcat_pipe.labels)}")
current_labels_ner = set(ner_pipe.labels)
for label in labels_ner:
     if label not in current_labels_ner:
          ner_pipe.add_label(label)
print(f"Label NER: {list(ner_pipe.labels)}")


# --- MEMBACA DATASET PELATIHAN DARI FILE JSON ---
TRAIN_DATA = []
train_data_file = args.input_data # <-- Gunakan argumen input
print(f"\nMembaca data latih dari file: {train_data_file}")
try:
    with open(train_data_file, 'r', encoding='utf-8') as f:
        data_from_json = json.load(f)
        # Ubah format kembali ke list of tuples: (text, {"cats": {...}, "entities": [...]})
        for item in data_from_json:
            if len(item) == 2 and isinstance(item[0], str) and isinstance(item[1], dict):
                text = item[0]
                annots = item[1]
                # Pastikan struktur anotasi dasar ada
                if "cats" not in annots: annots["cats"] = {}
                if "entities" not in annots: annots["entities"] = []

                # Validasi dan ubah format entitas jika perlu (JSON array -> Python tuple)
                if isinstance(annots.get("entities"), list):
                    valid_entities = []
                    for ent in annots["entities"]:
                        if isinstance(ent, list) and len(ent) == 3:
                             valid_entities.append(tuple(ent))
                        elif isinstance(ent, tuple) and len(ent) == 3:
                             valid_entities.append(ent)
                    annots["entities"] = valid_entities

                TRAIN_DATA.append((text, annots))
            else:
                print(f"Peringatan: Format data tidak valid dalam file JSON, item dilewati: {item}")
    print(f"Berhasil membaca {len(TRAIN_DATA)} data latih.")
except FileNotFoundError:
    print(f"ERROR: File data latih '{train_data_file}' tidak ditemukan.")
    exit(1) # Exit with error code
except json.JSONDecodeError as e:
    print(f"ERROR: Gagal membaca file JSON '{train_data_file}': {e}")
    exit(1)
except Exception as e:
    print(f"ERROR: Terjadi kesalahan saat memproses data latih dari JSON: {e}")
    traceback.print_exc()
    exit(1)

# --- Fungsi Pelatihan ---
# (Fungsi train_spacy tetap sama seperti sebelumnya)
def train_spacy(nlp_model, train_data, n_iter=30, dropout=0.35):
    # ... (kode fungsi train_spacy tidak berubah) ...
    if "textcat" not in nlp_model.pipe_names and "ner" not in nlp_model.pipe_names:
         print("Error: Pipe 'textcat' dan 'ner' tidak ditemukan.")
         return nlp_model # Kembalikan model asli jika kedua pipe tidak ada

    pipes_to_train = []
    if "textcat" in nlp_model.pipe_names:
        pipes_to_train.append("textcat")
    if "ner" in nlp_model.pipe_names:
        pipes_to_train.append("ner")

    if not pipes_to_train:
        print("Error: Tidak ada pipe ('textcat' atau 'ner') untuk dilatih.")
        return nlp_model

    other_pipes = [pipe for pipe in nlp_model.pipe_names if pipe not in pipes_to_train]

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=UserWarning, module='spacy')
        print(f"Nonaktifkan pipes: {other_pipes} selama pelatihan...")
        with nlp_model.disable_pipes(*other_pipes):
            print("Memulai pelatihan untuk pipes:", pipes_to_train)

            # Selalu gunakan begin_training() karena kita memulai dari model blank atau base
            print("Menginisialisasi optimizer dengan begin_training().")
            optimizer = nlp_model.begin_training()

            print("\nMemulai loop pelatihan...")
            for epoch in range(n_iter):
                losses = {}
                random.shuffle(train_data)
                batches = minibatch(train_data, size=compounding(4., 32., 1.001))

                for i, batch in enumerate(batches):
                    examples = []
                    texts_in_batch = [] # Untuk debug error update
                    annots_in_batch = [] # Untuk debug error update
                    for text, annotations in batch:
                        texts_in_batch.append(text) # Simpan untuk debug
                        annots_in_batch.append(annotations) # Simpan untuk debug
                        if not isinstance(annotations, dict):
                             print(f"Batch {i}, Peringatan: Format anotasi salah untuk '{text}'. Melewati.")
                             continue
                        # Validasi lebih lanjut: pastikan ada 'cats' jika textcat dilatih, 'entities' jika ner dilatih
                        if "textcat" in pipes_to_train and "cats" not in annotations:
                            print(f"Batch {i}, Peringatan: Anotasi 'cats' hilang untuk '{text}' padahal textcat dilatih. Melewati.")
                            continue
                        if "ner" in pipes_to_train and "entities" not in annotations:
                             print(f"Batch {i}, Peringatan: Anotasi 'entities' hilang untuk '{text}' padahal ner dilatih. Melewati.")
                             continue

                        try:
                            # Gunakan predicted=nlp_model(text) untuk Example.from_dict dengan base model
                            # Gunakan doc=nlp_model.make_doc(text) untuk blank model
                            doc = nlp_model.make_doc(text) # Asumsi kita sering mulai dari blank atau ingin re-tokenisasi
                            example = Example.from_dict(doc, annotations)
                            examples.append(example)
                        except Exception as e_ex:
                             print(f"Batch {i}, Error membuat Example untuk '{text}': {e_ex}")
                             print(f"  Anotasi bermasalah: {annotations}")
                             traceback.print_exc() # Cetak traceback untuk detail error
                             continue # Lanjut ke item berikutnya dalam batch

                    if examples: # Hanya update jika ada examples valid dalam batch
                        try:
                            # Pastikan ada examples sebelum update
                            nlp_model.update(examples, sgd=optimizer, drop=dropout, losses=losses)
                        except Exception as update_err:
                            print(f"Epoch {epoch+1}, Batch {i}, Error selama nlp.update: {update_err}")
                            print("Teks dalam batch ini:")
                            for t in texts_in_batch: print(f" - '{t}'")
                            print("Anotasi dalam batch ini:")
                            for a in annots_in_batch: print(f" - {a}")
                            traceback.print_exc() # Cetak traceback untuk detail error


                loss_textcat = losses.get('textcat', 'N/A')
                loss_ner = losses.get('ner', 'N/A')
                # Format loss hanya jika angka
                loss_textcat_str = f"{loss_textcat:.3f}" if isinstance(loss_textcat, (int, float)) else loss_textcat
                loss_ner_str = f"{loss_ner:.3f}" if isinstance(loss_ner, (int, float)) else loss_ner
                print(f"Epoch {epoch+1}/{n_iter} selesai. Loss Textcat: {loss_textcat_str}, Loss NER: {loss_ner_str}")

    print("Pelatihan Selesai.")
    return nlp_model

# --- Validasi dan Latih Model ---
print("\nMemvalidasi data latih yang dibaca...")
valid_train_data = []
# Dapatkan label aktual dari pipe setelah ditambahkan
labels_in_pipe_textcat = set(nlp.get_pipe("textcat").labels) if "textcat" in nlp.pipe_names else set()
labels_in_pipe_ner = set(nlp.get_pipe("ner").labels) if "ner" in nlp.pipe_names else set()
has_textcat_data = False
has_ner_data = False
original_data_count = len(TRAIN_DATA)

for i, item in enumerate(TRAIN_DATA):
    if not isinstance(item, (tuple, list)) or len(item) != 2:
        print(f"Data #{i+1} Invalid: Bukan tuple/list dengan 2 elemen. Item: {item}")
        continue
    text, annots = item
    is_valid = True
    if not isinstance(text, str):
        print(f"Data #{i+1} Invalid: Teks bukan string. Item: {item}")
        is_valid = False
        continue
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
            has_textcat_data = True
            unknown_cats = set(cats.keys()) - labels_in_pipe_textcat
            if unknown_cats:
                 print(f"Data #{i+1} Warning: Label 'cats' tidak dikenal di pipe textcat: {unknown_cats}. Teks: '{text}'")
            if not any(v > 0 for v in cats.values()):
                 print(f"Data #{i+1} Warning: Anotasi 'cats' tidak memiliki label positif. Teks: '{text}'")
    entities = annots.get("entities")
    if entities is not None:
        if not isinstance(entities, list):
             print(f"Data #{i+1} Invalid: 'entities' bukan list setelah diproses. Teks: '{text}'")
             is_valid = False
        else:
            has_ner_data = True
            for j, ent in enumerate(entities):
                if not (isinstance(ent, tuple) and len(ent) == 3 and
                        isinstance(ent[0], int) and isinstance(ent[1], int) and ent[0] <= ent[1] and
                        isinstance(ent[2], str)):
                    print(f"Data #{i+1}, Entity #{j+1} Invalid: Format entitas salah ({ent}). Teks: '{text}'")
                    is_valid = False
                    break
                if not (0 <= ent[0] <= len(text) and 0 <= ent[1] <= len(text)):
                    print(f"Data #{i+1}, Entity #{j+1} Invalid: Indeks entitas di luar batas teks ({ent[0]},{ent[1]} vs panjang {len(text)}). Teks: '{text}'")
                    is_valid = False
                    break
                if ent[2] not in labels_in_pipe_ner:
                     print(f"Data #{i+1}, Entity #{j+1} Warning: Label NER '{ent[2]}' tidak dikenal di pipe NER. Teks: '{text}'")

    if is_valid:
        valid_train_data.append((text, annots))

print("-" * 30)
if "textcat" in nlp.pipe_names and not has_textcat_data:
     print("PERINGATAN: Komponen Textcat ada, tetapi tidak ada data latih valid ditemukan dengan anotasi 'cats'. Textcat tidak akan terlatih.")
elif "textcat" not in nlp.pipe_names and has_textcat_data:
     print("PERINGATAN: Ditemukan data latih dengan anotasi 'cats', tetapi komponen Textcat tidak ada di model.")
if "ner" in nlp.pipe_names and not has_ner_data:
     print("PERINGATAN: Komponen NER ada, tetapi tidak ada data latih valid ditemukan dengan anotasi 'entities'. NER tidak akan terlatih dengan baik.")
elif "ner" not in nlp.pipe_names and has_ner_data:
     print("PERINGATAN: Ditemukan data latih dengan anotasi 'entities', tetapi komponen NER tidak ada di model.")

if not valid_train_data:
     print("ERROR: Tidak ada data latih valid yang bisa digunakan. Pelatihan dibatalkan.")
     exit(1)
elif len(valid_train_data) < original_data_count:
     print(f"PERINGATAN: {original_data_count - len(valid_train_data)} data latih dari file JSON tidak valid dan dilewati.")

print(f"Jumlah data latih valid: {len(valid_train_data)} dari {original_data_count} (dibaca dari JSON)")
print("Memulai pelatihan...")

# Latih dengan data valid menggunakan parameter dari args
nlp = train_spacy(nlp, valid_train_data, n_iter=args.n_iter, dropout=args.dropout)

# --- Simpan Model ---
output_dir = args.output_dir # <-- Gunakan argumen output
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
try:
    nlp.to_disk(output_dir)
    print(f"\nModel berhasil disimpan ke direktori: '{output_dir}'")
except Exception as e:
    print(f"Gagal menyimpan model ke '{output_dir}': {e}")
    traceback.print_exc()

# --- Uji Model ---
print("\nMenguji model yang baru disimpan:")
try:
    nlp_test = spacy.load(output_dir)
    # (Kode pengujian model tetap sama)
    # ... (rest of the testing code) ...
    test_texts = [
        # Variasi dengan huruf kecil dan kapital
        "halo, aku ingin tau biaya kuliah Sipil",
        "Aku mau tau, berapa biaya kuliah Informatika?",
        "Gimana cara daftar PMB?",
        "berapa biaya kuliah tahun ini untuk Teknik Sipil?",
        "Ada info tentang jadwal kuliah TI?",
        "Mau tanya, apa biaya praktikum di lab Sipil?",
        "saya mau bayar kuliah lewat Tokopedia, gimana caranya?",
        "Berapa biaya semesteran TI 2023?",
        "Mau tanya jadwal kuliah pertambangan, ada?",
        "Tanya, apakah bisa bayar kuliah lewat Tokopedia?",
        "halo, aku mau info tentang biaya SPP 2024",

        # Variasi awalan kapital dan huruf kecil
        "Apa aja yang dipelajari di lab Informatika?",
        "Di mana bisa bayar kuliah? Saya butuh info",
        "Gimana cara bayar kuliah lewat Tokped?",
        "Saya ingin tahu, ada perubahan biaya kuliah atau tidak?",
        "Mau tanya tentang biaya PMB tahun depan, ada info?",
        "Bisa bantu, saya cari info tentang lab mekanika tanah?",
        "Apakah biaya kuliah untuk Teknik Sipil berbeda setiap tahun?",
        "Di mana saya bisa lihat biaya UKT untuk TI 2023?",
        "Halo, saya ingin daftar ke prodi teknik pertambangan, gimana caranya?",
        "Mau tanya, ada biaya tambahan untuk praktikum?",

        # Variasi penggunaan kata tanya yang berbeda
        "Dimana saya bisa cek info tentang biaya PMB?",
        "Apa saja yang diajarkan di Teknik Sipil?",
        "Bagaimana cara mengisi KRS di Sevima?",
        "Kenapa biaya kuliah tahun ini naik ya?",
        "Berapa biaya UKT untuk prodi Informatika?",
        "Gimana cara isi KRS online?",
        "Apakah ada diskon untuk biaya kuliah?",
        "Ada biaya tambahan untuk PMB tahun ini?",
        "Kapan saya bisa bayar kuliah?",
        "Berapa biaya untuk semester pertama di Teknik Pertambangan?",

        # Kalimat dengan variasi informal atau bahasa gaul
        "Bro, bisa bantu tanya biaya kuliah TI?",
        "Sis, ada info nggak tentang kuliah pertambangan?",
        "Gimana ya cara bayar kuliah lewat Tokped?",
        "Yuk, kasih tau biaya kuliah TI 2023?",
        "Apa kabar? Bisa kasih info biaya PMB?",
        "Nanya dong, ada biaya tambahan di lab sipil?",
        "Bisa bantu? Saya lagi cari info biaya kuliah Sipil",
        "Gimana cara daftar prodi Teknik Pertambangan?",
        "Peraturan baru tentang biaya kuliah di tahun 2024?",

        # Variasi pertanyaan dan pernyataan campuran
        "Halo, mau tanya tentang biaya SPP Informatika",
        "Saya mau daftar PMB tahun ini, gimana caranya?",
        "Ada info jadwal kuliah Sipil?",
        "Bagaimana cara mengakses KRS online di Sevima?",
        "Mau bayar kuliah, gimana cara lewat Tokopedia?",
        "Berapa biaya kuliah S1 Informatika?",
        "Gimana cara bayar SPP lewat Sevima?",
        "Apakah ada kuliah di lab mekanika tanah?",
        "Di mana saya bisa lihat jadwal kuliah Informatika?",
        "Mau daftar PMB, tapi nggak tahu gimana caranya?",

        # Penambahan variasi bahasa Bugis Palopo
        "halo, aku ingin tau berapa biaya kuliah Sipil",
        "Halo, ada info nggak tentang biaya kuliah Informatika?",
        "saya mau tau biaya kuliah TI 2023",
        "Gimana cara bayar kuliah lewat Tokopedia?",
        "Mau tanya biaya praktikum lab TI, ada?",
        "Tanya, berapa biaya PMB tahun ini?",
        "Di mana saya bisa bayar kuliah?",
        "Ada info tentang lab mekanika tanah nggak?",
        "Berapa biaya kuliah untuk Teknik Pertambangan?",
        "Mau tanya, gimana cara isi KRS online?",

        # Variasi kalimat negatif dan ketidakpastian
        "Saya nggak yakin kalau saya bisa bayar kuliah tepat waktu.",
        "Saya tidak tahu apakah saya bisa memilih mata kuliah ini atau tidak.",
        "Tidak ada info lengkap tentang biaya praktikum, kan?",
        "Saya belum jelas tentang cara bayar kuliah lewat Tokopedia.",
        "Apakah biaya kuliah pertambangan itu tetap sama atau ada perubahan?"
    ]

    for text in test_texts:
        doc = nlp_test(text)
        print(f"\n>>> Teks: '{doc.text}'")
        cats = doc.cats
        if cats:
             # Pastikan textcat ada sebelum mencoba mengakses labelnya
             if "textcat" in nlp_test.pipe_names:
                 sorted_cats = sorted(cats.items(), key=lambda item: item[1], reverse=True)
                 print(f"  Intents (Top 3): {[ (cat, f'{score:.3f}') for cat, score in sorted_cats[:3] ]}")
             else:
                 print("  Intents: Komponen Textcat tidak ada di model yang dimuat.")
        else:
             print("  Intents: Komponen Textcat tidak aktif atau tidak ada hasil.")
        ents = doc.ents
        if ents:
            print(f"  Entitas: {[(ent.text, ent.label_) for ent in ents]}")
        else:
             # Pastikan NER ada sebelum menyatakan tidak ada entitas
             if "ner" in nlp_test.pipe_names:
                 print("  Entitas: Tidak ada")
             else:
                 print("  Entitas: Komponen NER tidak ada di model yang dimuat.")

except Exception as e:
    print(f"Gagal memuat atau menguji model dari '{output_dir}': {e}")
    traceback.print_exc()

print("\n--- Selesai ---")
# --- END OF FILE model.py ---