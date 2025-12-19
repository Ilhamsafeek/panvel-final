// =====================================================
// NEGOTIATION MODULE
// =====================================================

let currentNegotiationSession = null;
let messagePollingInterval = null;
let displayedMessageIds = new Set(); // Track displayed messages
let isSendingMessage = false; // Prevent double-sends

// =====================================================
// GET CONTRACT ID SAFELY
// =====================================================

function getContractId() {
    // Try multiple sources to get contract ID
    let id = null;
    
    // 1. Try global contractId variable
    if (typeof contractId !== 'undefined' && contractId) {
        id = contractId;
    }
    // 2. Try contractData object
    else if (typeof contractData !== 'undefined' && contractData?.contract?.id) {
        id = contractData.contract.id;
    }
    // 3. Try from URL path (e.g., /contracts/247/edit)
    else {
        const pathParts = window.location.pathname.split('/');
        const contractIndex = pathParts.indexOf('contracts');
        if (contractIndex !== -1 && pathParts[contractIndex + 1]) {
            id = pathParts[contractIndex + 1];
        }
    }
    
    // Validate and return
    if (!id) {
        console.error('❌ Contract ID not found!');
        console.log('Available sources:', {
            contractId: typeof contractId !== 'undefined' ? contractId : 'undefined',
            contractData: typeof contractData !== 'undefined' ? contractData : 'undefined',
            pathname: window.location.pathname
        });
        return null;
    }
    
    // Remove any non-numeric characters
    id = String(id).replace(/\D/g, '');
    
    console.log('✅ Using Contract ID:', id);
    return id;
}

// =====================================================
// OPEN NEGOTIATION MODAL
// =====================================================

function openNegotiationModal() {
    openModal('negotiationModal');
}

// =====================================================
// START INTERNAL NEGOTIATION
// =====================================================

async function startInternalNegotiation() {
    try {
        const contractId = getContractId();
        if (!contractId) {
            showNotification('Contract ID not found. Please refresh the page.', 'error');
            return;
        }
        
        showLoader();
        closeModal('negotiationModal');
        
        // Start negotiation session
        const response = await fetch('/api/negotiation/sessions/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                contract_id: contractId,
                session_type: 'internal',
                participant_ids: []
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentNegotiationSession = data;
            
            // Show appropriate message
            // if (data.message === "Joined existing negotiation session") {
            //     showNotification('Joined ongoing negotiation session', 'success');
            // } else {
            //     showNotification('Negotiation session started', 'success');
            // }

            if (data.message === "Joined existing negotiation session") {
                showNotification('Joining negotiation session', 'success');
            } else {
                showNotification('Negotiation session started', 'success');
            }
            
            // Open live negotiation modal
            setTimeout(() => {
                openLiveNegotiationModal('Internal Team Negotiation', 'internal');
            }, 300);
            
        } else {
            showNotification(data.message || data.detail || 'Failed to start negotiation', 'error');
        }
        
    } catch (error) {
        console.error('Error starting internal negotiation:', error);
        showNotification('Failed to start internal negotiation', 'error');
    } finally {
        hideLoader();
    }
}

// =====================================================
// START EXTERNAL NEGOTIATION (WITH INITIATOR)
// =====================================================

async function startExternalNegotiation() {

    const openNegotiationBtn = document.getElementById('openNegotiationBtn');
        const originalContent = openNegotiationBtn.innerHTML;
        openNegotiationBtn.disabled = true;
        openNegotiationBtn.innerHTML = '<i class="ti ti-loader" style="animation: spin 1s linear infinite;"></i> Opening…';

    try {
        const contractId = getContractId();
        if (!contractId) {
            showNotification('Contract ID not found. Please refresh the page.', 'error');
            return;
        }
        
        showLoader();
        closeModal('negotiationModal');
        
        // Start negotiation session
        const response = await fetch('/api/negotiation/sessions/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                contract_id: contractId,
                session_type: 'external',
                participant_ids: []
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentNegotiationSession = data;
            
            // Show appropriate message
            // if (data.message === "Joined existing negotiation session") {
            //     showNotification('Joined ongoing negotiation session', 'success');
            // } else {
            //     showNotification('Negotiation session started', 'success');
            // }

              if (data.message === "Joined existing negotiation session") {
                showNotification('Joining negotiation session', 'success');
            } else {
                showNotification('Negotiation session started', 'success');
            }
            
            // Open live negotiation modal
            setTimeout(() => {
                
                openLiveNegotiationModal('Negotiation Panel', 'external');
               
            }, 300);

             openNegotiationBtn.innerHTML = originalContent;
             openNegotiationBtn.disabled = false;
            
        } else {
            showNotification(data.message || data.detail || 'Failed to start negotiation', 'error');
        }
        
    } catch (error) {
        console.error('Error starting external negotiation:', error);
        showNotification('Failed to start external negotiation', 'error');
    } finally {
        hideLoader();
    }
}

