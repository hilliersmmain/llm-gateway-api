document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const chatContainer = document.getElementById('chat-container');
    const userInput = document.getElementById('userInput');
    const sendBtn = document.getElementById('send-btn');
    const newChatBtn = document.getElementById('newChatBtn');
    const historyList = document.getElementById('historyList');
    const currentChatTitle = document.getElementById('currentChatTitle');
    const themeToggleBtn = document.getElementById('themeToggleBtn');
    const sidebar = document.querySelector('.sidebar');
    const menuToggle = document.getElementById('menuToggle');

    // --- State ---
    let currentChatId = null;
    const STORAGE_KEY = 'llm_gateway_chats';

    // --- Initialization ---
    init();

    function init() {
        loadTheme();
        loadHistory();
        
        // Check if we need to load a specific chat or create new
        // For now, simple logic: create new if none active
        createNewChat(false); 
        
        setupEventListeners();
        setupHistoryDelegation(); // Added delegation setup
        autoResizeTextarea();
        toggleSendButton(); // Initial button state check
    }

    // --- Event Listeners ---
    function setupEventListeners() {
        console.log('Setting up event listeners...');
        
        // Single clean event listener for send button
        sendBtn.addEventListener('click', (e) => {
            console.log('Send button clicked');
            e.preventDefault();
            sendMessage();
        });
        
        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                console.log('Enter pressed in input');
                sendMessage();
            }
        });

        userInput.addEventListener('input', () => {
            autoResizeTextarea();
            toggleSendButton();
        });
        
        newChatBtn.addEventListener('click', () => {
            createNewChat(true);
            if (window.innerWidth <= 768) sidebar.classList.remove('active');
        });
        
        themeToggleBtn.addEventListener('click', toggleTheme);

        if (menuToggle) {
            menuToggle.addEventListener('click', () => {
                sidebar.classList.toggle('active');
            });
        }

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 && 
                sidebar.classList.contains('active') && 
                !sidebar.contains(e.target) && 
                !menuToggle.contains(e.target)) {
                sidebar.classList.remove('active');
            }
        });
    }

    // --- Chat Logic ---

    async function sendMessage() {
        const text = userInput.value.trim();
        console.log('Attempting to send message:', text);
        
        if (!text) {
            console.log('Empty text, aborting send');
            return;
        }

        // UI Updates
        appendMessage('user', text);
        userInput.value = '';
        autoResizeTextarea();
        toggleSendButton();
        
        // Save to History (if first message, creates the chat entry)
        saveToHistory('user', text);

        // API Call
        try {
            showTypingIndicator();
            
            console.log('Sending API request...');
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text }) 
            });

            if (!response.ok) throw new Error('API request failed');

            const data = await response.json();
            console.log('API Response received:', data);
            
            const botMessage = data.content; // Updated from 'response' to 'content' based on ChatResponse schema in main.py

            removeTypingIndicator();
            appendMessage('bot', botMessage);
            saveToHistory('bot', botMessage);

        } catch (error) {
            console.error('Send Message Error:', error);
            removeTypingIndicator();
            appendMessage('bot', 'Error: Could not connect to the server. ' + error.message);
        }
    }

    function appendMessage(role, text) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;
        
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'avatar';
        avatarDiv.innerHTML = role === 'user' ? '<i class="fas fa-user"></i>' : '<i class="fas fa-robot"></i>';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        if (role === 'bot') {
            // Configure marked to be safe
            contentDiv.innerHTML = DOMPurify.sanitize(marked.parse(text));
        } else {
            contentDiv.textContent = text;
        }

        msgDiv.appendChild(avatarDiv);
        msgDiv.appendChild(contentDiv);
        chatContainer.appendChild(msgDiv);
        scrollToBottom();
    }

    function scrollToBottom() {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function toggleSendButton() {
        // Query live DOM element to avoid stale references
        const btn = document.getElementById('send-btn');
        if (btn) btn.disabled = !userInput.value.trim();
    }

    // --- History Management (localStorage) ---

    function getChats() {
        const chats = localStorage.getItem(STORAGE_KEY);
        return chats ? JSON.parse(chats) : {};
    }

    function saveChats(chats) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
        renderHistoryList();
    }

    function createNewChat(clearUI = true) {
        currentChatId = Date.now().toString(); // Temporary ID until first save? Or use this as permanent.
        
        if (clearUI) {
            chatContainer.innerHTML = '';
            // Add welcome message
            const welcomeDiv = document.createElement('div');
            welcomeDiv.className = 'message bot';
            welcomeDiv.innerHTML = `
                <div class="avatar"><i class="fas fa-robot"></i></div>
                <div class="message-content">
                    <p>Hello! I'm your LLM Gateway assistant. How can I help you today?</p>
                </div>`;
            chatContainer.appendChild(welcomeDiv);
            
            currentChatTitle.textContent = 'New Conversation';
            
            // Remove active class from sidebar items
            document.querySelectorAll('.history-item').forEach(el => el.classList.remove('active'));
        }
    }

    function saveToHistory(role, text) {
        const chats = getChats();
        
        if (!chats[currentChatId]) {
            chats[currentChatId] = {
                id: currentChatId,
                title: text.substring(0, 30) + (text.length > 30 ? '...' : ''),
                timestamp: Date.now(),
                messages: []
            };
        }

        chats[currentChatId].messages.push({ role, text });
        chats[currentChatId].timestamp = Date.now(); 
        
        saveChats(chats);
        
        // Update title if it's still Generic
        if (currentChatTitle.textContent === 'New Conversation') {
            currentChatTitle.textContent = chats[currentChatId].title;
        }
    }

    function loadHistory() {
        renderHistoryList();
    }

    function renderHistoryList() {
        const chats = getChats();
        const sortedChats = Object.values(chats).sort((a, b) => b.timestamp - a.timestamp);

        historyList.innerHTML = '';
        
        sortedChats.forEach(chat => {
            const div = document.createElement('div');
            div.className = `history-item ${chat.id === currentChatId ? 'active' : ''}`;
            div.dataset.id = chat.id; // Store ID for delegation
            div.innerHTML = `
                <span><i class="far fa-message" style="margin-right: 8px; opacity: 0.7;"></i>${chat.title}</span>
                <button class="delete-chat-btn" data-id="${chat.id}"><i class="fas fa-trash" style="pointer-events: none;"></i></button>
            `;
            // No individual listeners attached here anymore!
            historyList.appendChild(div);
        });
    }

    // New delegated listener setup (call this in init/setupEventListeners)
    function setupHistoryDelegation() {
        if (!historyList) {
            console.error('historyList not found');
            return;
        }
        historyList.addEventListener('click', (e) => {
            const delBtn = e.target.closest('.delete-chat-btn');
            
            // Case 1: Delete Button Clicked
            if (delBtn) {
                e.preventDefault();
                e.stopPropagation();
                const chatId = delBtn.dataset.id;
                deleteChat(chatId);
                return;
            }

            // Case 2: History Item Clicked (only if not delete)
            const item = e.target.closest('.history-item');
            if (item) {
                const chatId = item.dataset.id;
                loadChatSession(chatId);
                 if (window.innerWidth <= 768) sidebar.classList.remove('active');
            }
        });
    }

    function loadChatSession(id) {
        currentChatId = id;
        const chats = getChats();
        const chat = chats[id];
        
        if (!chat) return;

        currentChatTitle.textContent = chat.title;
        chatContainer.innerHTML = ''; 
        
        chat.messages.forEach(msg => {
            appendMessage(msg.role, msg.text);
        });
        
        renderHistoryList(); // to update 'active' class
        scrollToBottom();
    }

    function deleteChat(id) {
        if (confirm('Delete this conversation?')) {
            const chats = getChats();
            delete chats[id];
            localStorage.setItem(STORAGE_KEY, JSON.stringify(chats)); // Save without render first?
            
            // If we deleted the current chat, reset UI
            if (currentChatId === id) {
                createNewChat(true);
            }
            
            renderHistoryList(); // Render after everything is settled
        }
    }

    // --- Utilities ---

    function autoResizeTextarea() {
        userInput.style.height = 'auto';
        userInput.style.height = userInput.scrollHeight + 'px';
    }

    function showTypingIndicator() {
        const div = document.createElement('div');
        div.id = 'typingIndicator';
        div.className = 'message bot';
        div.innerHTML = `
            <div class="avatar"><i class="fas fa-robot"></i></div>
            <div class="message-content">
                <i class="fas fa-circle-notch fa-spin"></i> Thinking...
            </div>`;
        chatContainer.appendChild(div);
        scrollToBottom();
    }

    function removeTypingIndicator() {
        const el = document.getElementById('typingIndicator');
        if (el) el.remove();
    }

    function toggleTheme() {
        const body = document.body;
        const isDark = body.getAttribute('data-theme') === 'dark';
        
        if (isDark) {
            body.removeAttribute('data-theme');
            localStorage.setItem('theme', 'light');
        } else {
            body.setAttribute('data-theme', 'dark');
            localStorage.setItem('theme', 'dark');
        }
    }

    function loadTheme() {
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark' || (!savedTheme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            document.body.setAttribute('data-theme', 'dark');
        }
    }
});
