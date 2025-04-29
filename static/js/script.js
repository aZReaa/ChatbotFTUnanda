document.getElementById("chat-form").addEventListener("submit", function(event) {
    event.preventDefault();

    const userInputField = document.getElementById("user-input"); // Ambil elemen input
    const userInput = userInputField.value.trim(); // Trim di awal
    const responseContainer = document.getElementById("response-container");

    // Pastikan userInput tidak kosong sebelum menampilkan dan mengirim
    if (!userInput) { // Cek string yang sudah di-trim
        return; // Jangan lakukan apa-apa jika input kosong
    }

    // --- Menampilkan input pengguna (MODIFIED) ---
    // Hapus baris lama: responseContainer.innerHTML += `<div><strong>You:</strong> ${escapeHTML(userInput)}</div>`;
    const userBubble = document.createElement('div');
    userBubble.classList.add('chat-bubble', 'user');
    // Menggunakan textContent lebih aman dan efisien daripada innerHTML + escapeHTML
    userBubble.textContent = userInput;
    responseContainer.appendChild(userBubble);
    // Scroll ke bawah setelah menambahkan pesan pengguna
    responseContainer.scrollTop = responseContainer.scrollHeight;

    // Kosongkan input field SEGERA setelah pesan pengguna ditampilkan
    userInputField.value = "";

    // Mengirim data ke Flask server menggunakan fetch API
    fetch('/predict', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text: userInput }) // Pastikan backend membaca 'text'
    })
    .then(response => {
        if (!response.ok) {
            // Tangani error HTTP (misal: 500 Internal Server Error)
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        // --- Menampilkan respons dari Flask (chatbot) (MODIFIED) ---
        const botReplyText = data.answer || "Maaf, terjadi kesalahan dalam menerima respons."; // Fallback jika answer tidak ada
        // Hapus baris lama: const botResponse = `<div><strong>Bot:</strong> ${escapeHTML(botReplyText)}</div>`; responseContainer.innerHTML += botResponse;
        const botBubble = document.createElement('div');
        botBubble.classList.add('chat-bubble', 'bot');
        botBubble.textContent = botReplyText; // textContent lebih aman
        responseContainer.appendChild(botBubble);
    })
    .catch(error => {
        console.error('Error fetching prediction:', error);
        // --- Tampilkan pesan error ke pengguna (MODIFIED) ---
        // Hapus baris lama: responseContainer.innerHTML += `<div><strong>Bot:</strong> Maaf, terjadi masalah...</div>`;
        const errorBubble = document.createElement('div');
        errorBubble.classList.add('chat-bubble', 'bot'); // Tampilkan error sebagai bubble bot
        errorBubble.textContent = "Maaf, terjadi masalah saat menghubungi server. Coba lagi nanti.";
        responseContainer.appendChild(errorBubble);
    })
    .finally(() => {
         // Selalu scroll ke bawah setelah respons bot atau error ditampilkan
         responseContainer.scrollTop = responseContainer.scrollHeight;
         // Pengosongan input sudah dipindahkan ke atas agar lebih responsif
    });
});