// =====================================================
// OPEN LIVE NEGOTIATION MODAL
// =====================================================
async function openLiveNegotiationModal(title, type) {
    try {
        // Update modal title
        const modalTitleElement = document.querySelector('#liveNegotiationModal .modal-title');
        if (modalTitleElement) {
            modalTitleElement.innerHTML = `<i class="ti ti-video"></i> ${title}`;
        }
        
        // IMPORTANT: Clear messages area first to prevent duplicates
        const chatMessages = document.getElementById('chatMessages');
        if (chatMessages) {
            chatMessages.innerHTML = ``;
        }
        
        // Clear displayed messages tracking
        displayedMessageIds.clear();
        
        // Load messages (initial load)
        await loadNegotiationMessagesInitial();
        
        // Load participants (including workflow participants)
        await loadNegotiationParticipants();
        
        // Open modal
        openModal('liveNegotiationModal');
        
        // Focus on message input
        setTimeout(() => {
            const input = document.getElementById('messageInput');
            if (input) {
                input.focus();
            }
        }, 300);
        
        // Start polling for new messages
        startMessagePolling();
        
    } catch (error) {
        console.error('Error opening live negotiation:', error);
        showNotification('Failed to load negotiation session', 'error');
    }
}


async function loadNegotiationMessagesInitial() {
    if (!currentNegotiationSession) return;
    
    try {
        const response = await fetch(`/api/negotiation/messages/${currentNegotiationSession.session_id}`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.success && data.messages.length > 0) {
            // Use displayMessages for initial load (clears and loads all)
            displayMessages(data.messages);
        }
        
    } catch (error) {
        console.error('Error loading initial messages:', error);
    }
}

// =====================================================
// SMOOTH SCROLL TO BOTTOM
// =====================================================

function smoothScrollToBottom(element) {
    if (!element) return;
    
    const targetScroll = element.scrollHeight;
    const startScroll = element.scrollTop;
    const distance = targetScroll - startScroll;
    const duration = 300; // ms
    const startTime = performance.now();
    
    function animation(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Ease-out function for smooth deceleration
        const easeOut = 1 - Math.pow(1 - progress, 3);
        
        element.scrollTop = startScroll + (distance * easeOut);
        
        if (progress < 1) {
            requestAnimationFrame(animation);
        }
    }
    
    requestAnimationFrame(animation);
}

// =====================================================
// LOAD NEGOTIATION MESSAGES (SMART UPDATE)
// =====================================================

async function loadNegotiationMessages() {
    if (!currentNegotiationSession) return;
    
    try {
        const response = await fetch(`/api/negotiation/messages/${currentNegotiationSession.session_id}`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Only add NEW messages (not all messages)
            displayNewMessages(data.messages);
        }
        
    } catch (error) {
        console.error('Error loading messages:', error);
    }
}

// =====================================================
// DISPLAY NEW MESSAGES ONLY (FIXED - NO DUPLICATES)
// =====================================================

function displayNewMessages(messages) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    console.log('📥 Polling returned', messages.length, 'messages');
    console.log('📋 Already displayed:', Array.from(displayedMessageIds));
    
    // Filter to only NEW messages that haven't been displayed yet
    const newMessages = messages.filter(msg => {
        const isNew = !displayedMessageIds.has(msg.id);
        if (!isNew) {
            console.log('⏭️ Skipping duplicate:', msg.id, msg.message_content);
        }
        return isNew;
    });
    
    console.log('✨ Adding', newMessages.length, 'new messages');
    
    // Add only new messages with animation
    newMessages.forEach(msg => {
        console.log('➕ Adding message:', msg.id, msg.message_content);
        addMessageToChat(msg);
    });
}

