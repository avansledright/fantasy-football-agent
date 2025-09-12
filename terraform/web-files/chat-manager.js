// ================================
// CHAT-MANAGER.JS - Chat Feature Management
// ================================

const ChatManager = {
    isMinimized: false,
    isTyping: false,
    messages: [],

    initialize() {
        this.createChatInterface();
        this.setupEventListeners();
        console.log('Chat Manager initialized');
    },

    createChatInterface() {
        const chatContainer = document.createElement('div');
        chatContainer.id = 'chatContainer';
        chatContainer.innerHTML = `
            <div class="chat-widget" id="chatWidget">
                <div class="chat-header" id="chatHeader">
                    <div class="chat-title">
                        <i class="fas fa-robot"></i>
                        <span>Fantasy AI Coach</span>
                    </div>
                    <div class="chat-controls">
                        <button class="chat-minimize" id="chatMinimize">
                            <i class="fas fa-minus"></i>
                        </button>
                    </div>
                </div>
                <div class="chat-body" id="chatBody">
                    <div class="chat-messages" id="chatMessages">
                        <div class="message bot-message">
                            <div class="message-content">
                                <i class="fas fa-robot message-avatar"></i>
                                <div class="message-text">
                                    Hello! I'm your Fantasy Football AI Coach. Ask me anything about your lineup, players, or strategy!
                                </div>
                            </div>
                            <div class="message-time">${this.getCurrentTime()}</div>
                        </div>
                    </div>
                    <div class="typing-indicator" id="typingIndicator" style="display: none;">
                        <div class="typing-dots">
                            <span></span>
                            <span></span>
                            <span></span>
                        </div>
                        <span class="typing-text">AI Coach is typing...</span>
                    </div>
                </div>
                <div class="chat-input-container" id="chatInputContainer">
                    <div class="chat-input-wrapper">
                        <textarea class="chat-input" id="chatInput" placeholder="Ask about your lineup, players, matchups..." rows="1"></textarea>
                        <button class="chat-send" id="chatSend">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                    </div>
                </div>
            </div>
            <div class="chat-toggle minimized" id="chatToggle" style="display: none;">
                <i class="fas fa-comments"></i>
                <span class="chat-notification" id="chatNotification" style="display: none;">1</span>
            </div>
        `;

        document.body.appendChild(chatContainer);
    },

    setupEventListeners() {
        const chatMinimize = document.getElementById('chatMinimize');
        const chatToggle = document.getElementById('chatToggle');
        const chatInput = document.getElementById('chatInput');
        const chatSend = document.getElementById('chatSend');

        // Minimize/Maximize functionality
        chatMinimize.addEventListener('click', () => this.toggleMinimize());
        chatToggle.addEventListener('click', () => this.toggleMinimize());

        // Input handling
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Auto-resize textarea
        chatInput.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            chatInput.style.height = Math.min(chatInput.scrollHeight, 100) + 'px';
        });

        // Send button
        chatSend.addEventListener('click', () => this.sendMessage());
    },

    toggleMinimize() {
        const chatWidget = document.getElementById('chatWidget');
        const chatToggle = document.getElementById('chatToggle');
        const chatNotification = document.getElementById('chatNotification');

        this.isMinimized = !this.isMinimized;

        if (this.isMinimized) {
            chatWidget.style.display = 'none';
            chatToggle.style.display = 'flex';
        } else {
            chatWidget.style.display = 'flex';
            chatToggle.style.display = 'none';
            chatNotification.style.display = 'none';
            
            // Focus input when opening
            setTimeout(() => {
                document.getElementById('chatInput').focus();
            }, 100);
        }
    },

    async sendMessage() {
        const chatInput = document.getElementById('chatInput');
        const message = chatInput.value.trim();

        if (!message) return;

        // Add user message to chat
        this.addMessage(message, 'user');
        chatInput.value = '';
        chatInput.style.height = 'auto';

        // Show typing indicator
        this.showTypingIndicator();

        try {
            // Send message to API
            const response = await this.sendChatMessage(message);
            
            // Hide typing indicator
            this.hideTypingIndicator();
            
            // Add bot response
            this.addMessage(response.message || response.response || 'Sorry, I didn\'t understand that.', 'bot');

        } catch (error) {
            console.error('Chat error:', error);
            this.hideTypingIndicator();
            this.addMessage('Sorry, I\'m having trouble connecting right now. Please try again later.', 'bot', true);
        }
    },

    async sendChatMessage(message) {
        const teamId = elements.teamId ? elements.teamId.value.trim() : '';
        const week = elements.weekNumber ? elements.weekNumber.value.trim() : '';

        const requestBody = {
            message: message,
            context: {
                team_id: teamId,
                week: week,
                current_team: currentTeam
            }
        };

        const response = await fetch(`${API_CONFIG.BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response.json();
    },

    addMessage(text, sender, isError = false) {
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        
        messageDiv.className = `message ${sender}-message${isError ? ' error-message' : ''}`;
        messageDiv.innerHTML = `
            <div class="message-content">
                <i class="fas ${sender === 'user' ? 'fa-user' : 'fa-robot'} message-avatar"></i>
                <div class="message-text">${this.formatMessageText(text)}</div>
            </div>
            <div class="message-time">${this.getCurrentTime()}</div>
        `;

        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Store message
        this.messages.push({
            text: text,
            sender: sender,
            timestamp: new Date().toISOString(),
            isError: isError
        });

        // Show notification if minimized
        if (this.isMinimized && sender === 'bot') {
            this.showNotification();
        }
    },

    formatMessageText(text) {
        // Basic formatting for the message text
        return text
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\*([^*]+)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>')
            .replace(/`([^`]+)`/g, '<code>$1</code>');
    },

    showTypingIndicator() {
        const typingIndicator = document.getElementById('typingIndicator');
        const chatMessages = document.getElementById('chatMessages');
        
        this.isTyping = true;
        typingIndicator.style.display = 'flex';
        chatMessages.scrollTop = chatMessages.scrollHeight;
    },

    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typingIndicator');
        this.isTyping = false;
        typingIndicator.style.display = 'none';
    },

    showNotification() {
        const chatNotification = document.getElementById('chatNotification');
        if (this.isMinimized) {
            chatNotification.style.display = 'block';
            chatNotification.textContent = '1'; // Could be made dynamic
        }
    },

    getCurrentTime() {
        return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    },

    // Public method to clear chat history
    clearChat() {
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.innerHTML = `
            <div class="message bot-message">
                <div class="message-content">
                    <i class="fas fa-robot message-avatar"></i>
                    <div class="message-text">
                        Chat cleared! How can I help you with your fantasy team?
                    </div>
                </div>
                <div class="message-time">${this.getCurrentTime()}</div>
            </div>
        `;
        this.messages = [];
    },

    // Public method to send a message programmatically
    sendProgrammaticMessage(message) {
        const chatInput = document.getElementById('chatInput');
        chatInput.value = message;
        this.sendMessage();
    }
};