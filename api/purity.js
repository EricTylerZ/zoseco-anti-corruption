const SERVER_URL = "https://anti-corruption-bot-git-purity-test-erictylerzs-projects.vercel.app";
let chatId = localStorage.getItem("purity_chat_id");

// Check authentication status
fetch(`${SERVER_URL}/api/check_auth`)
    .then(response => response.json())
    .then(data => {
        const authContainer = document.getElementById("auth-container");
        if (data.authenticated) {
            authContainer.innerHTML = `
                <span>Welcome, ${data.user} (${data.provider})!</span>
                <a href="${SERVER_URL}/logout" class="et_pb_button">Logout</a>
            `;
        }
    });

// Start a new chat if no chat_id exists
if (!chatId) {
    fetch(`${SERVER_URL}/api/purity/start_chat`, { method: "POST" })
        .then(response => response.json())
        .then(data => {
            chatId = data.chat_id;
            localStorage.setItem("purity_chat_id", chatId);
            loadHistory();
        });
} else {
    loadHistory();
}

// Load chat history
function loadHistory() {
    fetch(`${SERVER_URL}/api/purity/history?chat_id=${chatId}`)
        .then(response => response.json())
        .then(data => {
            const chatWindow = document.getElementById("chat-window");
            chatWindow.innerHTML = "";
            data.history.forEach(msg => displayMessage(msg.role, msg.content));
        })
        .catch(error => {
            console.error("History fetch error:", error);
            localStorage.removeItem("purity_chat_id");
            window.location.reload();
        });
}

// Send message
document.getElementById("send-button").addEventListener("click", () => {
    const messageInput = document.getElementById("message-input");
    const message = messageInput.value.trim();
    if (!message) return;
    displayMessage("user", message);
    fetch(`${SERVER_URL}/api/purity/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId, query: message })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                displayMessage("assistant", `Error: ${data.error}`);
            } else {
                displayMessage("assistant", data.response);
            }
        })
        .catch(error => {
            console.error("Query fetch error:", error);
            displayMessage("assistant", `Error: ${error.message}`);
        });
    messageInput.value = "";
});

// Attachment button (placeholder)
document.getElementById("attach-button").addEventListener("click", () => {
    document.getElementById("attachment").click();
});

// Display message in chat window
function displayMessage(role, content) {
    const chatWindow = document.getElementById("chat-window");
    const div = document.createElement("div");
    div.className = `message ${role}-message`;
    div.textContent = `${role === "user" ? "You" : "Assistant"}: ${content}`;
    chatWindow.appendChild(div);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}