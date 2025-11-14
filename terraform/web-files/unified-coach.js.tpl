// ================================
// UNIFIED COACH - JavaScript for index2.html
// ================================

// Configuration - Dynamically templated by Terraform
const API_CONFIG = {
    BASE_URL: "${api_endpoint}",
    UNIFIED_COACH_ENDPOINT: "/unified-coach"
};

// Global state
let messages = [];
let isTyping = false;
let hasStarted = false;

// ================================
// INITIALIZATION
// ================================

// Make initializeApp globally accessible for the auth system
window.initializeApp = function initializeApp() {
    console.log('Initializing Unified Coach...');

    setTimeout(() => {
        setupEventListeners();
        console.log("API Configuration:", API_CONFIG);
    }, 100);
};

function setupEventListeners() {
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const startCoachingBtn = document.getElementById('startCoachingBtn');
    const resetChatBtn = document.getElementById('resetChatBtn');

    // Send message on button click
    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    // Send message on Enter (but not Shift+Enter for new line)
    if (messageInput) {
        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Auto-resize textarea
        messageInput.addEventListener('input', () => {
            messageInput.style.height = 'auto';
            messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
        });
    }

    // Start coaching session
    if (startCoachingBtn) {
        startCoachingBtn.addEventListener('click', startCoaching);
    }

    // Reset chat
    if (resetChatBtn) {
        resetChatBtn.addEventListener('click', resetChat);
    }

    console.log('Event listeners set up');
}

// ================================
// CORE FUNCTIONS
// ================================

function startCoaching() {
    const teamId = document.getElementById('teamId').value.trim();
    const week = document.getElementById('weekNumber').value.trim();

    if (!teamId || !week) {
        showToast('Please enter Team ID and Week number', 'error');
        return;
    }

    // Clear welcome message if present
    const messagesContainer = document.getElementById('messagesContainer');
    if (messagesContainer && messagesContainer.querySelector('.welcome-message')) {
        messagesContainer.innerHTML = '';
    }

    // Send initial message to trigger lineup generation
    const initialMessage = "Generate my optimal lineup for this week";
    sendMessageToAPI(initialMessage);
    hasStarted = true;
}

async function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();

    if (!message) return;

    if (!hasStarted) {
        showToast('Please start a coaching session first', 'warning');
        return;
    }

    // Add user message to UI
    addMessage(message, 'user');

    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Send to API
    await sendMessageToAPI(message);
}

async function sendMessageToAPI(message) {
    const teamId = document.getElementById('teamId').value.trim();
    const week = document.getElementById('weekNumber').value.trim();
    const sendBtn = document.getElementById('sendBtn');

    if (!teamId || !week) {
        showToast('Please enter Team ID and Week number', 'error');
        return;
    }

    // Show typing indicator
    showTypingIndicator();

    // Disable send button
    if (sendBtn) {
        sendBtn.disabled = true;
    }

    try {
        const requestBody = {
            message: message,
            context: {
                team_id: teamId,
                week: parseInt(week)
            }
        };

        console.log('Sending request to:', `${API_CONFIG.BASE_URL}${API_CONFIG.UNIFIED_COACH_ENDPOINT}`);
        console.log('Request body:', requestBody);

        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.UNIFIED_COACH_ENDPOINT}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        console.log('Response:', data);

        // Hide typing indicator
        hideTypingIndicator();

        // Add bot response
        const botMessage = data.response || data.message || 'Sorry, I didn\'t get a response.';
        addMessage(botMessage, 'bot');

    } catch (error) {
        console.error('Error sending message:', error);
        hideTypingIndicator();
        addMessage('Sorry, I\'m having trouble connecting right now. Please try again later.', 'bot', true);
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        // Re-enable send button
        if (sendBtn) {
            sendBtn.disabled = false;
        }
    }
}

function addMessage(text, sender, isError = false) {
    const messagesContainer = document.getElementById('messagesContainer');

    // Remove welcome message if present
    const welcomeMessage = messagesContainer.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `unified-message ${sender}${isError ? ' error' : ''}`;

    const messageBubble = document.createElement('div');
    messageBubble.className = 'message-bubble';
    messageBubble.innerHTML = formatMessageText(text);

    const messageTime = document.createElement('div');
    messageTime.className = 'message-time';
    messageTime.textContent = getCurrentTime();

    messageDiv.appendChild(messageBubble);
    messageDiv.appendChild(messageTime);

    messagesContainer.appendChild(messageDiv);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Store message
    messages.push({
        text: text,
        sender: sender,
        timestamp: new Date().toISOString(),
        isError: isError
    });
}

function showTypingIndicator() {
    const messagesContainer = document.getElementById('messagesContainer');

    const typingDiv = document.createElement('div');
    typingDiv.className = 'unified-message bot';
    typingDiv.id = 'typingIndicator';

    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator';
    typingIndicator.innerHTML = `
        <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <span style="margin-left: 8px; color: #666; font-size: 13px;">Coach is thinking...</span>
    `;

    typingDiv.appendChild(typingIndicator);
    messagesContainer.appendChild(typingDiv);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    isTyping = true;
}

function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
    isTyping = false;
}

function formatMessageText(text) {
    // Format markdown-style text
    return text
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/^### (.+)$/gm, '<h3 style="margin: 10px 0; font-size: 16px;">$1</h3>')
        .replace(/^## (.+)$/gm, '<h2 style="margin: 12px 0; font-size: 18px;">$1</h2>')
        .replace(/^# (.+)$/gm, '<h1 style="margin: 15px 0; font-size: 20px;">$1</h1>');
}

function getCurrentTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function resetChat() {
    const messagesContainer = document.getElementById('messagesContainer');
    messagesContainer.innerHTML = `
        <div class="welcome-message">
            <i class="fas fa-helmet-safety"></i>
            <h2>Welcome to Your Unified Fantasy Coach!</h2>
            <p>I'll automatically generate your optimal lineup and then help you with any questions.</p>
            <div class="quick-actions">
                <button class="quick-action-btn" onclick="startCoaching()">Generate My Lineup</button>
                <button class="quick-action-btn" onclick="sendQuickMessage('Tell me about my bye week players')">Bye Week Analysis</button>
                <button class="quick-action-btn" onclick="sendQuickMessage('What waiver wire pickups should I target?')">Waiver Wire Targets</button>
                <button class="quick-action-btn" onclick="sendQuickMessage('Should I start or sit my FLEX players?')">Start/Sit Advice</button>
            </div>
        </div>
    `;
    messages = [];
    hasStarted = false;
    showToast('Chat reset successfully', 'success');
}

function showToast(message, type = 'info') {
    // Simple toast notification
    const toast = document.createElement('div');
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: ${type === 'error' ? '#dc3545' : type === 'warning' ? '#ffc107' : type === 'success' ? '#28a745' : '#007bff'};
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
    `;
    toast.textContent = message;

    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ================================
// GLOBAL HELPER FUNCTIONS
// ================================

window.startCoaching = startCoaching;

window.sendQuickMessage = function(message) {
    const teamId = document.getElementById('teamId').value.trim();
    const week = document.getElementById('weekNumber').value.trim();

    if (!teamId || !week) {
        showToast('Please enter Team ID and Week number first', 'warning');
        return;
    }

    if (!hasStarted) {
        // Start with the quick message
        const messagesContainer = document.getElementById('messagesContainer');
        if (messagesContainer && messagesContainer.querySelector('.welcome-message')) {
            messagesContainer.innerHTML = '';
        }
        hasStarted = true;
    }

    sendMessageToAPI(message);
};

// Add CSS for animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

console.log('Unified Coach loaded successfully');
