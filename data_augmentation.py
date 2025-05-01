# --- START OF FILE data_augmentation.py ---
import json
import random
import argparse
import logging
from typing import List, Dict, Any, Tuple, Set, Optional
import spacy
from tqdm import tqdm
from pathlib import Path
import re
from collections import defaultdict, Counter

# Set up logging
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Set base level to INFO

# File Handler - logs INFO and above to file
file_handler = logging.FileHandler("data_augmentation.log", mode='w', encoding='utf-8') # 'w' to overwrite log each run
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)

# Stream Handler - logs INFO and above to console
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
logger.addHandler(stream_handler)

# Load spaCy for basic NLP operations
# Set spaCy logging level to WARNING to reduce verbose output
logging.getLogger("spacy").setLevel(logging.WARNING)

try:
    # Coba muat model yang lebih besar jika tersedia, atau fallback
    try:
        nlp = spacy.load("id_core_news_lg")
        logger.info("Loaded Indonesian spaCy model: id_core_news_lg")
    except OSError:
        try:
            nlp = spacy.load("id_core_news_sm")
            logger.info("Loaded Indonesian spaCy model: id_core_news_sm")
        except OSError:
            nlp = spacy.blank("id")
            # This warning is expected if no Indonesian model is installed.
            # The code will still run using basic tokenization.
            logger.warning("Indonesian spaCy model not found. Using blank 'id' model instead. "
                           "Tokenization might be less accurate. Install with: "
                           "'python -m spacy download id_core_news_sm'")
except Exception as e:
    logger.error(f"Unexpected error loading spaCy: {e}", exc_info=True)
    # Fallback to blank model if any other error occurs during loading attempts
    nlp = spacy.blank("id")
    logger.warning("Using blank 'id' model due to spaCy loading error.")


