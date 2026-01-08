// =====================================================
// FILE: app/static/js/screens/experts/ask_expert_unified.js
// Ask an Expert - Unified Chat Interface
// =====================================================

(function() {
    'use strict';
    
    let currentSessionId = null;
    let currentExpertId = null;
    let messagePollingInterval = null;
    let allExperts = [];
    let currentCategory = 'all';

// =====================================================
// INITIALIZATION
// =====================================================
document.addEventListener('DOMContentLoaded', function() {
    loadChatHistory();
    loadExperts();
    
    // Setup modal event listeners
    setupModalListeners();
    
    // Auto-resize textarea
    const messageInput = document.getElementById('messageInput');
    if (messageInput) {
        messageInput.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
    }
});

// =====================================================
// SETUP MODAL LISTENERS
// =====================================================
function setupModalListeners() {
    const modal = document.getElementById('expertModal');
    const closeBtn = document.getElementById('closeModalBtn');
    
    // Close button
    if (closeBtn) {
        closeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            closeExpertSelector();
        });
    }
    
    // Click outside to close
    if (modal) {
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                closeExpertSelector();
            }
        });
    }
    
    // Category buttons
    const categoryBtns = document.querySelectorAll('.category-btn');
    categoryBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            const category = this.dataset.category;
            filterExperts(category);
        });
    });
}