// =====================================================
// DISPLAY MESSAGES (INITIAL LOAD ONLY)
// =====================================================
function displayMessages(messages) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    // Keep the welcome message, clear only the chat messages
    const welcomeMsg = chatMessages.querySelector('.welcome-message');
    chatMessages.innerHTML = '';
    
    if (welcomeMsg) {
        chatMessages.appendChild(welcomeMsg);
    } else {
        chatMessages.innerHTML = ``;
    }
    
    // Clear tracking
    displayedMessageIds.clear();
    
    // Add each message without animation (initial load)
    messages.forEach(msg => {
        const messageDiv = createMessageElement(msg);
        messageDiv.style.opacity = '1'; // No fade-in for initial load
        chatMessages.appendChild(messageDiv);
        displayedMessageIds.add(msg.id); // Track as displayed
    });
    
    // Instant scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}


// =====================================================
// CREATE MESSAGE ELEMENT (HELPER)
// =====================================================

function createMessageElement(message) {
    const messageDiv = document.createElement('div');
    messageDiv.setAttribute('data-message-id', message.id);
    
    if (message.message_type === 'system') {
        messageDiv.className = 'system-message';
        messageDiv.innerHTML = `
            <div class="system-icon"><i class="ti ti-info-circle"></i></div>
            <div class="system-text">${escapeHtml(message.message_content)}</div>
        `;
    } else {
        const isCurrentUser = message.sender_type === 'current_user';
        messageDiv.className = isCurrentUser ? 'message user-msg' : 'message initiator-msg';
        
        const timestamp = message.created_at ? new Date(message.created_at).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        }) : 'Just now';
        
        messageDiv.innerHTML = `
            ${!isCurrentUser ? '<div class="message-avatar"><i class="ti ti-user"></i></div>' : ''}
            <div class="message-content">
                <div class="message-header">
                    <span class="sender">${escapeHtml(message.sender_name)}</span>
                    <span class="timestamp">${timestamp}</span>
                </div>
                <div class="message-text">${escapeHtml(message.message_content)}</div>
            </div>
        `;
    }
    
    return messageDiv;
}
// =====================================================
// ADD MESSAGE TO CHAT - FIXED (Track message ID)
// =====================================================

function addMessageToChat(message) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    // Check if already displayed (prevent duplicates)
    if (displayedMessageIds.has(message.id)) {
        console.log('⏭️ Message already displayed:', message.id);
        return;
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.setAttribute('data-message-id', message.id);
    
    if (message.message_type === 'system') {
        messageDiv.className = 'system-message';
        messageDiv.innerHTML = `
            <div class="system-icon"><i class="ti ti-info-circle"></i></div>
            <div class="system-text">${escapeHtml(message.message_content)}</div>
        `;
    } else {
        const isCurrentUser = message.sender_type === 'current_user';
        messageDiv.className = isCurrentUser ? 'message user-msg' : 'message initiator-msg';
        
        const timestamp = message.created_at ? new Date(message.created_at).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit'
        }) : 'Just now';
        
        messageDiv.innerHTML = `
            ${!isCurrentUser ? '<div class="message-avatar"><i class="ti ti-user"></i></div>' : ''}
            <div class="message-content">
                <div class="message-header">
                    <span class="sender">${escapeHtml(message.sender_name)}</span>
                    <span class="timestamp">${timestamp}</span>
                </div>
                <div class="message-text">${escapeHtml(message.message_content)}</div>
            </div>
        `;
    }
    
    // Add with fade-in animation
    messageDiv.style.opacity = '0';
    chatMessages.appendChild(messageDiv);
    
    // IMPORTANT: Track this message as displayed
    displayedMessageIds.add(message.id);
    console.log('✅ Message displayed and tracked:', message.id);
    
    // Animate in
    setTimeout(() => {
        messageDiv.style.transition = 'opacity 0.3s ease';
        messageDiv.style.opacity = '1';
    }, 10);
    
    // Smooth scroll to bottom
    smoothScrollToBottom(chatMessages);
}


