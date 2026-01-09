// =====================================================
// FILE: app/static/js/screens/experts/ask_expert_unified.js
// Ask an Expert - Unified Chat Interface with Consultation Modal
// =====================================================

(function() {
    'use strict';
    
    let currentSessionId = null;
    let currentExpertId = null;
    let messagePollingInterval = null;
    let allExperts = [];
    let currentCategory = 'all';
    let selectedExpertForConsultation = null; // Store selected expert

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
        const expertModal = document.getElementById('expertModal');
        const closeBtn = document.getElementById('closeModalBtn');
        
        // Close button for expert selection modal
        if (closeBtn) {
            closeBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                closeExpertSelector();
            });
        }
        
        // Click outside to close expert selection modal
        if (expertModal) {
            expertModal.addEventListener('click', function(e) {
                if (e.target === expertModal) {
                    closeExpertSelector();
                }
            });
        }
        
        // Click outside to close consultation modal
        const consultationModal = document.getElementById('consultationModal');
        if (consultationModal) {
            consultationModal.addEventListener('click', function(e) {
                if (e.target === consultationModal) {
                    closeConsultationModal();
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
            
            // Handle any response format
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
            
            console.log('✅ Found', sessions.length, 'consultations');
            
            if (sessions.length === 0) {
                chatList.innerHTML = `
                    <div class="empty-state">
                        <i class="ti ti-inbox"></i>
                        <p>No consultations yet</p>
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
    
    // ✅ FIXED: Simple click handler that passes sessionId directly
    div.onclick = function() {
        openChat(session.session_id);
    };
    
    const expertName = session.expert_name || 'Unknown Expert';
    const subject = session.subject || 'No subject';
    const lastMessage = session.last_message || 'No messages yet';
    const time = formatTime(session.updated_at || session.created_at);
    const unreadCount = session.unread_count || 0;
    
    div.innerHTML = `
        <div class="chat-item-header">
            <span class="chat-expert-name">${escapeHtml(expertName)}</span>
        </div>
        <div class="chat-subject">${escapeHtml(subject)}</div>
        <div class="chat-preview">${escapeHtml(lastMessage)}</div>
        ${unreadCount > 0 ? `<span class="unread-badge">${unreadCount}</span>` : ''}
    `;
    
    return div;
}
    // =====================================================
    // OPEN CHAT
    // =====================================================


function formatTime(dateString) {
    if (!dateString) return '';
    
    try {
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
    } catch (error) {
        console.error('Error formatting time:', error);
        return '';
    }
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}



// =====================================================
// UPDATE CHAT HEADER
// =====================================================
function updateChatHeader(sessionData) {
    const expertName = sessionData.expert_name || 'Expert';
    const expertSpecialization = sessionData.expert_specialization || 'General';
    const isAvailable = sessionData.expert_available !== false;
    
    const expertNameEl = document.getElementById('expertName');
    const expertSpecEl = document.getElementById('expertSpecialization');
    const expertStatusEl = document.getElementById('expertStatus');
    const statusDot = document.getElementById('statusDot');
    
    if (expertNameEl) expertNameEl.textContent = expertName;
    if (expertSpecEl) expertSpecEl.textContent = expertSpecialization;
    if (expertStatusEl) expertStatusEl.textContent = isAvailable ? 'Available' : 'Offline';
    
    if (statusDot) {
        statusDot.className = isAvailable ? 'status-dot' : 'status-dot offline';
    }
    
    // Set avatar
    const avatar = document.getElementById('expertAvatar');
    if (avatar) {
        if (sessionData.expert_picture) {
            avatar.innerHTML = `<img src="${sessionData.expert_picture}" alt="${expertName}">`;
        } else {
            const initials = expertName.split(' ').map(n => n[0]).join('').toUpperCase();
            avatar.innerHTML = initials;
        }
    }
}


async function openChat(sessionIdOrEvent) {
    // ✅ Handle both direct sessionId and event object
    let sessionId;
    
    if (typeof sessionIdOrEvent === 'string') {
        // Called directly with sessionId
        sessionId = sessionIdOrEvent;
    } else if (sessionIdOrEvent && sessionIdOrEvent.currentTarget) {
        // Called as event handler
        sessionId = sessionIdOrEvent.currentTarget.dataset.sessionId;
    } else if (sessionIdOrEvent && sessionIdOrEvent.target) {
        // Fallback to event target
        sessionId = sessionIdOrEvent.target.closest('.chat-item')?.dataset.sessionId;
    } else {
        console.error('❌ Invalid sessionId or event:', sessionIdOrEvent);
        return;
    }
    
    if (!sessionId) {
        console.error('❌ No sessionId found');
        return;
    }
    
    currentSessionId = sessionId;
    
    // Update active state
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
    });
    const activeItem = document.querySelector(`[data-session-id="${sessionId}"]`);
    if (activeItem) {
        activeItem.classList.add('active');
    }
    
    // Show chat header and input
    const chatHeader = document.getElementById('chatHeader');
    const chatInputArea = document.getElementById('chatInputArea');
    
    if (chatHeader) chatHeader.style.display = 'flex';
    if (chatInputArea) chatInputArea.style.display = 'block';
    
    try {
        // Load session details
        const response = await fetch(`/api/v1/experts/sessions/${sessionId}`);
        
        if (!response.ok) {
            if (response.status === 401) {
                console.warn('⚠️ Session access denied');
                showError('You do not have access to this session');
                return;
            }
            throw new Error(`Failed to load session: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Update header
        updateChatHeader(data);
        
        // Load messages
        await loadMessages(sessionId);
        
        // Start polling for new messages
        startMessagePolling();
        
    } catch (error) {
        console.error('❌ Error opening chat:', error);
        showError('Failed to load chat: ' + error.message);
    }
}
    // =====================================================
    // LOAD MESSAGES
    // =====================================================
async function loadMessages(sessionId) {
    try {
        const response = await fetch(`/api/v1/experts/sessions/${sessionId}/messages`);
        
        if (response.status === 401) {
            console.warn('⚠️ Unauthorized access to session messages');
            const messagesContainer = document.getElementById('chatMessages');
            if (messagesContainer) {
                messagesContainer.innerHTML = `
                    <div class="empty-state">
                        <i class="ti ti-lock"></i>
                        <p>Access Denied</p>
                        <p style="font-size: 12px;">You do not have permission to view these messages</p>
                    </div>
                `;
            }
            return;
        }
        
        if (!response.ok) {
            throw new Error('Failed to load messages');
        }
        
        const data = await response.json();
        
        const messagesContainer = document.getElementById('chatMessages');
        if (!messagesContainer) {
            console.error('Messages container not found');
            return;
        }
        
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
        console.error('❌ Error loading messages:', error);
        const messagesContainer = document.getElementById('chatMessages');
        if (messagesContainer) {
            messagesContainer.innerHTML = `
                <div class="empty-state">
                    <i class="ti ti-alert-circle"></i>
                    <p>Failed to load messages</p>
                    <p style="font-size: 12px;">${error.message}</p>
                </div>
            `;
        }
    }
}
    // =====================================================
    // CREATE MESSAGE ELEMENT
    // =====================================================
    function createMessageElement(message) {
        const div = document.createElement('div');
        div.className = 'message';
        
        const isUser = message.sender_type === 'user';
        if (isUser) {
            div.classList.add('sent');
        }
        
        // Get sender name or fallback to type
        const senderName = message.sender_name || (isUser ? 'You' : 'Expert');
        const initials = senderName.split(' ').map(n => n[0]).join('').toUpperCase().substring(0, 2);
        
        const time = new Date(message.created_at).toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        
        // Use message_content from API response
        const messageContent = message.message_content || message.message || '';
        
        div.innerHTML = `
            <div class="message-avatar">${initials}</div>
            <div class="message-content">
                <div class="message-bubble">${escapeHtml(messageContent)}</div>
                <div class="message-time">${time}</div>
            </div>
        `;
        
        return div;
    }
    
    // =====================================================
    // ESCAPE HTML
    // =====================================================
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
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
            console.log('📤 Sending message to session:', currentSessionId);
            
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
            
            console.log('📥 Response status:', response.status);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ Error response:', errorText);
                throw new Error('Failed to send message');
            }
            
            console.log('✅ Message sent successfully');
            
            // Clear input
            input.value = '';
            input.style.height = 'auto';
            
            // Reload messages
            await loadMessages(currentSessionId);
            
        } catch (error) {
            console.error('❌ Error sending message:', error);
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
            console.log('Expert modal opened');
        }
    }

    function closeExpertSelector() {
        const modal = document.getElementById('expertModal');
        if (modal) {
            modal.classList.remove('show');
            document.body.style.overflow = '';
            console.log('Expert modal closed');
        }
    }

    // =====================================================
    // CONSULTATION MODAL
    // =====================================================
    function openConsultationModal(expertId, expertName) {
        console.log('📋 Opening consultation modal for expert:', expertId, expertName);
        
        // Store selected expert
        selectedExpertForConsultation = {
            id: expertId,
            name: expertName
        };
        
        // Update modal with expert info
        document.getElementById('selectedExpertName').textContent = expertName;
        
        // Clear form
        document.getElementById('consultationSubjectInput').value = '';
        document.getElementById('consultationQuestionInput').value = '';
        
        // Show modal
        const modal = document.getElementById('consultationModal');
        if (modal) {
            modal.classList.add('show');
            document.body.style.overflow = 'hidden';
            
            // Focus on subject input
            setTimeout(() => {
                document.getElementById('consultationSubjectInput').focus();
            }, 100);
        }
    }

    window.closeConsultationModal = function() {
        const modal = document.getElementById('consultationModal');
        if (modal) {
            modal.classList.remove('show');
            document.body.style.overflow = '';
            selectedExpertForConsultation = null;
        }
    };

    // =====================================================
    // SUBMIT CONSULTATION REQUEST
    // =====================================================
    window.submitConsultationRequest = async function() {
        console.log('📤 Submitting consultation request...');
        
        if (!selectedExpertForConsultation) {
            showError('No expert selected');
            return;
        }
        
        const subject = document.getElementById('consultationSubjectInput').value.trim();
        const question = document.getElementById('consultationQuestionInput').value.trim();
        
        // Validation
        if (!subject) {
            showError('Please enter a subject');
            document.getElementById('consultationSubjectInput').focus();
            return;
        }
        
        if (!question) {
            showError('Please describe your question');
            document.getElementById('consultationQuestionInput').focus();
            return;
        }
        
        if (subject.length < 5) {
            showError('Subject must be at least 5 characters');
            document.getElementById('consultationSubjectInput').focus();
            return;
        }
        
        if (question.length < 10) {
            showError('Question must be at least 10 characters');
            document.getElementById('consultationQuestionInput').focus();
            return;
        }
        
        try {
            console.log('Sending request with data:', {
                expert_id: selectedExpertForConsultation.id,
                subject: subject,
                question: question
            });
            
            const requestData = {
                expert_id: selectedExpertForConsultation.id.toString(),
                session_type: 'chat',
                subject: subject,
                question: question
            };
            
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
            console.log('✅ Consultation created:', data);
            
            // Close both modals
            closeConsultationModal();
            closeExpertSelector();
            
            // Reload chat history
            console.log('🔄 Reloading chat history...');
            await loadChatHistory();
            
            // Open the new chat
            console.log('📂 Opening new chat...');
            await openChat(data.session_id);
            
            showSuccess('Consultation created successfully!');
            
        } catch (error) {
            console.error('❌ Error creating consultation:', error);
            showError('Failed to create consultation: ' + error.message);
        }
    };

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
            console.log(`✅ Loaded ${allExperts.length} experts`);
            
            renderExperts(allExperts);
            
        } catch (error) {
            console.error('❌ Error loading experts:', error);
            document.getElementById('expertsGrid').innerHTML = `
                <div class="loading-spinner">
                    <i class="ti ti-alert-circle" style="font-size: 32px; color: #dc3545;"></i>
                    <p style="color: #dc3545;">Failed to load experts</p>
                </div>
            `;
        }
    }

    // =====================================================
    // FILTER EXPERTS
    // =====================================================
    function filterExperts(category) {
        console.log('Filtering experts by category:', category);
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
                const spec = (expert.specialization || '').toLowerCase();
                return spec.includes(category);
            });
        }
        
        console.log(`Showing ${filtered.length} experts`);
        renderExperts(filtered);
    }

    // =====================================================
    // RENDER EXPERTS
    // =====================================================
    function renderExperts(experts) {
        const grid = document.getElementById('expertsGrid');
        
        if (experts.length === 0) {
            grid.innerHTML = `
                <div class="loading-spinner">
                    <i class="ti ti-users" style="font-size: 32px;"></i>
                    <p>No experts found in this category</p>
                </div>
            `;
            return;
        }
        
        grid.innerHTML = '';
        
        experts.forEach(expert => {
            console.log(`Rendering expert: ${expert.first_name} ${expert.last_name} (ID: ${expert.expert_id})`);
            const card = createExpertCard(expert);
            grid.appendChild(card);
        });
        
        console.log('✅ Expert cards rendered successfully');
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
        
        // Click handler - open consultation modal instead of prompts
        div.onclick = function(e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('🎯 Expert card clicked! ID:', expert.expert_id, 'Name:', fullName);
            openConsultationModal(expert.expert_id, fullName);
        };
        
        return div;
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
    // NOTIFICATION HELPERS
    // =====================================================
    function showSuccess(message) {
        console.log('✅ Success:', message);
        alert(message);
    }

    function showError(message) {
        console.error('❌ Error:', message);
        alert('Error: ' + message);
    }

    function showInfo(message) {
        console.log('ℹ️ Info:', message);
        alert(message);
    }

    // =====================================================
    // EXPOSE GLOBAL FUNCTIONS
    // =====================================================
    window.openExpertSelector = openExpertSelector;
    window.closeExpertSelector = closeExpertSelector;
    window.sendMessage = sendMessage;
    window.handleEnterKey = handleEnterKey;
    window.searchChats = searchChats;
    window.endSession = endSession;

})();