// =====================================================
// LOAD CHAT HISTORY
// =====================================================
async function loadChatHistory() {
    console.log('🔄 Loading chat history...');
    try {
        const response = await fetch('/api/v1/experts/my-consultations');
        const data = await response.json();
        
        console.log('📦 API Response:', data);
        
        const chatList = document.getElementById('chatList');
        
        // ✅ FIXED: Handle any response format
        let sessions = [];
        if (Array.isArray(data)) {
            sessions = data;
        } else if (data.sessions) {
            sessions = data.sessions;
        } else if (data.consultations) {
            sessions = data.consultations;
        } else if (data.data) {
            sessions = data.data;
        }
        
        console.log(' Found', sessions.length, 'consultations');
        
        if (!sessions || sessions.length === 0) {
            chatList.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-inbox"></i>
                    <p>No consultations yet</p>
                    <p style="font-size: 12px;">Start a new consultation to get help from experts</p>
                </div>
            `;
            return;
        }
        
        chatList.innerHTML = '';
        
        sessions.forEach(session => {
            const chatItem = createChatItem(session);
            chatList.appendChild(chatItem);
        });
        
    } catch (error) {
        console.error('❌ Error loading chat history:', error);
        document.getElementById('chatList').innerHTML = `
            <div class="empty-state">
                <i class="ti ti-alert-circle"></i>
                <p>Failed to load consultations</p>
                <p style="font-size: 12px;">${error.message}</p>
            </div>
        `;
    }
}

// =====================================================
// CREATE CHAT ITEM
// =====================================================
function createChatItem(session) {
    const div = document.createElement('div');
    div.className = 'chat-item';
    div.dataset.sessionId = session.session_id;
    div.onclick = () => openChat(session.session_id);
    
    const expertName = session.expert_name || 'Unassigned Expert';
    const subject = session.subject || 'No subject';
    const lastMessage = session.last_message || 'No messages yet';
    const time = formatTime(session.updated_at || session.created_at);
    const unreadCount = session.unread_count || 0;
    
    div.innerHTML = `
        <div class="chat-item-header">
            <span class="chat-expert-name">${expertName}</span>
            <span class="chat-time">${time}</span>
        </div>
        <div class="chat-subject">${subject}</div>
        <div class="chat-preview">${lastMessage}</div>
        ${unreadCount > 0 ? `<span class="unread-badge">${unreadCount}</span>` : ''}
    `;
    
    return div;
}

// =====================================================
// OPEN CHAT
// =====================================================
async function openChat(sessionId) {
    currentSessionId = sessionId;
    
    // Update active state
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-session-id="${sessionId}"]`)?.classList.add('active');
    
    // Show chat header and input
    document.getElementById('chatHeader').style.display = 'flex';
    document.getElementById('chatInputArea').style.display = 'block';
    
    try {
        // Load session details
        const response = await fetch(`/api/v1/experts/sessions/${sessionId}`);
        const data = await response.json();
        
        // Update header
        updateChatHeader(data);
        
        // Load messages
        await loadMessages(sessionId);
        
        // Start polling for new messages
        startMessagePolling();
        
    } catch (error) {
        console.error('Error opening chat:', error);
        showError('Failed to load chat');
    }
}

// =====================================================
// UPDATE CHAT HEADER
// =====================================================
function updateChatHeader(sessionData) {
    const expertName = sessionData.expert_name || 'Expert';
    const expertSpecialization = sessionData.expert_specialization || 'General';
    const isAvailable = sessionData.expert_available !== false;
    
    document.getElementById('expertName').textContent = expertName;
    document.getElementById('expertSpecialization').textContent = expertSpecialization;
    document.getElementById('expertStatus').textContent = isAvailable ? 'Available' : 'Offline';
    
    const statusDot = document.getElementById('statusDot');
    statusDot.className = isAvailable ? 'status-dot' : 'status-dot offline';
    
    // Set avatar
    const avatar = document.getElementById('expertAvatar');
    if (sessionData.expert_picture) {
        avatar.innerHTML = `<img src="${sessionData.expert_picture}" alt="${expertName}">`;
    } else {
        const initials = expertName.split(' ').map(n => n[0]).join('').toUpperCase();
        avatar.innerHTML = initials;
    }
}

// =====================================================
// LOAD MESSAGES
// =====================================================
async function loadMessages(sessionId) {
    try {
        const response = await fetch(`/api/v1/experts/sessions/${sessionId}/messages`);
        const data = await response.json();
        
        const messagesContainer = document.getElementById('chatMessages');
        messagesContainer.innerHTML = '';
        
        if (!data.messages || data.messages.length === 0) {
            messagesContainer.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-message"></i>
                    <p>No messages yet</p>
                    <p style="font-size: 12px;">Start the conversation by sending a message</p>
                </div>
            `;
            return;
        }
        
        data.messages.forEach(message => {
            const messageElement = createMessageElement(message);
            messagesContainer.appendChild(messageElement);
        });
        
        // Scroll to bottom
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
    } catch (error) {
        console.error('Error loading messages:', error);
    }
}

// =====================================================
// CREATE MESSAGE ELEMENT
// =====================================================
function createMessageElement(message) {
    const div = document.createElement('div');
    const isCurrentUser = message.sender_type === 'user';
    div.className = isCurrentUser ? 'message sent' : 'message';
    
    const senderName = message.sender_name || 'User';
    const initials = senderName.split(' ').map(n => n[0]).join('').toUpperCase();
    const time = formatTime(message.created_at);
    
    div.innerHTML = `
        <div class="message-avatar">${initials}</div>
        <div class="message-content">
            <div class="message-header">
                <span class="message-sender">${senderName}</span>
                <span class="message-time">${time}</span>
            </div>
            <div class="message-bubble">${escapeHtml(message.message_content)}</div>
        </div>
    `;
    
    return div;
}

// =====================================================
// SEND MESSAGE
// =====================================================
async function sendMessage() {
    if (!currentSessionId) {
        showError('No active session');
        return;
    }
    
    const input = document.getElementById('messageInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    try {
        const response = await fetch(`/api/v1/experts/sessions/${currentSessionId}/messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message_content: message,
                message_type: 'text'
            })
        });
        
        if (!response.ok) throw new Error('Failed to send message');
        
        // Clear input
        input.value = '';
        input.style.height = 'auto';
        
        // Reload messages
        await loadMessages(currentSessionId);
        
    } catch (error) {
        console.error('Error sending message:', error);
        showError('Failed to send message');
    }
}

