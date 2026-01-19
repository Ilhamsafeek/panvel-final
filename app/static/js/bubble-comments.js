// =====================================================
// BUBBLE COMMENTS - FIXED WITH DEBUGGING
// =====================================================

let allComments = [];
let currentBubble = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    console.log('🎨 BUBBLE COMMENTS INITIALIZING...');
    initializeBubbleComments();
});

function initializeBubbleComments() {
    console.log('📋 Starting Bubble Comments System');
    
    // Get contract ID - check multiple sources
    function getContractId() {
        // Method 1: URL parameter
        const urlParams = new URLSearchParams(window.location.search);
        let id = urlParams.get('id');
        if (id) return id;
        
        // Method 2: Global contractId variable
        if (typeof contractId !== 'undefined' && contractId) return contractId;
        
        // Method 3: Hidden input
        const input = document.getElementById('contractId');
        if (input && input.value) return input.value;
        
        // Method 4: Parse from URL path
        const pathParts = window.location.pathname.split('/');
        const editIndex = pathParts.indexOf('edit');
        if (editIndex !== -1 && pathParts[editIndex + 1]) {
            return pathParts[editIndex + 1];
        }
        
        return null;
    }
    
    currentContractId = getContractId();
    console.log('🆔 Contract ID:', currentContractId);
    
    if (currentContractId) {
        console.log('📥 Will load comments for contract:', currentContractId);
        // Load immediately
        loadComments();
        
        // Also load after a delay (in case content isn't ready)
        setTimeout(loadComments, 1000);
        setTimeout(loadComments, 3000);
    } else {
        console.warn('⚠️ No contract ID found!');
    }
    
    // Setup event listeners
    setupCommentListeners();
    
    // Close bubble when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.comment-bubble') && 
            !e.target.closest('.comment-highlight') && 
            !e.target.closest('.track-insert') && 
            !e.target.closest('.track-delete')) {
            closeBubble();
        }
    });
    
    console.log('✅ Bubble Comments Initialized');
}

function setupCommentListeners() {
    console.log('🔗 Setting up listeners...');
    
    // Add comment button
    const addCommentBtn = document.getElementById('addCommentBtn');
    if (addCommentBtn) {
        addCommentBtn.addEventListener('click', openAddCommentModal);
        console.log('✅ Add comment button listener added');
    } else {
        console.warn('⚠️ addCommentBtn not found');
    }
    
    // Toggle comments panel
    const toggleBtn = document.getElementById('toggleCommentsBtn');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', toggleCommentsPanel);
        console.log('✅ Toggle button listener added');
    }
}