// =====================================================
// SEND MESSAGE (FIXED)
// =====================================================

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const sendBtn = document.querySelector('.send-btn');
    
    if (!input || !currentNegotiationSession || isSendingMessage) {
        return;
    }
    
    const message = input.value.trim();
    if (!message) return;
    
    try {
        // Set loading state
        isSendingMessage = true;
        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="ti ti-loader" style="animation: spin 1s linear infinite;"></i>';
        
        // Clear input immediately for better UX
        const messageCopy = message;
        input.value = '';
        
        // Send to server (NO optimistic UI - wait for confirmation)
        const response = await fetch('/api/negotiation/messages/send', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                session_id: currentNegotiationSession.session_id,
                message_content: messageCopy,
                message_type: 'text'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Add message immediately (server confirmed, correct sender_type)
            console.log('✅ Message sent:', data.message.id, data.message.message_content);
            addMessageToChat(data.message);
        } else {
            // Restore input on failure
            input.value = messageCopy;
            showNotification('Failed to send message', 'error');
        }
        
    } catch (error) {
        console.error('Error sending message:', error);
        input.value = message; // Restore on error
        showNotification('Failed to send message', 'error');
    } finally {
        // Reset button state
        isSendingMessage = false;
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<i class="ti ti-send"></i>';
        input.focus();
    }
}

// =====================================================
// HANDLE ENTER KEY IN MESSAGE INPUT
// =====================================================

function handleMessageKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// =====================================================
// LOAD PARTICIPANTS (INCLUDING WORKFLOW PARTICIPANTS)
// =====================================================

async function loadNegotiationParticipants() {
    if (!currentNegotiationSession) return;
    
    try {
        // Get negotiation session participants
        const sessionResponse = await fetch(`/api/negotiation/sessions/${currentNegotiationSession.session_id}`, {
            credentials: 'include'
        });
        
        const sessionData = await sessionResponse.json();
        
        let allParticipants = [];
        
        if (sessionData.success && sessionData.participants) {
            allParticipants = sessionData.participants;
        }
        
        // Also fetch workflow participants from the contract
        if (currentNegotiationSession.contract_id) {
            try {
                // CORRECTED ENDPOINT: /api/contract/workflow/{contract_id}
                const workflowResponse = await fetch(`/api/contract/workflow/${currentNegotiationSession.contract_id}`, {
                    credentials: 'include'
                });
                
                const workflowData = await workflowResponse.json();
                
                if (workflowData.success && workflowData.workflow && workflowData.workflow.steps) {
                    console.log('📋 Workflow steps found:', workflowData.workflow.steps.length);
                    
                    // Extract users from workflow steps
                    workflowData.workflow.steps.forEach(step => {
                        // Each step can have multiple users
                        if (step.users && Array.isArray(step.users)) {
                            step.users.forEach(user => {
                                // Check if not already in participants
                                const exists = allParticipants.some(p => p.user_id === user.id);
                                if (!exists) {
                                    allParticipants.push({
                                        user_id: user.id,
                                        full_name: user.name || user.email,
                                        email: user.email,
                                        role: step.step_name || step.assignee_role,
                                        status: 'online'
                                    });
                                    console.log('➕ Added workflow participant:', user.name);
                                }
                            });
                        }
                    });
                }
            } catch (workflowError) {
                console.log('Could not fetch workflow participants:', workflowError);
            }
        }
        
        console.log('👥 Total participants to display:', allParticipants.length);
        updateParticipantsDisplay(allParticipants);
        
    } catch (error) {
        console.error('Error loading participants:', error);
    }
}

// =====================================================
// UPDATE PARTICIPANTS DISPLAY
// =====================================================
function updateParticipantsDisplay(participants) {
    const participantsContainer = document.querySelector('.participants');
    if (!participantsContainer) return;
    
    // Clear existing participants
    participantsContainer.innerHTML = '';
    
    if (!participants || participants.length === 0) {
        participantsContainer.innerHTML = '<div class="participant"><span>No participants</span></div>';
        return;
    }
    
    // Get current user ID - try multiple sources
    let currentUserId = window.currentUserId || 
                        document.body.dataset.userId || 
                        sessionStorage.getItem('userId');
    
    // Convert to string for comparison
    currentUserId = String(currentUserId);
    
    console.log('Current User ID:', currentUserId); // Debug log
    console.log('Participants:', participants); // Debug log
    
    // Check if current user is initiator
    const currentUserParticipant = participants.find(p => String(p.user_id) === currentUserId);
    const isCurrentUserInitiator = currentUserParticipant && currentUserParticipant.role === 'initiator';
    
    console.log('Current user is initiator:', isCurrentUserInitiator); // Debug log
    
    participants.forEach(participant => {
        const participantDiv = document.createElement('div');
        participantDiv.className = 'participant online';
        
        // Determine if this is the current user (string comparison)
        const isCurrentUser = String(participant.user_id) === currentUserId;
        
        // Determine display name and role
        let displayName = participant.full_name || 'User';
        let displayRole = '';
        
        if (isCurrentUser) {
            // Current user shows as "You"
            displayName = 'You';
            if (participant.role === 'initiator') {
                displayRole = '(Initiator)';
            } else if (participant.role === 'participant') {
                displayRole = '(Participant)';
            } else if (participant.role === 'counterparty') {
                displayRole = '(Counter-Party)';
            }
        } else {
            // Other participants
            if (isCurrentUserInitiator) {
                // If current user is initiator, show others as Counter-Party
                displayRole = '(Counter-Party)';
            } else {
                // Show actual role
                if (participant.role === 'initiator') {
                    displayRole = '(Initiator)';
                } else if (participant.role === 'participant') {
                    displayRole = '';
                } else if (participant.role === 'counterparty') {
                    displayRole = '(Counter-Party)';
                }
            }
        }
        
        participantDiv.innerHTML = `
            <div class="status-dot"></div>
            <span>${displayName} ${displayRole}</span>
        `;
        
        participantsContainer.appendChild(participantDiv);
    });
}