// =====================================================
// HANDLE ENTER KEY
// =====================================================
function handleEnterKey(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// =====================================================
// MESSAGE POLLING
// =====================================================
function startMessagePolling() {
    stopMessagePolling();
    
    messagePollingInterval = setInterval(async () => {
        if (currentSessionId) {
            await loadMessages(currentSessionId);
        }
    }, 5000); // Poll every 5 seconds
}

function stopMessagePolling() {
    if (messagePollingInterval) {
        clearInterval(messagePollingInterval);
        messagePollingInterval = null;
    }
}

// =====================================================
// EXPERT SELECTION
// =====================================================
function openExpertSelector() {
    const modal = document.getElementById('expertModal');
    if (modal) {
        modal.classList.add('show');
        document.body.style.overflow = 'hidden';
        console.log('Modal opened');
    }
}

function closeExpertSelector() {
    const modal = document.getElementById('expertModal');
    if (modal) {
        modal.classList.remove('show');
        document.body.style.overflow = '';
        console.log('Modal closed');
    }
}

function handleModalClick(event) {
    // Close modal if clicking on the backdrop
    if (event.target.id === 'expertModal') {
        closeExpertSelector();
    }
}

// =====================================================
// LOAD EXPERTS
// =====================================================
async function loadExperts() {
    console.log('🔍 Loading experts directory...');
    
    try {
        const response = await fetch('/api/v1/experts/directory');
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        allExperts = data.experts || [];
        console.log(` Loaded ${allExperts.length} experts`);
        
        renderExperts(allExperts);
        
    } catch (error) {
        console.error('❌ Error loading experts:', error);
        document.getElementById('expertsGrid').innerHTML = `
            <div class="empty-state">
                <i class="ti ti-alert-circle"></i>
                <p>Failed to load experts</p>
                <p style="font-size: 12px; color: #868e96;">${error.message}</p>
            </div>
        `;
    }
}

// =====================================================
// FILTER EXPERTS
// =====================================================
function filterExperts(category) {
    console.log('Filtering by category:', category);
    currentCategory = category;
    
    // Update active button
    document.querySelectorAll('.category-btn').forEach(btn => {
        btn.classList.remove('active');
        if (btn.dataset.category === category) {
            btn.classList.add('active');
        }
    });
    
    // Filter and render
    let filtered = allExperts;
    if (category !== 'all') {
        filtered = allExperts.filter(expert => {
            const areas = expert.expertise_areas || [];
            return areas.some(area => area.toLowerCase().includes(category.toLowerCase()));
        });
    }
    
    console.log(`Filtered ${filtered.length} experts for category: ${category}`);
    renderExperts(filtered);
}

// =====================================================
// RENDER EXPERTS
// =====================================================
function renderExperts(experts) {
    const grid = document.getElementById('expertsGrid');
    
    console.log('📋 Rendering', experts.length, 'experts');
    
    if (experts.length === 0) {
        grid.innerHTML = `
            <div class="empty-state">
                <i class="ti ti-users-off"></i>
                <p>No experts found in this category</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = '';
    
    experts.forEach((expert, index) => {
        console.log(`  ${index + 1}. ${expert.first_name} ${expert.last_name} (ID: ${expert.expert_id})`);
        const card = createExpertCard(expert);
        grid.appendChild(card);
    });
    
    console.log(' Expert cards rendered successfully');
}

// =====================================================
// CREATE EXPERT CARD
// =====================================================
function createExpertCard(expert) {
    const div = document.createElement('div');
    div.className = 'expert-card';
    div.style.cursor = 'pointer';
    
    const fullName = `${expert.first_name} ${expert.last_name}`;
    const initials = fullName.split(' ').map(n => n[0]).join('').toUpperCase();
    const specialization = expert.specialization || 'General Expert';
    const consultations = expert.total_consultations || 0;
    const rating = expert.average_rating || 0;
    
    div.innerHTML = `
        <div class="expert-card-header">
            <div class="expert-card-avatar">${initials}</div>
            <div class="expert-card-info">
                <h4>${fullName}</h4>
                <p>${expert.job_title || 'Expert'}</p>
            </div>
        </div>
        <div class="expert-card-specialization">${specialization}</div>
        <div class="expert-card-stats">
            <span class="expert-card-stat">
                <i class="ti ti-star-filled" style="color: #ffc107;"></i>
                ${rating.toFixed(1)}
            </span>
            <span class="expert-card-stat">
                <i class="ti ti-message-circle"></i>
                ${consultations} consultations
            </span>
        </div>
    `;
    
    // Simple click handler
    div.onclick = function(e) {
        e.preventDefault();
        e.stopPropagation();
        console.log(' Expert card clicked! ID:', expert.expert_id, 'Name:', fullName);
        startConsultation(expert.expert_id);
    };
    
    return div;
}

// =====================================================
// START CONSULTATION
// =====================================================
async function startConsultation(expertId) {
    console.log('📞 Starting consultation with expert ID:', expertId);
    
    try {
        // Prompt for subject and question
        const subject = prompt('Enter consultation subject:', 'Expert Consultation Request');
        if (!subject) {
            console.log('❌ Cancelled - no subject');
            return;
        }
        
        const question = prompt('Briefly describe your question:', 'I need assistance with a matter.');
        if (!question) {
            console.log('❌ Cancelled - no question');
            return;
        }
        
        console.log('📤 Sending consultation request...');
        console.log('Expert ID:', expertId);
        console.log('Subject:', subject);
        console.log('Question:', question);
        
        const requestData = {
            expert_id: expertId.toString(),
            session_type: 'chat',
            subject: subject,
            question: question
        };
        
        console.log('Request data:', requestData);
        
        const response = await fetch('/api/v1/experts/sessions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        console.log('📥 Response status:', response.status);
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ Error response:', errorText);
            try {
                const errorData = JSON.parse(errorText);
                throw new Error(errorData.detail || 'Failed to create consultation');
            } catch {
                throw new Error('Failed to create consultation: ' + response.status);
            }
        }
        
        const data = await response.json();
        console.log(' Consultation created:', data);
        
        // Close modal
        closeExpertSelector();
        
        // Reload chat history
        console.log('🔄 Reloading chat history...');
        await loadChatHistory();
        
        // Open the new chat
        console.log(' Opening new chat...');
        await openChat(data.session_id);
        
        showSuccess('Consultation created successfully!');
        
    } catch (error) {
        console.error('❌ Error starting consultation:', error);
        showError('Failed to start consultation: ' + error.message);
    }
}

// =====================================================
// SEARCH CHATS
// =====================================================
function searchChats() {
    const searchTerm = document.getElementById('chatSearchInput').value.toLowerCase();
    const chatItems = document.querySelectorAll('.chat-item');
    
    chatItems.forEach(item => {
        const expertName = item.querySelector('.chat-expert-name').textContent.toLowerCase();
        const subject = item.querySelector('.chat-subject').textContent.toLowerCase();
        const preview = item.querySelector('.chat-preview').textContent.toLowerCase();
        
        if (expertName.includes(searchTerm) || subject.includes(searchTerm) || preview.includes(searchTerm)) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

// =====================================================
// VIEW SESSION DETAILS
// =====================================================
function viewSessionDetails() {
    if (!currentSessionId) return;
    
    // Show details in alert for now (can be enhanced with a modal later)
    showInfo('Session details feature coming soon!');
    
    // Alternative: Open existing consultation details page if it exists
    // window.location.href = `/consultation-details?session=${currentSessionId}`;
}

// =====================================================
// END SESSION
// =====================================================
async function endSession() {
    if (!currentSessionId) return;
    
    if (!confirm('Are you sure you want to end this consultation session?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/v1/experts/sessions/${currentSessionId}/end`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) throw new Error('Failed to end session');
        
        showSuccess('Session ended successfully');
        
        // Reload chat history
        await loadChatHistory();
        
        // Clear current session
        currentSessionId = null;
        document.getElementById('chatHeader').style.display = 'none';
        document.getElementById('chatInputArea').style.display = 'none';
        document.getElementById('chatMessages').innerHTML = `
            <div class="empty-state">
                <i class="ti ti-message-circle"></i>
                <h4>No Consultation Selected</h4>
                <p>Select a consultation from the list or start a new one</p>
            </div>
        `;
        
    } catch (error) {
        console.error('Error ending session:', error);
        showError('Failed to end session');
    }
}

// =====================================================
// UTILITY FUNCTIONS
// =====================================================
function formatTime(dateString) {
    if (!dateString) return '';
    
    const date = new Date(dateString);
    const now = new Date();
    const diff = now - date;
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    
    return date.toLocaleDateString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showLoading(message = 'Loading...') {
    // Simple loading implementation
    console.log('Loading:', message);
}

function hideLoading() {
    console.log('Loading complete');
}

function showError(message) {
    alert('❌ ' + message);
}

function showSuccess(message) {
    alert(' ' + message);
}

function showInfo(message) {
    alert('ℹ️ ' + message);
}

// =====================================================
// CLEANUP
// =====================================================
window.addEventListener('beforeunload', function() {
    stopMessagePolling();
});

// Expose functions globally for HTML onclick handlers
window.openExpertSelector = openExpertSelector;
window.closeExpertSelector = closeExpertSelector;
window.handleModalClick = handleModalClick;
window.filterExperts = filterExperts;
window.startConsultation = startConsultation;
window.searchChats = searchChats;
window.openChat = openChat;
window.sendMessage = sendMessage;
window.handleEnterKey = handleEnterKey;
window.viewSessionDetails = viewSessionDetails;
window.endSession = endSession;

})(); // End of IIFE