// =====================================================
// LOAD COMMENTS
// =====================================================
async function loadComments() {
    try {
        console.log('📥 Loading comments for contract:', currentContractId);
        
        const response = await fetch(`/api/contracts/comments/${currentContractId}`, {
            credentials: 'include'
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        console.log('📦 API Response:', data);
        
        if (data.success) {
            allComments = data.comments || [];
            console.log(`✅ Loaded ${allComments.length} comments:`, allComments);
            
            // Wait for contract content to be ready
            const content = document.getElementById('contractContent');
            if (!content || content.innerHTML.trim().length < 100) {
                console.log('⏳ Contract content not ready, will retry highlighting...');
                // Retry after delays
                setTimeout(() => {
                    console.log('🔄 Retry 1: Highlighting comments...');
                    highlightCommentsInDocument();
                }, 1000);
                setTimeout(() => {
                    console.log('🔄 Retry 2: Highlighting comments...');
                    highlightCommentsInDocument();
                }, 3000);
                setTimeout(() => {
                    console.log('🔄 Retry 3: Highlighting comments...');
                    highlightCommentsInDocument();
                }, 5000);
            } else {
                // Content ready, highlight immediately
                highlightCommentsInDocument();
            }
            
            // Update comments panel
            updateCommentsPanel();
            
            // Update badge count
            updateCommentBadge();
        } else {
            console.error('❌ API returned success=false:', data);
        }
    } catch (error) {
        console.error('❌ Error loading comments:', error);
    }
}


// =====================================================
// HIGHLIGHT AT EXACT POSITION (for new comments)
// =====================================================
function highlightAtExactPosition(selectionData, commentId, changeType) {
    console.log('🎯 Highlighting at EXACT position:', selectionData);
    
    try {
        const range = selectionData.range;
        if (!range) {
            console.error('❌ No range data, falling back to text search');
            // Fallback to old method
            highlightTextInContent(
                document.getElementById('contractContent'),
                selectionData.text,
                getHighlightClass(changeType),
                commentId
            );
            return;
        }
        
        // Clone the range to avoid modifying original
        const highlightRange = range.cloneRange();
        
        // Create highlight span
        const span = document.createElement('span');
        const className = getHighlightClass(changeType);
        span.className = className;
        span.dataset.commentId = commentId;
        span.style.cursor = 'pointer';
        span.style.position = 'relative';
        
        // CRITICAL: Make text non-editable
        span.contentEditable = 'false';
        span.setAttribute('data-protected', 'true');
        span.title = 'This text has a comment. Click to view or resolve the comment before editing.';
        
        // Add click listeners
        span.onclick = function(e) {
            console.log(`🖱️ Clicked on comment ${commentId}`);
            e.preventDefault();
            e.stopPropagation();
            showBubble(parseInt(commentId), e);
        };
        
        span.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            showBubble(parseInt(commentId), e);
        }, true);
        
        // Prevent editing
        span.addEventListener('keydown', function(e) {
            e.preventDefault();
            e.stopPropagation();
            showNotification('This text is protected by a comment. Resolve the comment first.', 'warning');
            this.style.animation = 'protectedFlash 0.5s ease 2';
        });
        
        span.addEventListener('beforeinput', function(e) {
            e.preventDefault();
            e.stopPropagation();
            showNotification('Cannot edit commented text. Resolve or delete the comment first.', 'warning');
        });
        
        // Wrap the range contents
        try {
            highlightRange.surroundContents(span);
            console.log('✅ Exact position highlighted successfully');
        } catch (e) {
            console.error('❌ Could not wrap range:', e);
            console.log('Falling back to text search method...');
            // Fallback to old method if wrapping fails
            highlightTextInContent(
                document.getElementById('contractContent'),
                selectionData.text,
                className,
                commentId
            );
        }
        
    } catch (error) {
        console.error('❌ Error highlighting exact position:', error);
    }
}


// =====================================================
// HIGHLIGHT COMMENTS IN DOCUMENT - FIXED VERSION
// =====================================================
function highlightCommentsInDocument() {
    console.log('🎨 Highlighting comments in document...');
    
    const content = document.getElementById('contractContent');
    if (!content) {
        console.error('❌ contractContent element not found!');
        return;
    }
    
    console.log('✅ Found contractContent element');
    
    // Remove existing highlights first
    const existing = content.querySelectorAll('.comment-highlight, .track-insert, .track-delete');
    console.log(`🧹 Removing ${existing.length} existing highlights`);
    existing.forEach(el => {
        const parent = el.parentNode;
        while (el.firstChild) {
            parent.insertBefore(el.firstChild, el);
        }
        parent.removeChild(el);
    });
    
    // Apply new highlights
    allComments.forEach((comment, index) => {
        console.log(`🔍 Processing comment ${index + 1}:`, comment);
        
        try {
            const className = getHighlightClass(comment.change_type);
            console.log(`  Class: ${className}, Text: "${comment.selected_text}"`);
            
            const success = highlightTextInContent(content, comment.selected_text, className, comment.id);
            
            if (success) {
                console.log(`  ✅ Highlighted successfully`);
            } else {
                console.warn(`  ⚠️ Could not find text to highlight`);
            }
        } catch (error) {
            console.error(`  ❌ Error highlighting comment:`, error);
        }
    });
    
    console.log('✅ Highlighting complete');
}

function getHighlightClass(changeType) {
    switch (changeType) {
        case 'insert': return 'track-insert';
        case 'delete': return 'track-delete';
        default: return 'comment-highlight';
    }
}

