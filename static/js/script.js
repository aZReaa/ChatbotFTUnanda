document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById("chat-form");
    const userInputField = document.getElementById("user-input");
    const responseContainer = document.getElementById("response-container");
    const initialBotMessageWrapper = responseContainer.querySelector('.message-wrapper.bot-wrapper');

    // Fungsi untuk format waktu (HH:MM)
    function formatTime(date) {
        const hours = date.getHours().toString().padStart(2, '0');
        const minutes = date.getMinutes().toString().padStart(2, '0');
        return `${hours}:${minutes}`;
    }

    // Fungsi untuk menambahkan pesan ke chatbox
    function addMessage(sender, text, isHTML = false) {
        const messageWrapper = document.createElement('div');
        messageWrapper.classList.add('message-wrapper', `${sender}-wrapper`);

        const bubble = document.createElement('div');
        bubble.classList.add('chat-bubble', sender);
        if (isHTML) {
            bubble.innerHTML = text; // Gunakan innerHTML untuk typing indicator
        } else {
            bubble.textContent = text;
        }

        const timestamp = document.createElement('div');
        timestamp.classList.add('timestamp');
        timestamp.textContent = formatTime(new Date());

        messageWrapper.appendChild(bubble);
        messageWrapper.appendChild(timestamp);
        responseContainer.appendChild(messageWrapper);

        // Scroll ke bawah setelah menambahkan pesan
        responseContainer.scrollTop = responseContainer.scrollHeight;

        return messageWrapper; // Kembalikan wrapper untuk referensi (misal loading)
    }

     // Tambahkan timestamp ke pesan bot awal jika ada
    if (initialBotMessageWrapper) {
        const initialTimestamp = document.createElement('div');
        initialTimestamp.classList.add('timestamp');
        initialTimestamp.textContent = formatTime(new Date()); // Waktu saat halaman load
        initialBotMessageWrapper.appendChild(initialTimestamp);
        // Trigger animasi untuk pesan awal
        initialBotMessageWrapper.style.opacity = '1';
        initialBotMessageWrapper.style.transform = 'translateY(0) scale(1)';
    }


    chatForm.addEventListener("submit", function(event) {
        event.preventDefault();

        const userInput = userInputField.value.trim();
        if (!userInput) return;

        // Tampilkan pesan pengguna
        addMessage('user', userInput);

        // Kosongkan input field
        userInputField.value = "";
        userInputField.focus(); // Fokus kembali ke input

        // Tampilkan loading indicator (typing indicator)
        const loadingWrapper = addMessage('bot', '<div class="typing-indicator"><span></span><span></span><span></span></div>', true);

        // *** BAGIAN INI TIDAK DIUBAH (Interaksi Backend) ***
        fetch('/predict', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ text: userInput })
        })
        .then(response => {
            if (!response.ok) {
                // Tangani error HTTP (misal: 500 Internal Server Error)
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            loadingWrapper.remove(); // Hapus loading indicator
            // Tampilkan respons bot
            addMessage('bot', data.answer || "Maaf, saya tidak bisa memproses permintaan Anda saat ini.");
        })
        .catch(error => {
            console.error('Fetch Error:', error);
            loadingWrapper.remove(); // Hapus loading indicator jika ada error
            // Tampilkan pesan error yang lebih ramah
            addMessage('bot', "Waduh, sepertinya ada gangguan jaringan atau server. Silakan coba lagi beberapa saat.");
        })
        // .finally(() => {
            // Scroll sudah dilakukan di dalam addMessage
        // });
         // *** AKHIR BAGIAN YANG TIDAK DIUBAH ***
    });
});

// Fungsi sendQuickQuestion sudah dihapus sebelumnya