class DataAugmenter:
    """Class for augmenting training data for the university chatbot."""

    def __init__(self):
        # Indonesian language variations (Expanded)
        self.greeting_variations = [
            "halo", "hai", "hi", "selamat pagi", "selamat siang",
            "selamat sore", "selamat malam", "permisi", "maaf", "assalamualaikum",
            "punten", "misi", "pagi", "siang", "sore", "malam", "gan", "bro", "kak"
        ]

        self.question_starters = [
            "bagaimana", "gimana", "apakah", "bisakah", "bolehkah",
            "kapan", "dimana", "di mana", "berapa", "apa", "siapa",
            "kenapa", "mengapa", "tolong", "mau tanya", "saya ingin tahu",
            "info dong", "kasih tau dong", "jelaskan", "mohon info", "caranya",
            "prosedurnya", "tata cara", "syaratnya apa"
        ]

        self.connecting_words = [
            "tentang", "mengenai", "untuk", "terkait", "soal",
            "perihal", "masalah", "informasi", "info", "detail", "prosedur",
            "persyaratan" # 'soal' can appear multiple times, which is fine
        ]

        # University-specific replacements (Expand with more specific terms)
        self.entity_variations = {
            # Finance & Payments
            "biaya kuliah": ["biaya spp", "uang kuliah", "uang spp", "biaya semester",
                           "uang semester", "biaya ukt", "uang ukt", "pembayaran kuliah",
                           "tarif kuliah", "cost kuliah", "biaya pendidikan", "dana kuliah"],
            "ukt": ["uang kuliah tunggal", "ukt", "biaya ukt"],
            "spp": ["sumbangan pembinaan pendidikan", "spp", "biaya spp"],
            "bayar": ["membayar", "pembayaran", "melakukan pembayaran", "transfer", "setor",
                      "transaksi", "lunasi", "bayarnya"],
            "cara bayar": ["metode pembayaran", "cara pembayaran", "bayarnya gimana",
                           "prosedur bayar", "alur pembayaran"],
            "tokopedia": ["tokped", "toped"],
            "virtual account": ["va", "nomor va", "akun virtual"],

            # Academics & Courses
            "informatika": ["TI", "teknik informatika", "if", "ilkom", "ilmu komputer",
                            "prodi informatika", "jurusan informatika", "computer science"],
            "sipil": ["teknik sipil", "prodi sipil", "jurusan sipil", "civil engineering"],
            "pertambangan": ["teknik pertambangan", "prodi pertambangan", "jurusan pertambangan", "tambang"],
            # Add other departments: elektro, mesin, arsitektur, hukum, ekonomi, etc.
            "lab": ["laboratorium", "praktikum", "kegiatan lab", "labkom"],
            "krs": ["kartu rencana studi", "pengisian krs", "kontrak kuliah", "pemrograman matkul",
                    "ambil mata kuliah", "rencana studi"],
            "jadwal kuliah": ["jadwal", "roster", "jadwal matkul", "jadwal pelajaran", "schedule",
                              "susunan jadwal"],
            "mata kuliah": ["matkul", "mk", "course", "mapel"],
            "dosen": ["pengajar", "dosen wali", "pa", "pembimbing akademik", "lecture"],
            "semester": ["smt", "semesteran"],
            "ipk": ["indeks prestasi kumulatif", "nilai", "transkrip"],
            "skripsi": ["tugas akhir", "ta", "thesis", "final project"],

            # Admissions & Systems
            "PMB": ["pendaftaran mahasiswa baru", "masuk kuliah", "daftar kuliah", "penerimaan mahasiswa",
                    "pmb", "daftar maba", "penerimaan maba", "registrasi baru"],
            "sevima": ["sistem akademik", "siakad", "sistem informasi akademik", "portal mahasiswa",
                       "sevima cloud", "website akademik", "simak"], # 'simak' common generic term

            # General University Terms
            "kampus": ["universitas", "univ", "institut", "politeknik"], # Depending on institution type
            "fakultas": ["fak", "faculty"],
            "gedung": ["ruang", "kelas", "auditorium", "bangunan"],
            "dokumen": ["berkas", "surat", "formulir", "file"],
            # Add more relevant entities: beasiswa, organisasi mahasiswa (ormawa), perpustakaan, wisuda, etc.
        }

        self.informal_variations = {
            "saya": ["aku", "gue", "gua", "saia", "sy", "ane", "gw", "ku"],
            "ingin": ["pengen", "mau", "pgn", "mo", "mw", "hendak"],
            "tahu": ["tau", "mengetahui", "liat", "cek", "cari info", "dapat info"],
            "tidak": ["nggak", "ngga", "gak", "ga", "tak", "belum", "tdk", "enggak"], # 'belum' can be ambiguous, use carefully
            "bagaimana": ["gimana", "gmn", "kek mana", "caranya gimana", "bgmn", "kyk gmn"],
            "terima kasih": ["makasih", "mksh", "thx", "thanks", "tq", "trims", "nuwun"],
            "bisakah": ["bisa", "bisa nggak", "bisanya", "bs", "dapatkah", "bolehkah"],
            "apakah": ["apa", "apanya", "apa iya", "kah"], # 'kah' as suffix, harder to handle directly here
            "berapa": ["brp", "berapaan", "ongkosnya"],
            "di mana": ["dimana", "dmn", "kemana", "kmn", "lokasinya", "tempatnya"],
            "kapan": ["kpn", "waktunya"],
            "untuk": ["buat", "utk", "guna"],
            "universitas": ["univ", "kampus", "uni"],
            "fakultas": ["fak"],
            "teknik": ["tek"],
            "informasi": ["info", "inpoh", "kabar"],
            "dengan": ["ama", "sm", "dgn"],
            "yang": ["yg", "yg"],
            "lagi": ["lg"],
            "sudah": ["sdh", "udah"],
            "belum": ["blm"],
            "mahasiswa": ["mhs", "anak kuliahan"],
            "anda": ["kamu", "situ", "loe", "lu", "sampean", "ente"]
            # Add more common informal words/slang/typos
        }

        # Create reverse mappings for easier lookup
        self._create_reverse_mappings()

    def _create_reverse_mappings(self):
        """Create reverse mappings for variations to original words."""
        self.reverse_entity_map = {}
        self.reverse_informal_map = {}

        # Build entity reverse map
        for original, variations in self.entity_variations.items():
            # Map original to itself (lowercase)
            self.reverse_entity_map[original.lower()] = original
            # Map variations to original (lowercase)
            for variant in variations:
                self.reverse_entity_map[variant.lower()] = original

        # Build informal reverse map
        for original, variations in self.informal_variations.items():
            # Map original to itself (lowercase)
            self.reverse_informal_map[original.lower()] = original
            # Map variations to original (lowercase)
            for variant in variations:
                self.reverse_informal_map[variant.lower()] = original

    def load_data(self, filename: str) -> List[Tuple[str, Dict[str, Any]]]:
        """Load training data from JSON file with validation."""
        try:
            filepath = Path(filename)
            if not filepath.is_file():
                logger.error(f"Error: Input file not found at {filename}")
                return []

            with filepath.open('r', encoding='utf-8') as f:
                data = json.load(f)

            if not isinstance(data, list):
                 logger.error(f"Error: Input JSON is not a list. Found type: {type(data)}")
                 return []

            formatted_data = []
            skipped_count = 0
            for i, item in enumerate(data):
                # Basic structure check
                if not (isinstance(item, list) and len(item) == 2 and
                        isinstance(item[0], str) and isinstance(item[1], dict)):
                    logger.warning(f"Skipping invalid data format at index {i}: Expected [str, dict], got {type(item)} with content: {item}")
                    skipped_count += 1
                    continue

                text, annots = item
                current_annots = annots.copy() # Work on a copy

                # Validate and Convert 'entities'
                valid_entities = []
                entities_valid = True
                if "entities" in current_annots:
                    if not isinstance(current_annots["entities"], list):
                        logger.warning(f"Skipping item {i}: 'entities' is not a list in '{text}'. Annotations: {current_annots}")
                        skipped_count += 1
                        continue # Skip this item

                    for ent_idx, ent in enumerate(current_annots["entities"]):
                        # Allow list or tuple format initially
                        is_valid_format = False
                        start, end, label = -1, -1, ""
                        if isinstance(ent, (list, tuple)) and len(ent) == 3 and \
                           isinstance(ent[0], int) and isinstance(ent[1], int) and \
                           isinstance(ent[2], str):
                            start, end, label = ent
                            # Boundary and order checks
                            if 0 <= start <= end <= len(text):
                                is_valid_format = True
                            else:
                                logger.warning(f"Skipping item {i} due to invalid entity bounds at entity index {ent_idx}: {(start, end, label)} for text length {len(text)} in '{text}'. Annotations: {current_annots}")
                                entities_valid = False
                                break
                        else:
                            logger.warning(f"Skipping item {i} due to invalid entity format/type at entity index {ent_idx}: {ent} in '{text}'. Annotations: {current_annots}")
                            entities_valid = False
                            break # Stop processing entities for this item

                        if is_valid_format:
                             # Standardize to tuple
                            valid_entities.append((start, end, label))

                    if not entities_valid:
                         skipped_count += 1
                         continue # Skip this whole item if any entity was invalid

                    current_annots["entities"] = valid_entities # Store validated entities as tuples
                else:
                    # If 'entities' key is missing, initialize it as empty list
                    current_annots["entities"] = []


                # Validate 'cats'
                if "cats" in current_annots:
                    if not isinstance(current_annots["cats"], dict):
                        logger.warning(f"Skipping item {i}: 'cats' is not a dict in '{text}'. Annotations: {current_annots}")
                        skipped_count += 1
                        continue
                    # Optional: Check if values are numbers (float/int)
                    for cat_label, score in current_annots["cats"].items():
                         if not isinstance(score, (int, float)):
                              logger.warning(f"Skipping item {i}: 'cats' value for '{cat_label}' is not a number ({type(score)}) in '{text}'. Annotations: {current_annots}")
                              entities_valid = False # Reuse flag to skip item
                              break
                    if not entities_valid:
                        skipped_count += 1
                        continue
                else:
                     # If 'cats' key is missing, initialize it as empty dict
                     current_annots["cats"] = {}


                formatted_data.append((text, current_annots))

            if skipped_count > 0:
                logger.warning(f"Skipped {skipped_count} invalid data items during loading (check log for details).")
            logger.info(f"Loaded {len(formatted_data)} valid examples from {filename}")
            return formatted_data

        except FileNotFoundError: # Already handled by Path check, but keep for safety
            logger.error(f"Error: Input file not found at {filename}")
            return []
        except json.JSONDecodeError as e:
             logger.error(f"Error decoding JSON from {filename}: {e}")
             return []
        except Exception as e:
            logger.error(f"An unexpected error occurred loading data from {filename}: {e}", exc_info=True)
            return []

    def save_data(self, data: List[Tuple[str, Dict[str, Any]]], filename: str) -> None:
        """Save augmented data to a JSON file."""
        try:
            filepath = Path(filename)
            filepath.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists

            # Convert tuples in entities back to lists for JSON serialization
            serializable_data = []
            for text, annots in data:
                serializable_annots = annots.copy()
                if "entities" in serializable_annots:
                    # Convert entity tuples back to lists
                    serializable_annots["entities"] = [list(ent) for ent in annots.get("entities", [])]
                serializable_data.append([text, serializable_annots])

            with filepath.open('w', encoding='utf-8') as f:
                json.dump(serializable_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved {len(data)} examples to {filename}")
        except TypeError as e:
             logger.error(f"Error during serialization (maybe non-serializable data?): {e} in data near: {serializable_data[-1] if serializable_data else 'N/A'}", exc_info=True)
        except Exception as e:
            logger.error(f"Error saving data to {filename}: {e}", exc_info=True)

    def analyze_data(self, data: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, Any]:
        """Analyze the training data to understand its characteristics."""
        analysis = {
            "total_examples": len(data),
            "intent_distribution": Counter(), # Use Counter for convenience
            "entity_types": Counter(),
            "entity_values": Counter(), # Track specific entity text: "TYPE:text"
            "avg_text_length": 0,
            "text_length_distribution": Counter(), # Group by tens
            "potential_issues": [],
            "intent_labels_found": set(),
            "entity_labels_found": set(),
        }

        if not data:
            logger.warning("No data provided for analysis.")
            return analysis

        total_text_length = 0
        text_counts = Counter(text for text, _ in data) # Count text occurrences

        for text, annots in data:
            # Text length
            text_length = len(text)
            total_text_length += text_length
            analysis["text_length_distribution"][text_length // 10 * 10] += 1

            # Intent distribution - Ensure 'cats' exists and is dict
            cats = annots.get("cats", {})
            if isinstance(cats, dict) and cats:
                try:
                    # Find intent(s) with score > 0 (handle multi-label later if needed)
                    positive_intents = [intent for intent, score in cats.items() if isinstance(score, (int, float)) and score > 0]
                    if positive_intents:
                        # For simplicity, take the first positive intent found or one with max score
                        # A more robust approach might be needed for true multi-label scenarios
                        top_intent = max(cats, key=cats.get)
                        if cats[top_intent] > 0:
                             analysis["intent_distribution"][top_intent] += 1
                             analysis["intent_labels_found"].add(top_intent)
                        else:
                             # This case should be rare if positive_intents check works
                             analysis["potential_issues"].append(
                                 f"Example has 'cats' but max score is not positive: '{text[:80]}...' cats: {cats}"
                             )
                    else:
                         analysis["potential_issues"].append(
                             f"Example has 'cats' but no intent with score > 0: '{text[:80]}...' cats: {cats}"
                         )
                except Exception as e: # Catch errors during intent processing
                     analysis["potential_issues"].append(
                         f"Error processing 'cats' for example: '{text[:80]}...' cats: {cats} - Error: {e}"
                     )
            elif "cats" not in annots:
                 # This shouldn't happen if load_data initializes it, but check anyway
                 analysis["potential_issues"].append(
                     f"Example missing 'cats' key (should have been initialized): '{text[:80]}...'"
                 )
            # else: 'cats' is present but empty or invalid type (handled in load_data or first check)


            # Entity analysis - Ensure 'entities' exists and is list
            entities = annots.get("entities", [])
            if isinstance(entities, list):
                processed_entity_spans = set() # Avoid double counting overlapping entities in analysis
                for entity in entities:
                    if isinstance(entity, tuple) and len(entity) == 3:
                        start, end, label = entity
                        # Basic validation (already done in load_data, but double-check)
                        if not (isinstance(start, int) and isinstance(end, int) and isinstance(label, str) and 0 <= start <= end <= len(text)):
                            analysis["potential_issues"].append(
                                f"Invalid entity span/format detected during analysis: {entity} in '{text[:80]}...'"
                            )
                            continue

                        entity_span = (start, end)
                        if entity_span not in processed_entity_spans:
                            entity_text = text[start:end]
                            analysis["entity_types"][label] += 1
                            analysis["entity_values"][f"{label}:{entity_text}"] += 1 # Lacak nilai spesifik
                            analysis["entity_labels_found"].add(label)
                            processed_entity_spans.add(entity_span)
                    else:
                         analysis["potential_issues"].append(
                             f"Invalid entity format detected during analysis (expected tuple): {entity} in '{text[:80]}...'"
                         )


        # Calculate average text length
        if data:
            analysis["avg_text_length"] = total_text_length / len(data)

        # Analyze duplicates
        duplicate_count = 0
        unique_duplicates = 0
        for text, count in text_counts.items():
            if count > 1:
                duplicate_count += (count - 1) # Count extra copies
                unique_duplicates += 1
        if duplicate_count > 0:
            analysis["potential_issues"].append(
                f"Found {duplicate_count} duplicate text instance(s) "
                f"(across {unique_duplicates} unique texts that are duplicated)."
            )
            # Example duplicates (log first few)
            for text, count in text_counts.most_common(3):
                 if count > 1:
                     logger.debug(f"  - Duplicate example: '{text[:80]}...' (appears {count} times)")


        # Check for label imbalance
        if analysis["intent_distribution"]:
            total_intents_assigned = sum(analysis["intent_distribution"].values())
            if total_intents_assigned > 0:
                # Define a threshold for 'few examples' (e.g., < 10 or < 1% of total)
                min_examples_threshold = max(5, int(total_intents_assigned * 0.01))
                for intent, count in analysis["intent_distribution"].items():
                    if count < min_examples_threshold:
                        percentage = (count / total_intents_assigned) * 100
                        analysis["potential_issues"].append(
                            f"Low Example Count: Intent '{intent}' has only {count} examples ({percentage:.2f}%) - Consider adding more data or merging."
                        )
            else:
                 # This might happen if all 'cats' scores were 0 or negative
                 analysis["potential_issues"].append("No examples with positive intent scores found in 'cats'.")
        elif analysis["total_examples"] > 0:
            # If there's data but no intents were counted
             analysis["potential_issues"].append("No intents found or processed. Check 'cats' format and scores in data.")


        # Convert sets to sorted lists for stable output
        analysis["intent_labels_found"] = sorted(list(analysis["intent_labels_found"]))
        analysis["entity_labels_found"] = sorted(list(analysis["entity_labels_found"]))

        return analysis

    def _word_replacement(self, text: str, start_idx: int, end_idx: int,
                         replacement: str) -> Tuple[str, int]:
        """Replace a word/phrase in text and calculate length difference."""
        if start_idx < 0 or end_idx > len(text) or start_idx > end_idx:
             raise ValueError(f"Invalid indices for replacement: start={start_idx}, end={end_idx}, text_len={len(text)}")
        before = text[:start_idx]
        after = text[end_idx:]
        new_text = before + replacement + after
        length_diff = len(replacement) - (end_idx - start_idx)
        return new_text, length_diff

    def _adjust_entities(self, entities: List[Tuple[int, int, str]],
                        change_start: int, change_end: int, length_diff: int) -> Optional[List[Tuple[int, int, str]]]:
        """
        Adjust entity indices after text modification.
        Returns adjusted list or None if an unsafe overlap occurs.
        """
        adjusted = []
        # The point in the *original* text where the change started.
        # Indices need shifting if they start at or after this point,
        # OR if they overlap with the change region.
        shift_point = change_start

        for start, end, label in entities:
            # --- Overlap Check ---
            # Does the change interval [change_start, change_end) overlap
            # with the entity interval [start, end)?
            # Overlap = START_change < END_entity AND END_change > START_entity
            is_overlap = (change_start < end) and (change_end > start)

            if is_overlap:
                # --- Handle Overlap ---
                # This is complex. Replacing part of an entity invalidates its span.
                # Safest options:
                # 1. Discard the entire augmentation attempt (signal failure by returning None).
                # 2. Keep the original entity (might be wrong in the new text).
                # 3. Try to intelligently resize (very difficult).
                # Let's go with option 1: signal failure.
                logger.debug(f"Overlap detected: Change [{change_start}:{change_end}] overlaps with entity "
                             f"{(start, end, label)}. Discarding this augmentation variant.")
                return None # Signal failure

            # --- No Overlap: Adjust based on position relative to the change ---
            elif start >= change_end:
                # Entity is entirely AFTER the change: Shift both start and end.
                adjusted.append((start + length_diff, end + length_diff, label))
            elif end <= change_start:
                 # Entity is entirely BEFORE the change: No adjustment needed.
                 adjusted.append((start, end, label))
            # The case where change_start == end or change_end == start (touching, no overlap)
            # If start == change_end, it means entity starts right after change ends -> shift needed. covered by start >= change_end
            # If end == change_start, it means entity ends right before change starts -> no shift needed. covered by end <= change_start
            else:
                 # This case should theoretically not be reached if overlap logic is correct.
                 logger.warning(f"Unexpected case in entity adjustment: Entity {(start, end, label)} "
                                f"relative to change [{change_start}:{change_end}]. Keeping original.")
                 adjusted.append((start, end, label))

        return adjusted

    def _validate_entities_after_augmentation(self, text: str, entities: List[Tuple[int, int, str]]) -> Optional[List[Tuple[int, int, str]]]:
        """Checks if all entity boundaries are valid within the new text."""
        validated_entities = []
        text_len = len(text)
        for start, end, label in entities:
            if 0 <= start <= end <= text_len:
                # Optional: Check if entity text still makes sense (e.g., not just whitespace)
                # span_text = text[start:end]
                # if not span_text.isspace():
                validated_entities.append((start, end, label))
            else:
                logger.warning(f"Invalid entity bounds after augmentation: {(start, end, label)} "
                               f"in text (len {text_len}): '{text[:80]}...'. Discarding variant.")
                return None # Indicate failure
        return validated_entities


    def augment_with_word_substitution(self, example: Tuple[str, Dict[str, Any]],
                                      substitution_prob: float = 0.3) -> List[Tuple[str, Dict[str, Any]]]:
        """Create variants by substituting words with their variations, handling entities carefully."""
        original_text, original_annots = example
        original_entities = original_annots.get("entities", [])

        augmented_examples = []
        processed_texts_in_batch = set() # Avoid duplicates within this function call
        processed_texts_in_batch.add(original_text)

        # Use spaCy doc if available, otherwise basic split
        try:
            doc = nlp(original_text)
            tokens = list(doc)
        except Exception as e:
            logger.warning(f"spaCy processing failed for text: '{original_text[:80]}...'. Error: {e}. Falling back to basic split.", exc_info=True)
            # Basic whitespace split as fallback (less accurate)
            tokens = [SimpleToken(t, i) for i, t in enumerate(original_text.split())] # Requires a dummy SimpleToken class or alternative

        # Try generating multiple variants
        max_variants_per_example = 3
        attempts_per_variant = 5 + int(len(tokens) * 0.1) # More attempts for longer text

        for _ in range(max_variants_per_example):
            variant_generated = False
            for attempt in range(attempts_per_variant):
                if variant_generated: break # Stop trying if we got one for this slot

                current_text = original_text
                current_entities = list(original_entities) # Fresh copy for each attempt
                made_change_in_attempt = False

                # Shuffle token indices for randomness
                shuffled_indices = list(range(len(tokens)))
                random.shuffle(shuffled_indices)

                # Iterate through tokens in random order
                for token_idx in shuffled_indices:
                    token = tokens[token_idx]
                    token_text = token.text

                    # Skip punctuation, spaces, or empty tokens
                    if not isinstance(token_text, str) or not token_text.strip() or (hasattr(token, 'is_punct') and token.is_punct) or (hasattr(token, 'is_space') and token.is_space):
                        continue

                    # Probabilistic substitution
                    if random.random() > substitution_prob:
                        continue

                    # --- Find token position in CURRENT text ---
                    try:
                        # Use regex to find the token as a whole word in the current text
                        # Need start/end relative to current_text
                        # Heuristic: Find closest match to original token.idx if possible
                        original_start_char = token.idx if hasattr(token, 'idx') else -1 # SpaCy token has idx

                        matches = list(re.finditer(r'\b' + re.escape(token_text) + r'\b', current_text))
                        if not matches:
                            # logger.debug(f"Token '{token_text}' not found in current augmented text: '{current_text}'. Skipping.")
                            continue

                        if original_start_char != -1:
                             # Find match closest to original position
                             best_match = min(matches, key=lambda m: abs(m.start() - original_start_char))
                        else:
                             # If no original index, just pick the first match (less ideal)
                             best_match = matches[0]

                        start_idx = best_match.start()
                        end_idx = best_match.end()

                    except Exception as e:
                        logger.warning(f"Error finding token '{token_text}' in '{current_text}': {e}. Skipping substitution.")
                        continue

                    # --- Check if token overlaps with an existing entity in CURRENT entities ---
                    is_part_of_entity = False
                    token_span = (start_idx, end_idx)
                    for ent_start, ent_end, _ in current_entities:
                        # Overlap check: max(start1, start2) < min(end1, end2)
                        if max(token_span[0], ent_start) < min(token_span[1], ent_end):
                            # logger.debug(f"Token '{token_text}' at {token_span} overlaps with entity [{ent_start}:{ent_end}], skipping substitution.")
                            is_part_of_entity = True
                            break
                    if is_part_of_entity:
                        continue # Do not substitute tokens that are part of entities

                    # --- Perform Substitution ---
                    replacement = None
                    token_text_lower = token_text.lower()

                    # Check Entity Variations first (more specific)
                    original_entity_term = self.reverse_entity_map.get(token_text_lower)
                    if original_entity_term:
                        choices = [v for v in self.entity_variations[original_entity_term] if v.lower() != token_text_lower]
                        # Also consider the canonical term itself if the current token is a variant
                        if original_entity_term.lower() != token_text_lower:
                            choices.append(original_entity_term)
                        if choices:
                            replacement = random.choice(choices)

                    # Check Informal Variations if no entity match
                    if not replacement:
                        original_informal_term = self.reverse_informal_map.get(token_text_lower)
                        if original_informal_term:
                            choices = [v for v in self.informal_variations[original_informal_term] if v.lower() != token_text_lower]
                            # Also consider the canonical term
                            if original_informal_term.lower() != token_text_lower:
                                 choices.append(original_informal_term)
                            if choices:
                                replacement = random.choice(choices)

                    # If a replacement is found
                    if replacement and replacement.lower() != token_text_lower : # Ensure replacement is different
                        try:
                            new_text_candidate, diff = self._word_replacement(
                                current_text, start_idx, end_idx, replacement
                            )

                            # --- Adjust Entities ---
                            # This returns None if there's an overlap, indicating failure
                            adjusted_entities = self._adjust_entities(
                                current_entities, start_idx, end_idx, diff
                            )

                            if adjusted_entities is not None:
                                # Success: Update text and entities for the *next* token in this attempt
                                current_text = new_text_candidate
                                current_entities = adjusted_entities
                                made_change_in_attempt = True
                                # logger.debug(f"Substituted '{token_text}' with '{replacement}' -> '{current_text[:80]}...'")
                                # Continue to potentially substitute other tokens in this same attempt
                            # else: # adjusted_entities is None (overlap occurred)
                                # logger.debug(f"Substitution of '{token_text}' failed due to entity overlap.")
                                # Do not update text/entities, try next token or attempt

                        except ValueError as ve:
                             logger.warning(f"ValueError during word replacement: {ve}. Skipping change.")
                        except Exception as e:
                            logger.warning(f"Error during substitution/adjustment for token '{token_text}' with '{replacement}': {e}", exc_info=True)
                            # Continue to next token or attempt


                # --- After iterating through all tokens for one attempt ---
                if made_change_in_attempt and current_text != original_text and current_text not in processed_texts_in_batch:
                    # Final validation of entities in the generated text
                    final_entities = self._validate_entities_after_augmentation(current_text, current_entities)

                    if final_entities is not None: # If validation passed
                        new_annots = original_annots.copy()
                        new_annots["entities"] = final_entities
                        augmented_examples.append((current_text, new_annots))
                        processed_texts_in_batch.add(current_text)
                        variant_generated = True # Mark that we generated a variant in this slot
                        # logger.info(f"Successfully generated variant: {current_text[:80]}...")
                        break # Move to the next variant slot

            # End of attempts for one variant slot

        return augmented_examples


    def augment_with_structure_variation(self, example: Tuple[str, Dict[str, Any]]) -> List[Tuple[str, Dict[str, Any]]]:
        """Create variants by adding/changing sentence starters or greetings."""
        original_text, original_annots = example
        original_entities = original_annots.get("entities", [])

        augmented_examples = []
        processed_texts_in_batch = set()
        processed_texts_in_batch.add(original_text)

        max_variants = 2 # Generate max 2 structural variants

        # --- 1. Greeting Variation ---
        text_without_greeting = original_text
        greeting_offset = 0 # Offset from original text start due to greeting removal

        # Try to identify and remove existing greeting (case-insensitive, start of string)
        # Make pattern more robust for optional punctuation/space
        # Pattern: ^\s*(greeting)[\s,.!?]+
        removed_greeting = False
        for greeting in self.greeting_variations:
            # Use word boundary \b ? Maybe not needed if ^ anchors it. Add optional space before.
            pattern = rf"^\s*({re.escape(greeting)})([\s,.!?]+|$)"
            match = re.search(pattern, original_text, re.IGNORECASE)
            if match:
                # Found a greeting
                cut_point = match.end(0) # End of the matched greeting + separator
                text_without_greeting = original_text[cut_point:]
                greeting_offset = -cut_point # Negative offset
                removed_greeting = True
                # logger.debug(f"Removed greeting '{match.group(1)}', offset: {greeting_offset}")
                break # Stop after finding the first match

        # Add new/different greetings
        greetings_to_try = random.sample(self.greeting_variations, min(3, len(self.greeting_variations)))
        added_greeting_variants = 0
        for new_greeting in greetings_to_try:
             if added_greeting_variants >= max_variants: break

             # Check if adding this greeting makes sense (e.g., don't add if removed same one)
             # A simple check: don't add back the exact same greeting if one was removed
             if removed_greeting and new_greeting.lower() == match.group(1).lower():
                 continue

             # Randomly add separator (or not for single word greetings like 'Pagi')
             separator = random.choice([", ", " "]) if len(new_greeting.split()) > 1 or random.random() > 0.3 else " "
             prefix = f"{new_greeting}{separator}"
             new_text = prefix + text_without_greeting

             if new_text not in processed_texts_in_batch:
                 prefix_len_change = len(prefix) + greeting_offset # Net change from original text start
                 new_entities = []
                 valid_entities = True
                 for start, end, label in original_entities:
                     new_start = start + prefix_len_change
                     new_end = end + prefix_len_change
                     # Basic check - full validation later
                     if new_start >= 0 and new_end >= new_start:
                         new_entities.append((new_start, new_end, label))
                     else:
                         # If offset makes start negative, this augmentation is invalid
                         logger.debug(f"Greeting '{new_greeting}' caused invalid entity shift for {(start, end, label)}. Skipping.")
                         valid_entities = False
                         break

                 if valid_entities:
                     # Validate final entity boundaries
                     final_entities = self._validate_entities_after_augmentation(new_text, new_entities)
                     if final_entities is not None:
                         new_annots = original_annots.copy()
                         new_annots["entities"] = final_entities
                         augmented_examples.append((new_text, new_annots))
                         processed_texts_in_batch.add(new_text)
                         added_greeting_variants += 1

        # --- 2. Question Starter Variation ---
        # Apply this to the text *potentially already modified by greeting removal*
        # Base text for this step: text_without_greeting
        # Base offset from original: greeting_offset
        added_question_variants = 0
        if len(augmented_examples) < max_variants: # Only try if we still need variants

            # Check if the base text looks like a question
            base_text_lower = text_without_greeting.lower().strip()
            is_already_question = base_text_lower.endswith("?")
            for starter in self.question_starters:
                 # Check if starter appears near the beginning
                 if re.match(rf"^\s*{re.escape(starter)}\b", base_text_lower):
                      is_already_question = True
                      break

            # If it doesn't look like a question, try adding a starter
            if not is_already_question:
                 starters_to_try = random.sample(self.question_starters, min(2, len(self.question_starters)))
                 for new_starter in starters_to_try:
                      if added_question_variants >= (max_variants - len(augmented_examples)): break

                      # Add connector word sometimes
                      connector = random.choice(["", random.choice(self.connecting_words)])
                      prefix = f"{new_starter} "
                      if connector:
                          prefix += f"{connector} "

                      # Add question mark if missing
                      suffix = "?" if not text_without_greeting.strip().endswith("?") else ""

                      new_text = prefix + text_without_greeting.strip() + suffix

                      if new_text not in processed_texts_in_batch:
                          prefix_len_change = len(prefix) + greeting_offset # Net change from original text start
                          # Entity adjustment only depends on prefix change here
                          new_entities = []
                          valid_entities = True
                          for start, end, label in original_entities:
                              new_start = start + prefix_len_change
                              new_end = end + prefix_len_change
                              if new_start >= 0 and new_end >= new_start:
                                  new_entities.append((new_start, new_end, label))
                              else:
                                  logger.debug(f"Question starter '{new_starter}' caused invalid entity shift for {(start, end, label)}. Skipping.")
                                  valid_entities = False
                                  break

                          if valid_entities:
                              # Validate final boundaries
                              final_entities = self._validate_entities_after_augmentation(new_text, new_entities)
                              if final_entities is not None:
                                  new_annots = original_annots.copy()
                                  new_annots["entities"] = final_entities
                                  augmented_examples.append((new_text, new_annots))
                                  processed_texts_in_batch.add(new_text)
                                  added_question_variants += 1


        return augmented_examples

    def augment_data(self, data: List[Tuple[str, Dict[str, Any]]],
                   target_multiplier: float = 2.0,
                   min_examples_per_intent: int = 10) -> List[Tuple[str, Dict[str, Any]]]:
        """Augment the training data focusing on balancing intents and variety."""
        if not data:
             logger.error("Cannot augment empty data.")
             return []

        original_data_count = len(data)
        augmented_data = list(data)  # Start with the original data
        # Use a set to track text content of all examples (original + augmented) for uniqueness
        all_texts = {text for text, _ in data}

        # --- Analyze original data for balancing targets ---
        analysis = self.analyze_data(data)
        original_intent_counts = analysis["intent_distribution"]
        total_original_examples = analysis["total_examples"] # Should be same as original_data_count

        if not original_intent_counts:
            logger.warning("No intents found in the original data analysis. Augmentation will proceed without intent balancing.")
            # Target total based purely on multiplier if no intents
            target_total_examples = int(total_original_examples * target_multiplier)
            intents_to_balance = []
            target_per_intent = {} # No specific intent targets
            examples_by_intent = {} # No intent grouping
            other_examples = list(data) # All examples are "other"
        else:
            logger.info("Analyzing intent distribution for balancing...")
            num_intents = len(original_intent_counts)
            # --- Calculate Target Counts ---
            # 1. Overall target based on multiplier
            target_total_overall = int(total_original_examples * target_multiplier)

            # 2. Target per intent for balancing
            target_per_intent = {}
            ideal_target_per_intent = max(min_examples_per_intent, int(total_original_examples / num_intents if num_intents > 0 else min_examples_per_intent))
            logger.info(f"Targeting at least {min_examples_per_intent} examples per intent.")
            logger.info(f"Heuristic ideal count per intent (avg/min): {ideal_target_per_intent}")

            for intent, count in original_intent_counts.items():
                # Aim for at least the ideal count, or slightly more than current if already above ideal
                target_per_intent[intent] = max(ideal_target_per_intent, int(count * 1.2)) # Aim a bit higher than current if already good

            # 3. Total target based on sum of per-intent targets (can exceed multiplier target)
            target_total_balanced = sum(target_per_intent.values())

            # 4. Final target: Max of overall target and balanced target? Or Min?
            # Let's use the multiplier as the primary driver, but ensure low-count intents get boosted.
            final_target_total = target_total_overall
            logger.info(f"Overall target number of examples: {final_target_total} (from multiplier {target_multiplier})")


            # --- Prioritize intents needing more examples ---
            intent_needs = {}
            for intent, count in original_intent_counts.items():
                 needed = target_per_intent.get(intent, ideal_target_per_intent) - count
                 if needed > 0:
                     intent_needs[intent] = needed

            # Sort intents by how many examples they need (descending)
            intents_to_balance = sorted(intent_needs.keys(), key=lambda i: intent_needs[i], reverse=True)
            logger.info(f"Prioritizing augmentation for intents needing examples: {intents_to_balance}")

            # --- Group examples by intent ---
            examples_by_intent = defaultdict(list)
            other_examples = [] # Examples without a clear positive intent
            for example in data:
                text, annots = example
                cats = annots.get("cats", {})
                if isinstance(cats, dict) and cats:
                    positive_intents = [intent for intent, score in cats.items() if isinstance(score, (int, float)) and score > 0]
                    if positive_intents:
                        # Assign to the highest scoring positive intent for augmentation source selection
                        top_intent = max(cats, key=cats.get)
                        if cats[top_intent] > 0:
                            examples_by_intent[top_intent].append(example)
                        else: # Should not happen based on positive_intents check
                             other_examples.append(example)
                    else:
                        other_examples.append(example) # No positive score
                else:
                    other_examples.append(example) # Missing or invalid cats

        # --- Augmentation Loop ---
        newly_added_count = 0
        max_new_examples = final_target_total - total_original_examples
        if max_new_examples <= 0:
             logger.info("Target size is not larger than original data size. No augmentation needed.")
             return augmented_data

        logger.info(f"Attempting to generate approximately {max_new_examples} new examples...")

        # Use a combined pool of examples, prioritizing based on intent needs
        source_pool = []
        # Add examples from prioritized intents multiple times to increase their chance
        for intent in intents_to_balance:
            if intent in examples_by_intent:
                 needed_multiplier = max(1, int(intent_needs[intent] / len(examples_by_intent[intent])) if examples_by_intent[intent] else 1)
                 source_pool.extend(examples_by_intent[intent] * needed_multiplier)
                 logger.debug(f"Adding examples for intent '{intent}' with multiplier {needed_multiplier}")

        # Add examples from intents that already meet the target (add once)
        for intent, examples in examples_by_intent.items():
            if intent not in intents_to_balance:
                 source_pool.extend(examples)

        # Add examples with no clear intent
        source_pool.extend(other_examples)

        if not source_pool:
            logger.error("No source examples available for augmentation after processing intents. Cannot proceed.")
            return data # Return original data

        logger.info(f"Created augmentation source pool with {len(source_pool)} entries (includes duplicates for balancing).")

        with tqdm(total=max_new_examples, desc="Augmenting data", unit=" examples") as pbar:
            while newly_added_count < max_new_examples:
                # Randomly select an example from the weighted pool
                example_to_augment = random.choice(source_pool)

                # Choose augmentation method randomly (give word sub higher chance)
                methods = [
                    self.augment_with_word_substitution,
                    self.augment_with_structure_variation,
                    self.augment_with_word_substitution # Weight towards substitution
                ]
                augmentation_method = random.choice(methods)

                try:
                    # Generate potential new variants (method handles internal uniqueness)
                    new_variants = augmentation_method(example_to_augment)

                    # Add variants to dataset if they are globally unique
                    added_in_batch = 0
                    for variant in new_variants:
                        variant_text, _ = variant
                        if variant_text not in all_texts:
                            augmented_data.append(variant)
                            all_texts.add(variant_text)
                            newly_added_count += 1
                            added_in_batch += 1
                            pbar.update(1) # Increment progress bar
                            if newly_added_count >= max_new_examples:
                                break # Stop if target reached

                    if newly_added_count >= max_new_examples:
                        break # Stop if target reached

                except Exception as e:
                     logger.error(f"Error during augmentation for example: {example_to_augment[0][:80]}... using {augmentation_method.__name__}. Error: {e}", exc_info=True)
                     # Continue with the next example

                # Safety break: If the source pool is exhausted and no new examples are generated
                # This simple loop doesn't track exhaustion well, but tqdm handles the count target.


        logger.info(f"Augmentation complete.")
        logger.info(f"Original examples: {total_original_examples}")
        logger.info(f"Newly generated unique examples: {newly_added_count}")
        logger.info(f"Total examples after augmentation: {len(augmented_data)}")

        if newly_added_count < max_new_examples:
             logger.warning(f"Target generation ({max_new_examples} new) not fully met. Generated {newly_added_count} new unique examples.")
        elif newly_added_count > max_new_examples:
             logger.info(f"Generated slightly more examples ({newly_added_count}) than the target ({max_new_examples}) due to batch generation.")

        return augmented_data


# Helper for fallback tokenization if spaCy fails completely
class SimpleToken:
     def __init__(self, text, idx):
         self.text = text
         self.idx = idx # Character index is harder to get here, use word index
         self.is_punct = False # Basic assumption
         self.is_space = False

def main():
    """Main function to run the data augmentation."""
    parser = argparse.ArgumentParser(
        description="Augment training data (JSON format [text, {annotations}]) for NLP models.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--input", type=str, required=True, help="Input JSON file with training data")
    parser.add_argument("--output", type=str, required=True, help="Output file for augmented data")
    parser.add_argument("--multiplier", type=float, default=2.5, help="Target size multiplier relative to original data (approximate)")
    parser.add_argument("--min-intent-examples", type=int, default=15, help="Minimum examples desired per intent after augmentation (used for balancing)")
    parser.add_argument("--analyze-only", action="store_true", help="Only analyze input data without performing augmentation")
    parser.add_argument("--substitution-prob", type=float, default=0.3, help="Probability of substituting a single word in substitution augmentation")
    args = parser.parse_args()

    logger.info("Starting Data Augmentation Script...")
    logger.info(f"Input file: {args.input}")
    logger.info(f"Output file: {args.output}")
    logger.info(f"Target Multiplier: {args.multiplier}")
    logger.info(f"Min Examples per Intent: {args.min_intent_examples}")
    logger.info(f"Substitution Probability: {args.substitution_prob}")

    augmenter = DataAugmenter()

    # Validate output path
    output_path = Path(args.output)
    if output_path.is_dir():
        logger.error(f"Output path '{args.output}' is a directory. Please specify a file path.")
        return
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True) # Create parent dirs if needed
    except OSError as e:
         logger.error(f"Could not create output directory {output_path.parent}: {e}")
         return


    # Load data
    logger.info("Loading data...")
    data = augmenter.load_data(args.input)
    if not data:
        logger.error("No valid data loaded. Exiting.")
        return

    # Analyze original data
    logger.info("\n--- Analyzing Original Data ---")
    analysis = augmenter.analyze_data(data)

    # Print analysis results nicely
    logger.info(f"Total valid examples: {analysis['total_examples']}")
    logger.info(f"Average text length: {analysis['avg_text_length']:.2f} characters")

    if analysis['intent_distribution']:
        logger.info(f"Intent Distribution ({len(analysis['intent_distribution'])} intents found):")
        total_intent_samples = sum(analysis['intent_distribution'].values())
        sorted_intents = sorted(analysis['intent_distribution'].items(), key=lambda item: item[1], reverse=True)
        for intent, count in sorted_intents:
            percentage = (count / total_intent_samples) * 100 if total_intent_samples > 0 else 0
            logger.info(f"  - {intent}: {count} ({percentage:.1f}%)")
    else:
         logger.info("No intents found or processed in the original data.")

    if analysis['entity_types']:
        logger.info(f"Entity Type Distribution ({len(analysis['entity_types'])} types found):")
        total_entity_samples = sum(analysis['entity_types'].values())
        sorted_entities = sorted(analysis['entity_types'].items(), key=lambda item: item[1], reverse=True)
        for entity_type, count in sorted_entities:
            percentage = (count / total_entity_samples) * 100 if total_entity_samples > 0 else 0
            logger.info(f"  - {entity_type}: {count} ({percentage:.1f}%)")

        # Log top N specific entity values if desired (can be verbose)
        # logger.info("Top 10 specific entity values encountered:")
        # for entity_val, count in analysis['entity_values'].most_common(10):
        #     logger.info(f"  - {entity_val}: {count}")
    else:
        logger.info("No entities found in the original data.")


    if analysis['potential_issues']:
        logger.warning(f"\n--- Potential Issues Found in Original Data ({len(analysis['potential_issues'])}) ---")
        for i, issue in enumerate(analysis['potential_issues']):
            if i < 15: # Limit console output
                logger.warning(f"  - {issue}")
            else:
                 # Log all issues to file anyway
                 file_handler.handle(logging.LogRecord(
                    name=logger.name, level=logging.WARNING, pathname="", lineno=0,
                    msg=f"  - {issue}", args=[], exc_info=None, func=""
                 ))
        if len(analysis['potential_issues']) > 15:
            logger.warning("  - ... (more issues logged in data_augmentation.log)")
        logger.warning("--- End of Original Data Issues ---")


    # Stop here if analyze-only flag is set
    if args.analyze_only:
        logger.info("\n--- Analysis complete. Exiting as --analyze-only flag was used. ---")
        return

    # Augment data
    logger.info("\n--- Starting Data Augmentation ---")
    # Pass substitution probability to the relevant augmentation method if needed,
    # or set it as a class attribute if it's used across methods.
    # Here, we pass it directly to the method that uses it.
    # Note: Augmenter class needs modification if we want to pass prob this way.
    # Easier: Let augment_data call the methods which use their default/internal prob.
    # For more control, modify `augment_data` to pass args.substitution_prob
    # to `augment_with_word_substitution`. Let's modify augment_data slightly.

    # --- MODIFICATION NEEDED in augment_data or methods to use args.substitution_prob ---
    # Option A: Modify methods to accept prob ( cleaner )
    # Option B: Set augmenter attribute ( simpler for now )
    augmenter.substitution_prob = args.substitution_prob # Set instance attribute

    # Modify augment_with_word_substitution to use self.substitution_prob if prob not passed
    # (This requires changing the method signature or logic slightly. Let's assume
    # the existing method uses a default or we adjust it mentally for now. The provided
    # code uses a default in the method signature.)
    # Let's stick to the default defined in the method for now unless explicitly overridden.

    augmented_data = augmenter.augment_data(
        data,
        target_multiplier=args.multiplier,
        min_examples_per_intent=args.min_intent_examples
        # We are not passing substitution_prob here, method uses its default or class attribute
    )

    if not augmented_data or len(augmented_data) == len(data):
         logger.warning("Augmentation did not produce new examples or failed. Saving original data.")
         if not augmented_data: augmented_data = data # Ensure we save something

    # Analyze augmented data
    logger.info("\n--- Analyzing Augmented Data ---")
    aug_analysis = augmenter.analyze_data(augmented_data)

    logger.info(f"Original examples: {analysis['total_examples']}")
    logger.info(f"Total examples after augmentation: {aug_analysis['total_examples']}")
    if aug_analysis['intent_distribution']:
        logger.info(f"Intent Distribution in Augmented Data ({len(aug_analysis['intent_distribution'])} intents):")
        total_intent_samples_aug = sum(aug_analysis['intent_distribution'].values())
        sorted_intents_aug = sorted(aug_analysis['intent_distribution'].items(), key=lambda item: item[1], reverse=True)
        for intent, count in sorted_intents_aug:
            percentage = (count / total_intent_samples_aug) * 100 if total_intent_samples_aug > 0 else 0
            logger.info(f"  - {intent}: {count} ({percentage:.1f}%)")
    else:
         logger.info("No intent distribution data found in augmented data.")

    if aug_analysis['potential_issues']:
         logger.warning(f"\n--- Potential Issues Found in Augmented Data ({len(aug_analysis['potential_issues'])}) ---")
         for i, issue in enumerate(aug_analysis['potential_issues']):
             if i < 10: logger.warning(f"  - {issue}")
             else:
                 file_handler.handle(logging.LogRecord(
                    name=logger.name, level=logging.WARNING, pathname="", lineno=0,
                    msg=f"  - {issue}", args=[], exc_info=None, func=""
                 ))
         if len(aug_analysis['potential_issues']) > 10:
             logger.warning("  - ... (more issues logged in data_augmentation.log)")
         logger.warning("--- End of Augmented Data Issues ---")

    # Save augmented data
    logger.info("\n--- Saving Augmented Data ---")
    augmenter.save_data(augmented_data, args.output)
    logger.info("--- Augmentation and Saving Complete ---")


if __name__ == "__main__":
    main()
# --- END OF FILE data_augmentation.py ---