function highlightTextInContent(container, searchText, className, commentId) {
    console.log(`🔎 Searching for text: "${searchText}"`);
    
    // Get all text nodes
    const textNodes = [];
    const walker = document.createTreeWalker(
        container,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );
    
    let node;
    while (node = walker.nextNode()) {
        if (node.textContent.trim()) {
            textNodes.push(node);
        }
    }
    
    console.log(`  Found ${textNodes.length} text nodes`);
    
    // Search for the text in nodes
    for (const textNode of textNodes) {
        const text = textNode.textContent;
        const index = text.indexOf(searchText);
        
        if (index !== -1) {
            console.log(`  ✅ Found text at index ${index} in node:`, textNode);
            
            // Create highlight span
            const span = document.createElement('span');
            span.className = className;
            span.dataset.commentId = commentId;
            span.style.cursor = 'pointer';
            span.style.position = 'relative';
            
            // CRITICAL: Make text non-editable
            span.contentEditable = 'false';
            span.setAttribute('data-protected', 'true');
            
            // Add lock icon for visual indication
            span.title = 'This text has a comment. Click to view or resolve the comment before editing.';
            
            // CRITICAL: Add click listener with proper event handling
            span.onclick = function(e) {
                console.log(`🖱️ Clicked on comment ${commentId}`);
                e.preventDefault();
                e.stopPropagation();
                showBubble(parseInt(commentId), e);
            };
            
            // Also add addEventListener as backup
            span.addEventListener('click', function(e) {
                console.log(`🖱️ Event listener triggered for comment ${commentId}`);
                e.preventDefault();
                e.stopPropagation();
                showBubble(parseInt(commentId), e);
            }, true);
            
            // Prevent editing attempts
            span.addEventListener('keydown', function(e) {
                e.preventDefault();
                e.stopPropagation();
                showNotification('This text is protected by a comment. Resolve the comment first.', 'warning');
                // Flash the highlight
                this.style.animation = 'protectedFlash 0.5s ease 2';
            });
            
            span.addEventListener('beforeinput', function(e) {
                e.preventDefault();
                e.stopPropagation();
                showNotification('Cannot edit commented text. Resolve or delete the comment first.', 'warning');
            });
            
            // Prevent paste
            span.addEventListener('paste', function(e) {
                e.preventDefault();
                showNotification('Cannot paste into commented text.', 'warning');
            });
            
            // Prevent drag & drop
            span.addEventListener('drop', function(e) {
                e.preventDefault();
                showNotification('Cannot drop content into commented text.', 'warning');
            });
            
            // Split text and wrap
            const before = text.substring(0, index);
            const highlighted = text.substring(index, index + searchText.length);
            const after = text.substring(index + searchText.length);
            
            const parent = textNode.parentNode;
            
            if (before) {
                parent.insertBefore(document.createTextNode(before), textNode);
            }
            
            span.textContent = highlighted;
            parent.insertBefore(span, textNode);
            
            if (after) {
                parent.insertBefore(document.createTextNode(after), textNode);
            }
            
            parent.removeChild(textNode);
            
            console.log('  ✅ Wrapped text with protected highlight and click listeners');
            return true;
        }
    }
    
    console.warn('  ⚠️ Text not found in document');
    return false;
}

// =====================================================
// ATTACH CLICK LISTENERS TO ALL HIGHLIGHTS
// =====================================================
function attachClickListenersToHighlights() {
    const highlights = document.querySelectorAll('.comment-highlight, .track-insert, .track-delete');
    console.log(`🔗 Attaching click listeners to ${highlights.length} highlights...`);
    
    highlights.forEach(highlight => {
        const commentId = highlight.getAttribute('data-comment-id');
        
        // Remove existing listener by cloning
        const newHighlight = highlight.cloneNode(true);
        highlight.parentNode.replaceChild(newHighlight, highlight);
        
        // Add onclick handler
        newHighlight.onclick = function(e) {
            console.log(`🖱️ Clicked highlight for comment ${commentId}`);
            e.preventDefault();
            e.stopPropagation();
            showBubble(parseInt(commentId), e);
        };
        
        // Also add addEventListener as backup
        newHighlight.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            showBubble(parseInt(commentId), e);
        }, true);
    });
    
    console.log('✅ Click listeners attached to all highlights');
}