// =====================================================
// START MESSAGE POLLING
// =====================================================

function startMessagePolling() {
    // Clear any existing interval
    if (messagePollingInterval) {
        clearInterval(messagePollingInterval);
    }
    
    // Poll for new messages every 3 seconds
    messagePollingInterval = setInterval(() => {
        loadNegotiationMessages();
    }, 3000);
}

// =====================================================
// STOP MESSAGE POLLING
// =====================================================

function stopMessagePolling() {
    if (messagePollingInterval) {
        clearInterval(messagePollingInterval);
        messagePollingInterval = null;
    }
    // Clear displayed messages tracking when session ends
    displayedMessageIds.clear();
}

// =====================================================
// FINALIZE NEGOTIATION
// =====================================================

async function finalizeNegotiation() {
    if (!currentNegotiationSession) return;
    
    if (!confirm('Are you sure you want to finalize this negotiation? This will end the session.')) {
        return;
    }
    
    try {
        showLoader();
        
        const response = await fetch(`/api/negotiation/sessions/${currentNegotiationSession.session_id}/end`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                outcome: 'finalized'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('Negotiation finalized successfully!', 'success');
            stopMessagePolling();
            closeModal('liveNegotiationModal');
            currentNegotiationSession = null;
            
            // Refresh contract data
            setTimeout(() => location.reload(), 1500);
        } else {
            showNotification('Failed to finalize negotiation', 'error');
        }
        
    } catch (error) {
        console.error('Error finalizing negotiation:', error);
        showNotification('Failed to finalize negotiation', 'error');
    } finally {
        hideLoader();
    }
}

// =====================================================
// DOWNLOAD MINUTES
// =====================================================

async function downloadMinutes() {
    if (!currentNegotiationSession) return;
    
    try {
        showLoader();
        
        const response = await fetch(`/api/negotiation/sessions/${currentNegotiationSession.session_id}/minutes`, {
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Create download link
            const blob = new Blob([data.minutes], { type: 'text/plain' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = data.filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            showNotification('Minutes downloaded successfully!', 'success');
        } else {
            showNotification('Failed to download minutes', 'error');
        }
        
    } catch (error) {
        console.error('Error downloading minutes:', error);
        showNotification('Failed to download minutes', 'error');
    } finally {
        hideLoader();
    }
}

// =====================================================
// INSERT SUGGESTION
// =====================================================

function insertSuggestion(suggestion) {
    const input = document.getElementById('messageInput');
    if (input) {
        input.value = suggestion;
        input.focus();
    }
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
// CLEANUP ON MODAL CLOSE
// =====================================================

// Add event listener to stop polling when modal closes
document.addEventListener('DOMContentLoaded', () => {
    const liveNegotiationModal = document.getElementById('liveNegotiationModal');
    if (liveNegotiationModal) {
        // Observe when modal is closed
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.attributeName === 'class') {
                    const isOpen = liveNegotiationModal.classList.contains('show') || 
                                   liveNegotiationModal.classList.contains('active');
                    if (!isOpen) {
                        stopMessagePolling();
                    }
                }
            });
        });
        
        observer.observe(liveNegotiationModal, { attributes: true });
    }
});

console.log('✅ Negotiation module loaded');