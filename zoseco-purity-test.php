<?php
/*
Plugin Name: Zoseco Purity Test
Description: Adds a Purity Test shortcode for Zoseco.com, integrating with Flask API for chat and OAuth.
Version: 1.0
Author: Zoseco Incorporated
*/

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

// Register shortcode
function zoseco_purity_test_shortcode() {
    ob_start();
    ?>
    <style>
        #auth-container { text-align: right; margin-bottom: 20px; }
        #chat-container { text-align: center; }
        #chat-container .subheader { text-align: left; max-width: 600px; margin: 0 auto; }
        #chat-window { max-height: 400px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; margin: 20px auto; background-color: #f9f9f9; max-width: 600px; border-radius: 5px; }
        .chat-input { display: flex; align-items: center; max-width: 600px; margin: 0 auto; }
        .message { margin-bottom: 10px; }
        .user-message { font-weight: bold; color: #00918B; }
        .assistant-message { color: #333; }
    </style>
    <div id="auth-container" class="et_pb_module et_pb_text">
        <div class="auth-buttons">
            <a href="https://anti-corruption-bot-git-purity-test-erictylerzs-projects.vercel.app/login/github" class="et_pb_button">Sign in with GitHub</a>
            <a href="https://anti-corruption-bot-git-purity-test-erictylerzs-projects.vercel.app/login/twitter" class="et_pb_button">Sign in with X.com</a>
            <a href="https://anti-corruption-bot-git-purity-test-erictylerzs-projects.vercel.app/login/facebook" class="et_pb_button">Sign in with Facebook</a>
        </div>
    </div>
    <div id="chat-container" class="et_pb_module et_pb_text">
        <h1>Welcome to Zoseco</h1>
        <h2>How can we help you today?</h2>
        <p class="subheader">
            If you are sharing tips but not logged in, your tips are initially considered far less trustworthy. 
            Logged in Users will be able to see some other tips provided by others and help verify trustworthiness. 
            The more trustworthy you prove to be, the more you will have access to. 
            By using this tool you agree to our <a href="/terms">Terms here</a>. Please review before sending anything.
        </p>
        <div id="chat-window"></div>
        <div class="chat-input">
            <input type="file" id="attachment" style="display: none;" />
            <button id="attach-button" class="et_pb_button">📎</button>
            <textarea id="message-input" rows="4" placeholder="What do you think is happening in Valparaiso? Or is it always sunny here?" class="et_pb_text"></textarea>
            <button id="send-button" class="et_pb_button">Send</button>
        </div>
    </div>
    <script>
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
    </script>
    <?php
    return ob_get_clean();
}
add_shortcode('zoseco_purity_test', 'zoseco_purity_test_shortcode');

// Enqueue Divi styles
function zoseco_purity_test_enqueue_styles() {
    if (is_page('purity-test')) {
        wp_enqueue_style('divi-style', get_template_directory_uri() . '/style.css');
    }
}
add_action('wp_enqueue_scripts', 'zoseco_purity_test_enqueue_styles');
?>