// =====================================================
// SHOW BUBBLE TOOLTIP - FIXED
// =====================================================
function showBubble(commentId, event) {
    console.log('💬 SHOWING BUBBLE for comment:', commentId);
    
    const comment = allComments.find(c => c.id === commentId);
    if (!comment) {
        console.error('❌ Comment not found:', commentId);
        return;
    }
    
    console.log('✅ Found comment:', comment);
    
    // Remove existing bubble
    closeBubble();
    
    // Create bubble
    const bubble = document.createElement('div');
    bubble.className = 'comment-bubble active';
    bubble.id = 'commentBubble';
    
    // Get initials
    const nameParts = comment.user_name.split(' ');
    const initials = nameParts.map(n => n[0]).join('').toUpperCase();
    
    // Format time
    const timeAgo = formatTimeAgo(new Date(comment.created_at));
    
    // Determine if this is a tracked change (not just a comment)
    const isTrackedChange = comment.change_type && comment.change_type !== 'comment';
    
    // Build bubble HTML
    bubble.innerHTML = `
        <div class="comment-bubble-header">
            <div class="comment-author">
                <div class="comment-author-avatar">${initials}</div>
                <div class="comment-author-info">
                    <div class="comment-author-name">${escapeHtml(comment.user_name)}</div>
                </div>
            </div>
            <div class="comment-actions">
                ${comment.can_delete ? `
                    <button class="comment-action-btn delete" onclick="deleteComment(${comment.id})" title="Delete">
                        <i class="ti ti-trash" style="font-size: 18px;"></i>
                    </button>
                ` : ''}
                <button class="comment-action-btn" onclick="closeBubble()" title="Close">
                    <i class="ti ti-x" style="font-size: 18px;"></i>
                </button>
            </div>
        </div>
        <div class="comment-bubble-body">
            <div class="comment-text">${escapeHtml(comment.comment_text)}</div>
            ${comment.selected_text ? `
                <div class="comment-selected-text">
                    <i class="ti ti-quote"></i> "${escapeHtml(comment.selected_text)}"
                </div>
            ` : ''}
            ${renderTrackChanges(comment)}
        </div>
        ${isTrackedChange ? `
            <div class="comment-bubble-actions" style="padding: 12px; border-top: 1px solid #e0e0e0; display: flex; gap: 8px; background: #f8f9fa;">
                <button onclick="acceptChange(${comment.id})" style="flex: 1; padding: 8px 12px; background: #28a745; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 6px;">
                    <i class="ti ti-check"></i> Accept Change
                </button>
                <button onclick="rejectChange(${comment.id})" style="flex: 1; padding: 8px 12px; background: #dc3545; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 6px;">
                    <i class="ti ti-x"></i> Reject Change
                </button>
            </div>
        ` : ''}
    `;
    
    document.body.appendChild(bubble);
    currentBubble = bubble;
    
    console.log('✅ Bubble created and added to DOM');
    
    // Position bubble near clicked element
    positionBubble(bubble, event.target);
}

function renderTrackChanges(comment) {
    if (comment.change_type === 'comment' || !comment.change_type) return '';
    
    console.log('🔄 Rendering track changes for:', comment.change_type);
    
    let html = '<div class="track-changes-details">';
    
    if (comment.change_type === 'delete') {
        html += `
            <span class="track-change-label">
                <i class="ti ti-trash"></i> Deleted Text:
            </span>
            <div class="track-original">${escapeHtml(comment.original_text || comment.selected_text)}</div>
        `;
    } else if (comment.change_type === 'insert') {
        html += `
            <span class="track-change-label">
                <i class="ti ti-plus"></i> Inserted Text:
            </span>
            <div class="track-new">${escapeHtml(comment.new_text || comment.selected_text)}</div>
        `;
        if (comment.original_text) {
            html += `
                <span class="track-change-label" style="margin-top: 8px;">
                    <i class="ti ti-arrow-back"></i> Replaced:
                </span>
                <div class="track-original">${escapeHtml(comment.original_text)}</div>
            `;
        }
    }
    
    html += '</div>';
    return html;
}

function positionBubble(bubble, target) {
    console.log('📍 Positioning bubble near:', target);
    
    const rect = target.getBoundingClientRect();
    const bubbleRect = bubble.getBoundingClientRect();
    
    let top = rect.bottom + window.scrollY + 10;
    let left = rect.left + window.scrollX;
    
    // Adjust if bubble goes off screen
    if (left + bubbleRect.width > window.innerWidth) {
        left = window.innerWidth - bubbleRect.width - 20;
    }
    
    if (top + bubbleRect.height > window.innerHeight + window.scrollY) {
        top = rect.top + window.scrollY - bubbleRect.height - 10;
    }
    
    bubble.style.top = top + 'px';
    bubble.style.left = left + 'px';
    
    console.log(`✅ Bubble positioned at (${left}, ${top})`);
}

