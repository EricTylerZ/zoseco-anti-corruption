(function() {
    // Widget configuration
    const CHAT_SERVER = 'https://your-server-url.com';  // Change to your server URL
    
    // Create and inject CSS
    const style = document.createElement('style');
    style.innerHTML = `
        #zoseco-chat-widget {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            font-family: Arial, sans-serif;
        }
        
        #zoseco-chat-button {
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background-color: #4a86e8;
            color: white;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(0,0,0,0.2);
        }
        
        #zoseco-chat-container {
            position: fixed;
            bottom: 90px;
            right: 20px;
            width: 350px;
            height: 450px;
            background-color: white;
            border-radius: 10px;
            overflow: hidden;
            display: none;
            flex-direction: column;
            box-shadow: 0 5px 20px rgba(0,0,0,0.2);
        }
        
        #zoseco-chat-header {
            background-color: #4a86e8;
            color: white;
            padding: 15px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
        }
        
        #zoseco-chat-close {
            cursor: pointer;
        }
        
        #zoseco-chat-messages {
            flex: 1;
            padding: 15px;
            overflow-y: auto;
        }
        
        .zoseco-message {
            margin-bottom: 10px;
            max-width: 80%;
            padding: 10px;
            border-radius: 10px;
        }
        
        .zoseco-visitor-message {
            background-color: #e6f2ff;
            margin-left: auto;
        }
        
        .zoseco-agent-message {
            background-color: #f1f1f1;
            margin-right: auto;
        }
        
        #zoseco-chat-input-container {
            padding: 15px;
            border-top: 1px solid #eee;
            display: flex;
        }
        
        #zoseco-chat-input {
            flex: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            outline: none;
        }
        
        #zoseco-chat-submit {
            margin-left: 10px;
            padding: 10px 15px;
            background-color: #4a86e8;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        
        #zoseco-chat-form {
            display: flex;
            flex-direction: column;
            padding: 15px;
            display: none;
        }
        
        #zoseco-chat-form input {
            margin-bottom: 10px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }
        
        #zoseco-chat-form button {
            padding: 10px;
            background-color: #4a86e8;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
    `;
    document.head.appendChild(style);
    
    // Create chat button and container
    const body = document.body;
    const widgetDiv = document.createElement('div');
    widgetDiv.id = 'zoseco-chat-widget';
    widgetDiv.innerHTML = `
        <div id="zoseco-chat-button">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M20 2H4C2.9 2 2 2.9 2 4V22L6 18H20C21.1 18 22 17.1 22 16V4C22 2.9 21.1 2 20 2Z" fill="white"/>
            </svg>
        </div>
        <div id="zoseco-chat-container">
            <div id="zoseco-chat-header">
                <span>Chat with Us</span>
                <span id="zoseco-chat-close">✕</span>
            </div>
            <div id="zoseco-chat-form">
                <input type="text" id="zoseco-name" placeholder="Your name" required>
                <input type="email" id="zoseco-email" placeholder="Your email (optional)">
                <button id="zoseco-start-chat">Start Chat</button>
            </div>
            <div id="zoseco-chat-messages"></div>
            <div id="zoseco-chat-input-container">
                <input type="text" id="zoseco-chat-input" placeholder="Type your message here...">
                <button id="zoseco-chat-submit">Send</button>
            </div>
        </div>
    `;
    body.appendChild(widgetDiv);
    
    // Load socket.io client from CDN
    const script = document.createElement('script');
    script.src = 'https://cdn.socket.io/4.5.4/socket.io.min.js';
    script.onload = initChat;
    document.head.appendChild(script);
    
    function initChat() {
        const chatButton = document.getElementById('zoseco-chat-button');
        const chatContainer = document.getElementById('zoseco-chat-container');
        const chatClose = document.getElementById('zoseco-chat-close');
        const chatInput = document.getElementById('zoseco-chat-input');
        const chatSubmit = document.getElementById('zoseco-chat-submit');
        const chatMessages = document.getElementById('zoseco-chat-messages');
        const chatForm = document.getElementById('zoseco-chat-form');
        const nameInput = document.getElementById('zoseco-name');
        const emailInput = document.getElementById('zoseco-email');
        const startChatBtn = document.getElementById('zoseco-start-chat');
        
        let socket = null;
        let chatId = localStorage.getItem('zoseco-chat-id');
        
        // Toggle chat window
        chatButton.addEventListener('click', () => {
            if (chatContainer.style.display === 'none' || chatContainer.style.display === '') {
                chatContainer.style.display = 'flex';
                
                if (chatId) {
                    chatForm.style.display = 'none';
                    chatMessages.style.display = 'block';
                    chatInput.parentElement.style.display = 'flex';
                    
                    if (!socket) {
                        connectSocket();
                    }
                } else {
                    chatForm.style.display = 'flex';
                    chatMessages.style.display = 'none';
                    chatInput.parentElement.style.display = 'none';
                }
            } else {
                chatContainer.style.display = 'none';
            }
        });
        
        chatClose.addEventListener('click', () => {
            chatContainer.style.display = 'none';
        });
        
        startChatBtn.addEventListener('click', () => {
            const name = nameInput.value.trim();
            const email = emailInput.value.trim();
            
            if (!name) {
                alert('Please enter your name');
                return;
            }
            
            fetch(`${CHAT_SERVER}/api/start_chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name, email })
            })
            .then(response => response.json())
            .then(data => {
                chatId = data.chat_id;
                localStorage.setItem('zoseco-chat-id', chatId);
                
                chatForm.style.display = 'none';
                chatMessages.style.display = 'block';
                chatInput.parentElement.style.display = 'flex';
                
                connectSocket();
                
                // Add welcome message
                addMessage('Welcome to Zoseco support! How can we help you today?', 'agent');
            })
            .catch(error => {
                console.error('Error starting chat:', error);
                alert('Failed to start chat. Please try again.');
            });
        });
        
        // Send message
        function sendMessage() {
            const message = chatInput.value.trim();
            if (!message) return;
            
            if (socket && chatId) {
                socket.emit('message', {
                    chat_id: chatId,
                    message: message,
                    sender: 'visitor'
                });
                
                addMessage(message, 'visitor');
                chatInput.value = '';
            }
        }
        
        chatSubmit.addEventListener('click', sendMessage);
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
        
        // Connect to socket
        function connectSocket() {
            socket = io(CHAT_SERVER);
            
            socket.on('connect', () => {
                console.log('Connected to chat server');
                socket.emit('join', { chat_id: chatId, user_type: 'visitor' });
            });
            
            socket.on('message', (data) => {
                if (data.sender === 'agent') {
                    addMessage(data.text, 'agent');
                }
            });
            
            socket.on('chat_history', (data) => {
                chatMessages.innerHTML = '';
                data.messages.forEach(msg => {
                    addMessage(msg.text, msg.sender);
                });
            });
            
            socket.on('disconnect', () => {
                console.log('Disconnected from chat server');
            });
        }
        
        // Add message to chat
        function addMessage(text, sender) {
            const messageDiv = document.createElement('div');
            messageDiv.className = `zoseco-message zoseco-${sender}-message`;
            messageDiv.textContent = text;
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        
        // If we have a chat ID, connect immediately
        if (chatId) {
            connectSocket();
        }
    }
})();