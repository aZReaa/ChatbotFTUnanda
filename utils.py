from markupsafe import escape
import re

def format_idr(amount):
    """Memformat angka menjadi string Rupiah.

    Args:
        amount (int/float/str): Jumlah yang akan diformat.

    Returns:
        str: Jumlah dalam format Rupiah (misal: Rp 1.000.000).
    """
    if amount is None or amount == "N/A":
        return "Informasi belum tersedia"
    try:
        numeric_amount = float(amount)
        return f"Rp {numeric_amount:,.0f}".replace(',', '.')
    except (ValueError, TypeError):
        return str(amount)

def sanitize_input(text, max_length=500):
    """Membersihkan input pengguna dari karakter berbahaya dan membatasi panjangnya.

    Args:
        text (str): Teks input pengguna.
        max_length (int): Panjang maksimum teks yang diizinkan.

    Returns:
        tuple: (str, str) - (Teks yang sudah dibersihkan, pesan error jika ada).
    """
    if not isinstance(text, str):
        return None, "Input harus berupa teks."

    # Batasi panjang teks
    if len(text) > max_length:
        return None, f"Teks terlalu panjang, maksimum {max_length} karakter."

    # Hapus karakter berbahaya (contoh: script tags, karakter khusus)
    text = re.sub(r'<[^>]+>', '', text)  # Hapus tag HTML
    text = escape(text.strip())  # Sanitasi dan hapus whitespace berlebih

    return text, None

def normalize_text(text):
    """Menormalkan teks untuk pemrosesan lebih lanjut (lowercase dan hapus karakter berlebih).

    Args:
        text (str): Teks input.

    Returns:
        str: Teks yang sudah dinormalkan.
    """
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text.strip())  # Ganti spasi berlebih dengan satu spasi
    return text.lower()

# Contoh penggunaan (untuk testing)
if __name__ == "__main__":
    # Test format_idr
    print(format_idr(1000000))  # Output: Rp 1.000.000
    print(format_idr("N/A"))    # Output: Informasi belum tersedia

    # Test sanitize_input
    text, error = sanitize_input("<script>alert('hacked')</script> Halo!")
    print(f"Sanitized: {text}, Error: {error}")  # Output: Sanitized: alert('hacked') Halo!, Error: None

    # Test normalize_text
    print(normalize_text("  Halo   Dunia!  "))  # Output: halo dunia!