function closeBubble() {
    if (currentBubble) {
        console.log('🗑️ Closing bubble');
        currentBubble.remove();
        currentBubble = null;
    }
}

// =====================================================
// ADD COMMENT
// =====================================================
function openAddCommentModal() {
    console.log('➕ Opening add comment modal');
    
    const selection = window.getSelection();
    console.log('📝 Current selection:', selection.toString());
    
    if (!selection.rangeCount || selection.toString().trim() === '') {
        showNotification('Please select text to comment on', 'warning');
        console.warn('⚠️ No text selected');
        return;
    }
    
    const selectedText = selection.toString().trim();
    const range = selection.getRangeAt(0).cloneRange();
    
    console.log('✅ Selected text:', selectedText);
    
    // Store selection BEFORE opening modal (selection gets cleared)
    window.commentSelection = {
        text: selectedText,
        range: range
    };
    
    // Show modal
    const modal = document.getElementById('commentModal');
    if (modal) {
        modal.style.display = 'flex';
        
        // Clear textarea
        const textarea = document.getElementById('commentText');
        if (textarea) {
            textarea.value = '';
            setTimeout(() => textarea.focus(), 100);
        }
        
        // Update preview IMMEDIATELY
        const preview = document.getElementById('selectedTextPreview');
        if (preview) {
            preview.textContent = selectedText;
            preview.style.fontStyle = 'normal';
            preview.style.color = '#333';
            console.log('✅ Preview updated with:', selectedText);
        } else {
            console.error('❌ selectedTextPreview element not found');
        }
        
        console.log('✅ Modal opened with selection:', selectedText);
    } else {
        console.error('❌ commentModal not found');
    }
}

async function submitComment() {
    console.log('💾 Submitting comment...');
    
    const commentText = document.getElementById('commentText').value.trim();
    if (!commentText || !window.commentSelection) {
        showNotification('Please enter a comment', 'warning');
        console.warn('⚠️ No comment text or selection');
        return;
    }
    
    // Get change type from radio buttons
    const changeType = document.querySelector('input[name="changeType"]:checked')?.value || 'comment';
    const newText = document.getElementById('newText')?.value.trim() || null;
    
    // Validate modification requires new text
    if (changeType === 'insert' && !newText) {
        showNotification('Please enter the new text for modification', 'warning');
        return;
    }
    
    console.log('📤 Sending to API with exact position:', {
        contract_id: currentContractId,
        comment_text: commentText,
        selected_text: window.commentSelection.text,
        change_type: changeType,
        position_start: window.commentSelection.absoluteStart,
        position_end: window.commentSelection.absoluteEnd,
        start_xpath: window.commentSelection.startXPath,
        original_text: window.commentSelection.text,
        new_text: newText
    });
    
    try {
        const response = await fetch('/api/contracts/comments/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                contract_id: parseInt(currentContractId),
                comment_text: commentText,
                selected_text: window.commentSelection.text,
                position_start: window.commentSelection.absoluteStart || 0,
                position_end: window.commentSelection.absoluteEnd || 0,
                start_xpath: window.commentSelection.startXPath || '',
                change_type: changeType,
                original_text: window.commentSelection.text,
                new_text: newText
            })
        });
        
        const data = await response.json();
        console.log('📥 API Response:', data);
        
        if (data.success) {
            // Add position info to comment object
            data.comment.position_start = window.commentSelection.absoluteStart;
            data.comment.position_end = window.commentSelection.absoluteEnd;
            data.comment.start_xpath = window.commentSelection.startXPath;
            
            allComments.push(data.comment);
            console.log('✅ Comment added with position, total:', allComments.length);
            
            // Highlight at EXACT position
            highlightAtExactPosition(window.commentSelection, data.comment.id, changeType);
            
            // CRITICAL: Re-attach click listeners after highlighting
            setTimeout(() => {
                console.log('🔗 Re-attaching click listeners after highlight...');
                attachClickListenersToHighlights();
            }, 200);
            
            // Update UI
            updateCommentsPanel();
            updateCommentBadge();
            
            closeModal('commentModal');
            window.commentSelection = null;
            
            // Reset form
            document.getElementById('commentText').value = '';
            if (document.getElementById('newText')) {
                document.getElementById('newText').value = '';
            }
            const defaultRadio = document.querySelector('input[name="changeType"][value="comment"]');
            if (defaultRadio) {
                defaultRadio.checked = true;
                if (typeof updateChangeType === 'function') {
                    updateChangeType('comment');
                }
            }
            
            const typeMessages = {
                'comment': 'Comment added successfully',
                'delete': 'Text marked for deletion',
                'insert': 'Change tracked successfully'
            };
            showNotification(typeMessages[changeType] || 'Comment added', 'success');
        } else {
            throw new Error(data.message || 'Failed to add comment');
        }
    } catch (error) {
        console.error('❌ Error adding comment:', error);
        showNotification('Failed to add comment: ' + error.message, 'error');
    }
}

// =====================================================
// ACCEPT/REJECT TRACKED CHANGES
// =====================================================

async function acceptChange(commentId) {
    console.log('✅ Accepting change for comment:', commentId);
    
    const comment = allComments.find(c => c.id === commentId);
    if (!comment) {
        console.error('❌ Comment not found');
        return;
    }
    
    if (!confirm('Accept this change? The modification will be applied to the document.')) {
        return;
    }
    
    try {
        // Find the highlight element
        const highlight = document.querySelector(`[data-comment-id="${commentId}"]`);
        if (!highlight) {
            console.error('❌ Highlight not found');
            return;
        }
        
        const parent = highlight.parentNode;
        
        // Apply the change based on type
        if (comment.change_type === 'delete') {
            // Delete: Remove the text completely
            console.log('🗑️ Removing deleted text:', comment.selected_text);
            parent.removeChild(highlight);
            
        } else if (comment.change_type === 'insert') {
            // Insert: Replace old text with new text
            console.log('✏️ Replacing text:', comment.original_text, '→', comment.new_text);
            const newTextNode = document.createTextNode(comment.new_text || comment.selected_text);
            parent.replaceChild(newTextNode, highlight);
            
        } else {
            // Regular comment: just remove highlight
            const text = highlight.textContent;
            parent.replaceChild(document.createTextNode(text), highlight);
        }
        
        // Delete comment from database
        const response = await fetch(`/api/contracts/comments/${commentId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Remove from array
            allComments = allComments.filter(c => c.id !== commentId);
            
            // Close bubble
            closeBubble();
            
            // Update UI
            updateCommentsPanel();
            updateCommentBadge();
            
            // Auto-save the contract with changes applied
            if (typeof saveAsDraft === 'function') {
                console.log('💾 Auto-saving contract with accepted changes...');
                saveAsDraft();
            }
            
            showNotification('Change accepted and applied', 'success');
        }
    } catch (error) {
        console.error('❌ Error accepting change:', error);
        showNotification('Failed to accept change', 'error');
    }
}

async function rejectChange(commentId) {
    console.log('❌ Rejecting change for comment:', commentId);
    
    const comment = allComments.find(c => c.id === commentId);
    if (!comment) {
        console.error('❌ Comment not found');
        return;
    }
    
    if (!confirm('Reject this change? The original text will remain unchanged.')) {
        return;
    }
    
    try {
        // Find the highlight element
        const highlight = document.querySelector(`[data-comment-id="${commentId}"]`);
        if (highlight) {
            // Remove highlight but keep original text
            const text = highlight.textContent;
            const parent = highlight.parentNode;
            parent.replaceChild(document.createTextNode(text), highlight);
        }
        
        // Delete comment from database
        const response = await fetch(`/api/contracts/comments/${commentId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Remove from array
            allComments = allComments.filter(c => c.id !== commentId);
            
            // Close bubble
            closeBubble();
            
            // Update UI
            updateCommentsPanel();
            updateCommentBadge();
            
            showNotification('Change rejected', 'info');
        }
    } catch (error) {
        console.error('❌ Error rejecting change:', error);
        showNotification('Failed to reject change', 'error');
    }
}

// =====================================================
// DELETE COMMENT
// =====================================================
async function deleteComment(commentId) {
    console.log('🗑️ Deleting comment:', commentId);
    
    if (!confirm('Delete this comment? The highlighted text will remain.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/contracts/comments/${commentId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        const data = await response.json();
        console.log('📥 Delete response:', data);
        
        if (data.success) {
            // Remove from array
            allComments = allComments.filter(c => c.id !== commentId);
            console.log('✅ Comment removed, remaining:', allComments.length);
            
            // Remove highlight
            const highlight = document.querySelector(`[data-comment-id="${commentId}"]`);
            if (highlight) {
                const text = highlight.textContent;
                const parent = highlight.parentNode;
                parent.replaceChild(document.createTextNode(text), highlight);
                console.log('✅ Highlight removed');
            }
            
            closeBubble();
            updateCommentsPanel();
            updateCommentBadge();
            
            showNotification('Comment deleted', 'success');
        }
    } catch (error) {
        console.error('❌ Error deleting comment:', error);
        showNotification('Failed to delete comment', 'error');
    }
}

// =====================================================
// COMMENTS PANEL
// =====================================================
function toggleCommentsPanel() {
    console.log('🎚️ Toggling comments panel');
    
    const panel = document.getElementById('commentsPanel');
    if (panel) {
        panel.classList.toggle('active');
        console.log('✅ Panel toggled, active:', panel.classList.contains('active'));
    } else {
        console.error('❌ commentsPanel not found');
    }
}

function updateCommentsPanel() {
    const panel = document.getElementById('commentsPanelBody');
    if (!panel) {
        console.warn('⚠️ commentsPanelBody not found');
        return;
    }
    
    console.log('📋 Updating comments panel with', allComments.length, 'comments');
    
    if (allComments.length === 0) {
        panel.innerHTML = `
            <div class="comments-empty">
                <i class="ti ti-message-off"></i>
                <p>No comments yet</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    allComments.forEach(comment => {
        const nameParts = comment.user_name.split(' ');
        const initials = nameParts.map(n => n[0]).join('').toUpperCase();
        const timeAgo = formatTimeAgo(new Date(comment.created_at));
        const typeClass = `${comment.change_type || 'comment'}-type`;
        
        html += `
            <div class="comment-item ${typeClass}" onclick="scrollToComment(${comment.id})" style="cursor: pointer;">
                <div class="comment-author" style="margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">
                    <div class="comment-author-avatar" style="width: 28px; height: 28px; font-size: 12px; background: var(--primary-color, #0066cc); color: white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 600;">${initials}</div>
                    <div class="comment-author-info">
                        <div class="comment-author-name" style="font-size: 13px; font-weight: 600; color: #2c3e50;">${escapeHtml(comment.user_name)}</div>
                        <div class="comment-time" style="font-size: 11px; color: #7f8c8d;">${timeAgo}</div>
                    </div>
                </div>
                <div class="comment-text" style="font-size: 13px; color: #34495e;">${escapeHtml(comment.comment_text)}</div>
            </div>
        `;
    });
    
    panel.innerHTML = html;
    console.log('✅ Panel updated with', allComments.length, 'comments');
}

function scrollToComment(commentId) {
    console.log('📜 Scrolling to comment:', commentId);
    
    const highlight = document.querySelector(`[data-comment-id="${commentId}"]`);
    if (highlight) {
        highlight.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // Pulse animation
        highlight.style.animation = 'none';
        setTimeout(() => {
            highlight.style.animation = 'pulse 0.5s ease 2';
        }, 10);
        
        console.log('✅ Scrolled to highlight');
    } else {
        console.warn('⚠️ Highlight not found for comment:', commentId);
    }
}

function updateCommentBadge() {
    const badges = document.querySelectorAll('#commentsBadge, #commentsBadge2');
    badges.forEach(badge => {
        if (badge) {
            badge.textContent = allComments.length;
            badge.style.display = allComments.length > 0 ? 'flex' : 'none';
        }
    });
    console.log('🔢 Badge updated:', allComments.length);
}

// =====================================================
// UTILITY FUNCTIONS
// =====================================================
function formatTimeAgo(date) {
    const seconds = Math.floor((new Date() - date) / 1000);
    
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    if (seconds < 604800) return `${Math.floor(seconds / 86400)}d ago`;
    
    return date.toLocaleDateString();
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function closeModal(modalId) {
    console.log('🔒 Closing modal:', modalId);
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
    }
}

// Add CSS for animations
if (!document.getElementById('bubble-animations')) {
    const style = document.createElement('style');
    style.id = 'bubble-animations';
    style.textContent = `
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(20px); }
            to { opacity: 1; transform: translateX(0); }
        }
        @keyframes slideOut {
            from { opacity: 1; transform: translateX(0); }
            to { opacity: 0; transform: translateX(20px); }
        }
        @keyframes pulse {
            0%, 100% { background: inherit; }
            50% { background: rgba(255, 193, 7, 0.6); }
        }
        @keyframes protectedFlash {
            0%, 100% { 
                box-shadow: none;
                transform: scale(1);
            }
            50% { 
                box-shadow: 0 0 0 4px rgba(220, 53, 69, 0.5);
                transform: scale(1.03);
            }
        }
    `;
    document.head.appendChild(style);
}

// =====================================================
// GLOBAL PROTECTION SYSTEM
// =====================================================

function initializeProtectionSystem() {
    console.log('🔒 Initializing text protection system...');
    
    const contractContent = document.getElementById('contractContent');
    if (!contractContent) {
        console.warn('⚠️ Contract content not found, protection not initialized');
        return;
    }
    
    // Monitor for selection changes in protected areas
    document.addEventListener('selectionchange', function() {
        const selection = window.getSelection();
        if (!selection.rangeCount) return;
        
        try {
            const range = selection.getRangeAt(0);
            const container = range.commonAncestorContainer;
            
            // Check if selection is inside or overlaps with protected element
            let node = container.nodeType === 3 ? container.parentNode : container;
            
            while (node && node !== contractContent) {
                if (node.dataset && node.dataset.protected === 'true') {
                    // Selection is in protected area
                    console.log('⚠️ Selection in protected area');
                    break;
                }
                node = node.parentNode;
            }
        } catch (e) {
            // Ignore errors
        }
    });
    
    // Prevent editing protected content at editor level
    contractContent.addEventListener('beforeinput', function(e) {
        const selection = window.getSelection();
        if (!selection.rangeCount) return;
        
        try {
            const range = selection.getRangeAt(0);
            const container = range.commonAncestorContainer;
            
            // Check if input is happening in protected area
            let node = container.nodeType === 3 ? container.parentNode : container;
            
            while (node && node !== contractContent) {
                if (node.dataset && node.dataset.protected === 'true') {
                    e.preventDefault();
                    e.stopPropagation();
                    
                    // Flash the protected element
                    node.style.animation = 'protectedFlash 0.4s ease 2';
                    setTimeout(() => {
                        node.style.animation = '';
                    }, 800);
                    
                    showNotification('⚠️ This text is protected by a comment. Resolve the comment before editing.', 'warning');
                    
                    console.log('🔒 Blocked edit attempt on protected text');
                    return false;
                }
                node = node.parentNode;
            }
        } catch (e) {
            console.error('Protection check error:', e);
        }
    }, true); // Use capture phase
    
    // Also prevent delete key on protected text
    contractContent.addEventListener('keydown', function(e) {
        if (e.key === 'Backspace' || e.key === 'Delete') {
            const selection = window.getSelection();
            if (!selection.rangeCount) return;
            
            try {
                const range = selection.getRangeAt(0);
                
                // Check if deleting will affect protected content
                const protectedElements = contractContent.querySelectorAll('[data-protected="true"]');
                
                for (let element of protectedElements) {
                    if (range.intersectsNode(element)) {
                        e.preventDefault();
                        e.stopPropagation();
                        
                        element.style.animation = 'protectedFlash 0.4s ease 2';
                        setTimeout(() => {
                            element.style.animation = '';
                        }, 800);
                        
                        showNotification('🔒 Cannot delete commented text. Resolve or delete the comment first.', 'warning');
                        
                        console.log('🔒 Blocked delete attempt on protected text');
                        return false;
                    }
                }
            } catch (e) {
                console.error('Delete protection error:', e);
            }
        }
    }, true);
    
    console.log('✅ Protection system initialized');
}

// Initialize protection after DOM loads
setTimeout(() => {
    initializeProtectionSystem();
}, 1000);

console.log('🎯 Bubble Comments JavaScript Loaded with Protection');