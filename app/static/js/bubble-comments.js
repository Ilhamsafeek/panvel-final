// =====================================================
// BUBBLE COMMENTS - CLEANED VERSION
// =====================================================

window.bcAllComments = [];
window.bcCurrentBubble = null;
window.bcContractId = null;
window.bcUserId = null;
window.bcIsHighlighting = false;
window.bcOriginalTexts = {}; // Track original texts for change detection

// =====================================================
// INITIALIZE
// =====================================================
document.addEventListener('DOMContentLoaded', function () {
    console.log('🚀 Bubble comments initializing...');

    window.bcContractId = contractId;
    window.bcUserId = getUserId();

    if (window.bcContractId) loadComments();

    setTimeout(function () {
        if (!window.bcContractId) {
            window.bcContractId = getContractId();
            if (window.bcContractId) loadComments();
        }
    }, 1500);

    waitForContractContent();

    // Close bubble when clicking outside
    document.addEventListener('click', function (e) {
        if (e.target.closest('.comment-icon')) return;
        if (e.target.closest('.comment-bubble, #commentBubble')) return;
        if (window.bcCurrentBubble) closeBubble();
    }, true);

    setupIconProtection();
});

function waitForContractContent() {
    var checkInterval = setInterval(function () {
        var content = document.getElementById('contractContent');
        if (content && content.innerHTML.length > 100) {
            clearInterval(checkInterval);
            if (window.bcAllComments.length > 0) {
                highlightCommentsInDocument();
            }
        }
    }, 500);
    setTimeout(function () { clearInterval(checkInterval); }, 30000);
}

function getUserId() {
    var el = document.getElementById('currentUserId');
    if (el) return parseInt(el.value || el.dataset.userId || 0);
    if (window.currentUserId) return window.currentUserId;
    return null;
}

// =====================================================
// ICON PROTECTION
// =====================================================
function setupIconProtection() {
    var content = document.getElementById('contractContent');
    if (!content) { setTimeout(setupIconProtection, 500); return; }

    function protectAllIcons() {
        content.querySelectorAll('.comment-icon').forEach(function (icon) {
            icon.setAttribute('contenteditable', 'false');
            icon.style.userSelect = 'none';
        });
    }
    protectAllIcons();

    // Prevent deletion of comment icons
    content.addEventListener('keydown', function (e) {
        if (e.key !== 'Backspace' && e.key !== 'Delete') return;
        
        var sel = window.getSelection();
        if (!sel.rangeCount) return;
        var range = sel.getRangeAt(0);

        // Check if selection contains comment icon
        if (!range.collapsed) {
            var container = document.createElement('div');
            container.appendChild(range.cloneContents());
            if (container.querySelector('.comment-icon')) {
                e.preventDefault();
                showNotification('Cannot delete comment icon', 'warning');
                return false;
            }
        }

        // Check adjacent nodes
        var node = range.startContainer;
        var offset = range.startOffset;

        if (e.key === 'Backspace' && range.collapsed) {
            if (node.nodeType === 3 && offset === 0) {
                var prev = node.previousSibling;
                if (prev && prev.classList && prev.classList.contains('comment-icon')) {
                    e.preventDefault();
                    return false;
                }
            }
        }

        if (e.key === 'Delete' && range.collapsed) {
            if (node.nodeType === 3 && offset === node.textContent.length) {
                var next = node.nextSibling;
                if (next && next.classList && next.classList.contains('comment-icon')) {
                    e.preventDefault();
                    return false;
                }
            }
        }
    }, true);

    // Monitor for removed icons and re-highlight
    var observer = new MutationObserver(function (mutations) {
        if (window.bcIsHighlighting) return;
        var iconRemoved = false;
        mutations.forEach(function (m) {
            m.removedNodes.forEach(function (node) {
                if (node.classList && node.classList.contains('comment-icon')) iconRemoved = true;
                if (node.querySelector && node.querySelector('.comment-icon')) iconRemoved = true;
            });
        });
        if (iconRemoved && window.bcAllComments.length > 0) {
            setTimeout(highlightCommentsInDocument, 150);
        }
    });
    observer.observe(content, { childList: true, subtree: true });
}

// =====================================================
// LOAD COMMENTS
// =====================================================
function loadComments() {
    if (!window.bcContractId) window.bcContractId = getContractId();
    if (!window.bcContractId) return;

    fetch('/api/contracts/comments/' + window.bcContractId, { credentials: 'include' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.success) {
                window.bcAllComments = data.comments || [];
                if (data.current_user_id) window.bcUserId = data.current_user_id;
                console.log('📥 Loaded', window.bcAllComments.length, 'comments');

                var content = document.getElementById('contractContent');
                if (content && content.innerHTML.length > 100) {
                    highlightCommentsInDocument();
                }
                updateCommentsPanel();
                updateCommentBadge();
            }
            
            // Store original texts for tracking
            window.bcAllComments.forEach(function(c) {
                if (!window.bcOriginalTexts[c.id]) {
                    window.bcOriginalTexts[c.id] = c.original_text || c.selected_text;
                }
            });
        })
        .catch(function (err) { console.error('Load error:', err); });
}

// =====================================================
// HIGHLIGHT COMMENTS
// =====================================================
function highlightCommentsInDocument() {
    var content = document.getElementById('contractContent');
    if (!content || content.innerHTML.length < 100) return;

    window.bcIsHighlighting = true;
    console.log('🎨 Highlighting', window.bcAllComments.length, 'comments...');

    // Remove existing highlights
    content.querySelectorAll('.comment-highlight, .track-insert, .track-delete, .comment-icon').forEach(function (el) {
        if (el.classList.contains('comment-icon')) {
            el.remove();
        } else {
            var parent = el.parentNode;
            while (el.firstChild) parent.insertBefore(el.firstChild, el);
            parent.removeChild(el);
        }
    });
    content.normalize();

    // Sort by position descending (process from end to start)
    var sortedComments = window.bcAllComments.slice().sort(function (a, b) {
        return (b.position_start || 0) - (a.position_start || 0);
    });

    var successCount = 0;
    sortedComments.forEach(function (comment) {
        if (highlightComment(content, comment)) successCount++;
    });

    console.log('✅ Highlighted', successCount, '/', window.bcAllComments.length, 'comments');

    setTimeout(function () { window.bcIsHighlighting = false; }, 300);
}

/**
 * NEW: Highlight comment using robust anchor
 * Highlight persists even if text changes - only removed when comment deleted
 */
function highlightCommentByAnchor(container, comment, className) {
    if (!comment.anchor) {
        // Fallback to old method for legacy comments
        console.log('⚠️ No anchor, using fallback');
        return highlightComment(container, comment);
    }
    
    // Find position using anchor (ALWAYS finds something)
    var result = window.PositionTracker.findFromAnchor(container, comment.anchor);
    
    if (!result || !result.range) {
        console.log('❌ Could not find comment', comment.id, 'from anchor (should be rare)');
        return false;
    }
    
    try {
        var wrapper = document.createElement('span');
        wrapper.className = className || 'comment-highlight';
        wrapper.dataset.commentId = comment.id;
        
        // If text was modified, add visual indicator
        if (result.modified) {
            wrapper.classList.add('comment-modified');
            // wrapper.title = 'Comment text has been edited. Original: "' + comment.anchor.text + '"';
            console.log('🔄 Comment', comment.id, 'text modified - highlighting current text');
        }
        
        var contents = result.range.extractContents();
        wrapper.appendChild(contents);
        wrapper.appendChild(createCommentIcon(comment.id));
        result.range.insertNode(wrapper);
        
        // Update comment with current text if modified
        if (result.modified && result.currentText) {
            comment._currentText = result.currentText;
        }
        
        return true;
    } catch (e) {
        console.error('Error wrapping comment:', e);
        return false;
    }
}

/**
 * Check if commented text still exists at the exact position
 * Returns: true if valid, 'search_new' if should search by new text, 'skip' if skip
 */
function isCommentStillValid(container, comment) {
    if (!comment.position_start || !comment.selected_text) return true;
    
    // Get current full text
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    var fullText = '';
    var node;
    
    while (node = walker.nextNode()) {
        var parent = node.parentElement;
        if (parent && (
            parent.classList.contains('comment-highlight') ||
            parent.classList.contains('track-insert') ||
            parent.classList.contains('track-delete') ||
            parent.classList.contains('comment-icon')
        )) continue;
        fullText += node.textContent;
    }
    
    // Check if text at recorded position matches the ORIGINAL text
    var textAtPosition = fullText.substring(
        comment.position_start, 
        comment.position_start + comment.selected_text.length
    );
    
    if (textAtPosition === comment.selected_text) {
        return true; // Original text still there - highlight normally
    }
    
    // Text at position doesn't match original
    console.log('⚠️ Position text changed for comment', comment.id);
    
    // If this is a tracked change with new_text, search for the NEW text
    if (comment.change_type === 'insert' && comment.new_text) {
        console.log('   → Has new_text, searching for:', comment.new_text);
        return 'search_new';
    }
    
    // Check if new text exists in document (user edited but not saved yet)
    var newTextAtPosition = fullText.substring(
        comment.position_start,
        comment.position_start + textAtPosition.length
    );
    
    if (newTextAtPosition && newTextAtPosition.length > 0) {
        console.log('   → Found edited text at position:', newTextAtPosition);
        // Temporarily store for highlighting
        comment._tempNewText = newTextAtPosition;
        return 'search_temp';
    }
    
    // For duplicate text scenarios - only skip if it's truly a different occurrence
    var allOccurrences = fullText.split(comment.selected_text).length - 1;
    if (allOccurrences > 1) {
        console.log('   → Duplicate text exists, checking if this is wrong occurrence');
        return 'skip'; // Skip to avoid highlighting wrong duplicate
    }
    
    return true; // Fall back to normal search
}

function highlightComment(container, comment) {
    var className = comment.change_type === 'insert' ? 'track-insert' : 
                    comment.change_type === 'delete' ? 'track-delete' : 'comment-highlight';
    var text = comment.selected_text;
    if (!text) return false;

    // Already highlighted?
    if (container.querySelector('[data-comment-id="' + comment.id + '"]')) return true;

    // **NEW: Try anchor-based highlighting first**
    if (comment.anchor) {
        return highlightCommentByAnchor(container, comment, className);
    }

    // **FALLBACK: Old validation for legacy comments**
    var validStatus = isCommentStillValid(container, comment);
    
    if (validStatus === 'search_new') {
        // Text was tracked as changed - search for the NEW text
        console.log('🔍 Highlighting new text:', comment.new_text);
        return findAndWrapByText(container, comment.new_text, comment.id, className);
    }
    
    if (validStatus === 'search_temp') {
        // Text was edited but not saved - highlight at position
        console.log('🔍 Highlighting temporarily edited text');
        return findAndWrapByPosition(container, comment._tempNewText, comment.id, className, comment.position_start);
    }
    
    if (validStatus === 'skip') {
        console.log('⏭️ Skipping duplicate text comment', comment.id);
        return false;
    }

    // Try position-based search
    if (typeof comment.position_start === 'number' && comment.position_start >= 0) {
        if (findAndWrapByPosition(container, text, comment.id, className, comment.position_start)) {
            return true;
        }
    }

    // Last resort: text-based search
    return findAndWrapByText(container, text, comment.id, className);
}

// =====================================================
// POSITION-BASED SEARCH
// =====================================================
function findAndWrapByPosition(container, searchText, commentId, className, targetPosition) {
    var textNodes = [];
    var fullText = '';
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    var node;

    // Build text nodes array
    while (node = walker.nextNode()) {
        var parent = node.parentElement;
        if (parent && (
            parent.classList.contains('comment-highlight') ||
            parent.classList.contains('track-insert') ||
            parent.classList.contains('track-delete') ||
            parent.classList.contains('comment-icon')
        )) continue;

        textNodes.push({ node: node, start: fullText.length, end: fullText.length + node.textContent.length });
        fullText += node.textContent;
    }

    // Verify text at position
    var expectedText = fullText.substring(targetPosition, targetPosition + searchText.length);
    if (expectedText !== searchText) {
        console.log('⚠️ Position mismatch for comment', commentId);
        return false;
    }

    // Find nodes containing the target range
    var matchEnd = targetPosition + searchText.length;
    var startNode = null, startOffset = 0, endNode = null, endOffset = 0;

    for (var i = 0; i < textNodes.length; i++) {
        var tn = textNodes[i];
        if (!startNode && targetPosition >= tn.start && targetPosition < tn.end) {
            startNode = tn.node;
            startOffset = targetPosition - tn.start;
        }
        if (matchEnd > tn.start && matchEnd <= tn.end) {
            endNode = tn.node;
            endOffset = matchEnd - tn.start;
            break;
        }
    }

    if (!startNode || !endNode) return false;

    try {
        var range = document.createRange();
        range.setStart(startNode, Math.min(startOffset, startNode.textContent.length));
        range.setEnd(endNode, Math.min(endOffset, endNode.textContent.length));

        var wrapper = document.createElement('span');
        wrapper.className = className;
        wrapper.dataset.commentId = commentId;

        var contents = range.extractContents();
        wrapper.appendChild(contents);
        wrapper.appendChild(createCommentIcon(commentId));
        range.insertNode(wrapper);
        return true;
    } catch (e) {
        console.error('Wrap error:', e);
        return false;
    }
}

// =====================================================
// TEXT-BASED SEARCH (FALLBACK)
// =====================================================
function findAndWrapByText(container, searchText, commentId, className) {
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    var node;

    while (node = walker.nextNode()) {
        var parent = node.parentElement;
        if (parent && (
            parent.classList.contains('comment-highlight') ||
            parent.classList.contains('track-insert') ||
            parent.classList.contains('track-delete')
        )) continue;

        var idx = node.textContent.indexOf(searchText);
        if (idx !== -1) {
            try {
                var range = document.createRange();
                range.setStart(node, idx);
                range.setEnd(node, idx + searchText.length);

                var wrapper = document.createElement('span');
                wrapper.className = className;
                wrapper.dataset.commentId = commentId;

                var contents = range.extractContents();
                wrapper.appendChild(contents);
                wrapper.appendChild(createCommentIcon(commentId));
                range.insertNode(wrapper);
                return true;
            } catch (e) { 
                continue; 
            }
        }
    }
    return false;
}

// =====================================================
// CREATE COMMENT ICON
// =====================================================
function createCommentIcon(commentId) {
    var icon = document.createElement('span');
    icon.className = 'comment-icon';
    icon.dataset.commentId = commentId;
    icon.innerHTML = '<i class="ti ti-message-circle-filled"></i>';
    icon.title = 'Click to view comment';
    icon.contentEditable = 'false';
    icon.setAttribute('contenteditable', 'false');
    icon.style.cssText = 'display:inline-flex !important;align-items:center;justify-content:center;width:18px;height:18px;margin-left:2px;background:linear-gradient(135deg,#ffc107,#ff9800);color:#000;border-radius:50%;font-size:10px;cursor:pointer;vertical-align:middle;user-select:none !important;box-shadow:0 2px 4px rgba(0,0,0,0.2);z-index:100;';

    icon.onclick = function (e) { 
        e.preventDefault(); 
        e.stopPropagation(); 
        showBubble(parseInt(commentId), e); 
        return false; 
    };
    
    return icon;
}

// =====================================================
// ADD COMMENT
// =====================================================
function openAddCommentModal() {
    var sel = window.getSelection();
    if (!sel.rangeCount || !sel.toString().trim()) {
        showNotification('Select text first', 'warning');
        return;
    }

    var text = sel.toString().trim();
    var range = sel.getRangeAt(0);
    var content = document.getElementById('contractContent');

    // **NEW: Create robust anchor instead of fragile position**
    var anchor = window.PositionTracker.createAnchor(content, range);
    
    console.log('📍 Created anchor:', anchor.fingerprint);

    window.commentSelection = { 
        text: text,
        anchor: anchor,  // ← NEW: Store anchor
        // Keep old format for backward compatibility
        absoluteStart: anchor.absolutePos, 
        absoluteEnd: anchor.absolutePos + text.length 
    };

    var modal = document.getElementById('commentModal');
    if (modal) {
        modal.style.display = 'flex';
        var ta = document.getElementById('commentText');
        if (ta) { 
            ta.value = ''; 
            setTimeout(function () { ta.focus(); }, 100); 
        }
        var prev = document.getElementById('selectedTextPreview');
        if (prev) prev.textContent = text.length > 200 ? text.substring(0, 200) + '...' : text;
        var newTextEl = document.getElementById('newText');
        if (newTextEl) newTextEl.value = '';
    }
}

function submitComment() {
    var ta = document.getElementById('commentText');
    var commentText = ta ? ta.value.trim() : '';

    if (!commentText) { 
        showNotification('Enter a comment', 'warning'); 
        return; 
    }
    if (!window.commentSelection || !window.commentSelection.text) { 
        showNotification('No text selected', 'warning'); 
        return; 
    }
    if (!window.bcContractId) window.bcContractId = getContractId();
    if (!window.bcContractId) { 
        showNotification('No contract ID', 'error'); 
        return; 
    }

    var typeEl = document.querySelector('input[name="changeType"]:checked');
    var changeType = typeEl ? typeEl.value : 'comment';
    var newEl = document.getElementById('newText');
    var newText = newEl ? newEl.value.trim() : null;

    if (changeType === 'insert' && !newText) {
        showNotification('Enter new text for modification', 'warning');
        return;
    }

    var selectedText = window.commentSelection.text;
    var anchor = window.commentSelection.anchor;  // ← NEW

    fetch('/api/contracts/comments/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
            contract_id: parseInt(window.bcContractId),
            comment_text: commentText,
            selected_text: selectedText,
            anchor: anchor,  // ← NEW: Send anchor instead of just position
            position_start: anchor ? anchor.absolutePos : 0,  // Backward compatibility
            position_end: anchor ? (anchor.absolutePos + selectedText.length) : 0,
            start_xpath: '',
            change_type: changeType,
            original_text: selectedText,
            new_text: newText
        })
    })
    .then(function (r) { return r.json(); })
    .then(function (d) {
        if (d.success && d.comment) {
            var newComment = d.comment;
            newComment.anchor = anchor;  // ← Store anchor locally
            newComment.position_start = anchor ? anchor.absolutePos : 0;
            newComment.position_end = anchor ? (anchor.absolutePos + selectedText.length) : 0;
            window.bcAllComments.push(newComment);

            closeModal('commentModal');
            window.getSelection().removeAllRanges();

            // Highlight the new comment
            var content = document.getElementById('contractContent');
            var className = changeType === 'insert' ? 'track-insert' : 
                          changeType === 'delete' ? 'track-delete' : 'comment-highlight';

            window.bcIsHighlighting = true;
            highlightCommentByAnchor(content, newComment, className);  // ← NEW function
            setTimeout(function () { window.bcIsHighlighting = false; }, 300);

            updateCommentsPanel();
            updateCommentBadge();
            showNotification('Comment added', 'success');
            window.commentSelection = null;
            
            // Store original text for change tracking
            window.bcOriginalTexts[newComment.id] = selectedText;
        } else {
            showNotification('Failed to add comment', 'error');
        }
    })
    .catch(function (e) { 
        console.error('Submit error:', e); 
        showNotification('Error adding comment', 'error'); 
    });
}

// =====================================================
// SHOW BUBBLE
// =====================================================

// Find the showBubble function in app/static/js/bubble-comments.js
// Update the modifiedWarning section (around line 190-200)

function showBubble(commentId, event) {
    var comment = findComment(commentId);
    if (!comment) return;
    closeBubble();

    var isOwner = (comment.user_id == window.bcUserId);
    var isChange = comment.change_type && comment.change_type !== 'comment';

    var bubble = document.createElement('div');
    bubble.id = 'commentBubble';
    bubble.style.cssText = 'position:fixed;background:white;border:2px solid #ffc107;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,0.25);min-width:320px;max-width:420px;z-index:99999;';

    var name = comment.user_name || 'User';
    var initials = name.split(' ').map(function (n) { return n[0]; }).join('').toUpperCase().substring(0, 2);

    var actions = '';
    if (isOwner) {
        actions = '<button onclick="deleteComment(' + comment.id + ')" style="width:32px;height:32px;border:none;border-radius:8px;background:#fee2e2;color:#dc3545;cursor:pointer;display:flex;align-items:center;justify-content:center;" title="Delete"><i class="ti ti-trash"></i></button>';
    } else {
        if (isChange) {
            actions += '<button onclick="acceptChange(' + comment.id + ')" style="width:32px;height:32px;border:none;border-radius:8px;background:#d1fae5;color:#28a745;cursor:pointer;display:flex;align-items:center;justify-content:center;margin-right:4px;" title="Accept"><i class="ti ti-check"></i></button>';
            actions += '<button onclick="rejectChange(' + comment.id + ')" style="width:32px;height:32px;border:none;border-radius:8px;background:#fee2e2;color:#dc3545;cursor:pointer;display:flex;align-items:center;justify-content:center;margin-right:4px;" title="Reject"><i class="ti ti-x"></i></button>';
        }
        actions += '<button onclick="resolveComment(' + comment.id + ')" style="width:32px;height:32px;border:none;border-radius:8px;background:#dbeafe;color:#3b82f6;cursor:pointer;display:flex;align-items:center;justify-content:center;" title="Resolve"><i class="ti ti-circle-check"></i></button>';
    }

    var details = '';
    
    // Show if text has been modified - UPDATED TEXT
    var modifiedWarning = '';
    if (comment._currentText && comment._currentText !== comment.selected_text) {
        modifiedWarning = '<div style="margin-top:10px;padding:10px;background:#fff3cd;border-left:3px solid #ff9800;border-radius:6px;"><div style="color:#ff9800;font-weight:600;font-size:12px;margin-bottom:6px;">⚠️ Text Modified</div><div style="font-size:12px;color:#856404;">Comment text has been edited. Original: [' + escapeHtml(comment.selected_text) + ']</div></div>';
    }
    
    if (comment.change_type === 'delete') {
        details = '<div style="margin-top:10px;padding:10px;background:#f8f9fa;border-radius:8px;"><div style="color:#dc3545;font-weight:600;font-size:12px;margin-bottom:6px;">🗑️ Delete:</div><div style="padding:8px;background:#fee2e2;border-radius:6px;color:#991b1b;text-decoration:line-through;max-height:100px;overflow:auto;">' + escapeHtml(comment.selected_text) + '</div></div>';
    } else if (comment.change_type === 'insert') {
        details = '<div style="margin-top:10px;padding:10px;background:#f8f9fa;border-radius:8px;"><div style="color:#6c757d;font-weight:600;font-size:12px;margin-bottom:6px;">✏️ Change:</div><div style="padding:8px;background:#fee2e2;border-radius:6px;color:#991b1b;text-decoration:line-through;margin-bottom:6px;max-height:60px;overflow:auto;">' + escapeHtml(comment.original_text || comment.selected_text) + '</div><div style="text-align:center;">↓</div><div style="padding:8px;background:#d1fae5;border-radius:6px;color:#166534;max-height:60px;overflow:auto;">' + escapeHtml(comment.new_text) + '</div></div>';
    }

    var badge = comment.change_type === 'delete' ? 'background:#fee2e2;color:#991b1b' : 
                comment.change_type === 'insert' ? 'background:#d1fae5;color:#166534' : 
                'background:#fff3cd;color:#856404';
    var label = comment.change_type === 'delete' ? '🗑️ Deletion' : 
                comment.change_type === 'insert' ? '✏️ Modification' : '💬 Comment';

    bubble.innerHTML =
        '<div style="padding:12px;background:linear-gradient(135deg,#fff9e6,#fff3cd);border-radius:10px 10px 0 0;display:flex;justify-content:space-between;align-items:center;">' +
        '<div style="display:flex;align-items:center;gap:10px;"><div style="width:36px;height:36px;background:linear-gradient(135deg,#ffc107,#ff9800);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;">' + initials + '</div><div style="font-weight:600;">' + escapeHtml(name) + '</div></div>' +
        '<div style="display:flex;gap:4px;">' + actions + '</div>' +
        '</div>' +
        '<div style="padding:15px;max-height:300px;overflow:auto;"><div style="color:#333;line-height:1.6;">' + escapeHtml(comment.comment_text) + '</div>' + modifiedWarning + details + '</div>' +
        '<div style="padding:10px 15px;background:#f8f9fa;border-radius:0 0 10px 10px;display:flex;gap:10px;">' +
        '<span style="font-size:11px;padding:4px 10px;border-radius:20px;' + badge + ';font-weight:600;">' + label + '</span>' +
        (isOwner ? '<span style="font-size:11px;padding:4px 10px;border-radius:20px;background:#e0e7ff;color:#4338ca;">Your comment</span>' : '') +
        '</div>';

    document.body.appendChild(bubble);
    window.bcCurrentBubble = bubble;

    // Position bubble
    var rect = event && event.target ? event.target.getBoundingClientRect() : { bottom: 200, left: 200, top: 180 };
    var top = rect.bottom + 10, left = rect.left;
    if (left + 350 > window.innerWidth) left = window.innerWidth - 370;
    if (top + 300 > window.innerHeight) top = rect.top - 310;
    bubble.style.top = Math.max(10, top) + 'px';
    bubble.style.left = Math.max(10, left) + 'px';
    bubble.onclick = function (e) { e.stopPropagation(); };
}

function closeBubble() {
    if (window.bcCurrentBubble) { 
        window.bcCurrentBubble.remove(); 
        window.bcCurrentBubble = null; 
    }
    document.querySelectorAll('#commentBubble').forEach(function (b) { b.remove(); });
}

// =====================================================
// ACTIONS
// =====================================================
function deleteComment(id) {
    var c = findComment(id);
    if (!c) return;
    if (c.user_id != window.bcUserId) { 
        showNotification('You can only delete your own comments', 'warning'); 
        return; 
    }
    if (!confirm('Delete this comment?')) return;
    
    removeHighlight(id);
    deleteFromDB(id);
    showNotification('Comment deleted', 'success');
}

function acceptChange(id) {
    var c = findComment(id);
    if (!c) return;
    if (c.user_id == window.bcUserId) { 
        showNotification('Cannot accept your own change', 'warning'); 
        return; 
    }
    if (!confirm('Accept this change?')) return;

    window.bcIsHighlighting = true;
    var el = document.querySelector('[data-comment-id="' + id + '"]');
    if (el && !el.classList.contains('comment-icon')) {
        var p = el.parentNode;
        var icon = el.querySelector('.comment-icon');
        if (icon) icon.remove();
        
        if (c.change_type === 'delete') {
            p.removeChild(el);
        } else if (c.change_type === 'insert' && c.new_text) {
            p.replaceChild(document.createTextNode(c.new_text), el);
        } else {
            while (el.firstChild) p.insertBefore(el.firstChild, el);
            p.removeChild(el);
        }
        p.normalize();
    }
    setTimeout(function () { window.bcIsHighlighting = false; }, 200);
    
    deleteFromDB(id);
    if (typeof saveAsDraft === 'function') saveAsDraft();
    showNotification('Change accepted', 'success');
}

function rejectChange(id) {
    var c = findComment(id);
    if (!c) return;
    if (c.user_id == window.bcUserId) { 
        showNotification('Cannot reject your own change', 'warning'); 
        return; 
    }
    if (!confirm('Reject this change?')) return;
    
    removeHighlight(id);
    deleteFromDB(id);
    showNotification('Change rejected', 'info');
}

function resolveComment(id) {
    var c = findComment(id);
    if (!c) return;
    if (c.user_id == window.bcUserId) { 
        showNotification('Cannot resolve your own comment', 'warning'); 
        return; 
    }
    if (!confirm('Mark as resolved?')) return;
    
    removeHighlight(id);
    deleteFromDB(id);
    showNotification('Comment resolved', 'success');
}

function removeHighlight(id) {
    window.bcIsHighlighting = true;
    var el = document.querySelector('[data-comment-id="' + id + '"]');
    if (el && el.classList.contains('comment-icon')) {
        el = el.closest('.comment-highlight, .track-insert, .track-delete');
    }
    if (el) {
        var p = el.parentNode;
        var icon = el.querySelector('.comment-icon');
        if (icon) icon.remove();
        while (el.firstChild) p.insertBefore(el.firstChild, el);
        p.removeChild(el);
        p.normalize();
    }
    setTimeout(function () { window.bcIsHighlighting = false; }, 200);
}

function deleteFromDB(id) {
    fetch('/api/contracts/comments/' + id, { 
        method: 'DELETE', 
        credentials: 'include' 
    })
    .then(function (r) { return r.json(); })
    .then(function (d) {
        if (d.success) {
            window.bcAllComments = window.bcAllComments.filter(function (c) { 
                return c.id != id; 
            });
            closeBubble();
            updateCommentsPanel();
            updateCommentBadge();
        }
    });
}

function findComment(id) {
    for (var i = 0; i < window.bcAllComments.length; i++) {
        if (window.bcAllComments[i].id == id) return window.bcAllComments[i];
    }
    return null;
}

// =====================================================
// UI UPDATES
// =====================================================
function toggleCommentsPanel() {
    var p = document.getElementById('commentsPanel');
    if (p) {
        var isVisible = p.style.display === 'flex';
        p.style.display = isVisible ? 'none' : 'flex';
        if (!isVisible) loadComments();
    }
}

function updateCommentsPanel() {
    var p = document.getElementById('commentsPanelBody') || document.getElementById('commentsListContainer');
    if (!p) return;

    if (window.bcAllComments.length === 0) {
        p.innerHTML = '<div style="text-align:center;padding:40px;color:#999;"><i class="ti ti-message-off" style="font-size:40px;display:block;margin-bottom:10px;"></i>No comments</div>';
        return;
    }

    var h = '';
    window.bcAllComments.forEach(function (c) {
        var initials = (c.user_name || 'User').split(' ').map(function (n) { return n[0]; }).join('').toUpperCase().substring(0, 2);
        var isOwner = c.user_id == window.bcUserId;

        var changeDisplay = '';
        if (c.change_type === 'insert' && c.original_text && c.new_text) {
            changeDisplay = '<div style="margin-top:10px;padding:10px;background:#f8f9fa;border-radius:6px;"><div style="font-size:11px;color:#dc3545;margin-bottom:4px;">Before:</div><div style="text-decoration:line-through;color:#dc3545;font-size:13px;">' + escapeHtml(c.original_text) + '</div><div style="font-size:11px;color:#28a745;margin:8px 0 4px;">After:</div><div style="color:#28a745;font-size:13px;">' + escapeHtml(c.new_text) + '</div></div>';
        } else if (c.change_type === 'delete' && c.original_text) {
            changeDisplay = '<div style="margin-top:10px;padding:10px;background:#f8f9fa;border-radius:6px;"><div style="text-decoration:line-through;color:#dc3545;">' + escapeHtml(c.original_text) + '</div></div>';
        }

        h += '<div style="padding:15px;border-bottom:1px solid #e0e0e0;">';
        h += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">';
        h += '<div style="display:flex;align-items:center;gap:10px;">';
        h += '<div style="width:36px;height:36px;border-radius:50%;background:linear-gradient(135deg,#667eea,#764ba2);display:flex;align-items:center;justify-content:center;color:white;font-weight:600;">' + initials + '</div>';
        h += '<div style="font-weight:600;">' + escapeHtml(c.user_name) + '</div>';
        h += '</div>';
        if (isOwner) {
            h += '<button onclick="deleteComment(' + c.id + ')" style="background:none;border:none;color:#dc3545;cursor:pointer;" title="Delete"><i class="ti ti-trash"></i></button>';
        }
        h += '</div>';
        h += '<div style="color:#444;margin-bottom:4px;">' + escapeHtml(c.comment_text) + '</div>';
        h += changeDisplay;
        h += '</div>';
    });

    p.innerHTML = h;
}

function updateCommentBadge() {
    document.querySelectorAll('#commentsBadge, #commentsBadge2, .comment-badge').forEach(function (b) {
        b.textContent = window.bcAllComments.length;
        b.style.display = window.bcAllComments.length > 0 ? 'flex' : 'none';
    });
}

// =====================================================
// HELPERS
// =====================================================
function escapeHtml(t) { 
    if (!t) return ''; 
    var d = document.createElement('div'); 
    d.textContent = t; 
    return d.innerHTML; 
}

function closeModal(id) { 
    var m = document.getElementById(id); 
    if (m) m.style.display = 'none'; 
}

function scrollToComment(id) { 
    var el = document.querySelector('[data-comment-id="' + id + '"]'); 
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); 
}

// =====================================================
// EXPOSE GLOBALLY
// =====================================================
window.toggleCommentsPanel = toggleCommentsPanel;
window.openAddCommentModal = openAddCommentModal;
window.submitComment = submitComment;
window.deleteComment = deleteComment;
window.acceptChange = acceptChange;
window.rejectChange = rejectChange;
window.resolveComment = resolveComment;
window.closeBubble = closeBubble;
window.closeModal = closeModal;
window.scrollToComment = scrollToComment;
window.showBubble = showBubble;
window.loadComments = loadComments;
window.highlightCommentsInDocument = highlightCommentsInDocument;

console.log('✅ Bubble comments loaded');

// =====================================================
// TRACK CHANGES - Detect when user edits commented text
// =====================================================

/**
 * Check all comments for text changes and track them
 */
function checkForChanges() {
    var content = document.getElementById('contractContent');
    if (!content || window.bcIsHighlighting) return;
    
    var highlights = content.querySelectorAll('[data-comment-id]');
    if (highlights.length === 0) return;
    
    var changesDetected = 0;
    
    highlights.forEach(function(highlight) {
        var commentId = parseInt(highlight.dataset.commentId);
        if (!commentId) return;
        
        var comment = findComment(commentId);
        if (!comment) return;
        
        // Skip if already tracked as a change
        if (comment.change_type === 'insert' && comment.new_text) return;
        
        // Get current text in the highlight
        var icon = highlight.querySelector('.comment-icon');
        var currentText = highlight.textContent;
        if (icon) {
            currentText = currentText.replace('💬', '').replace(/\s+/g, ' ').trim();
        }
        
        // Get original text
        var originalText = window.bcOriginalTexts[commentId];
        if (!originalText) return;
        
        // Compare
        var cleanOriginal = originalText.replace(/\s+/g, ' ').trim();
        var cleanCurrent = currentText.replace(/\s+/g, ' ').trim();
        
        if (cleanCurrent !== cleanOriginal && cleanCurrent.length > 0) {
            console.log('🎯 Change detected on comment', commentId);
            console.log('   Before:', cleanOriginal);
            console.log('   After:', cleanCurrent);
            
            changesDetected++;
            trackChange(commentId, cleanOriginal, cleanCurrent);
        }
    });
    
    if (changesDetected > 0) {
        console.log('✅ Tracked', changesDetected, 'change(s)');
        setTimeout(function() { loadComments(); }, 500);
    }
}

/**
 * Track a change via API
 */
function trackChange(commentId, originalText, newText) {
    fetch('/api/contracts/comments/' + commentId + '/track-change', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
            original_text: originalText,
            new_text: newText,
            change_type: 'insert'
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            console.log('✅ Tracked change for comment', commentId);
            var comment = findComment(commentId);
            if (comment) {
                comment.change_type = 'insert';
                comment.original_text = originalText;
                comment.new_text = newText;
            }
            window.bcOriginalTexts[commentId] = newText;
        }
    })
    .catch(function(err) {
        console.error('Error tracking change:', err);
    });
}

/**
 * Manual button to check for changes
 */
function manualCheckChanges() {
    checkForChanges();
    showNotification('Checked for changes', 'info');
}

// Check for changes when user stops editing
document.addEventListener('DOMContentLoaded', function() {
    var content = document.getElementById('contractContent');
    if (content) {
        var changeTimeout;
        content.addEventListener('input', function() {
            clearTimeout(changeTimeout);
            changeTimeout = setTimeout(function() {
                checkForChanges();
            }, 2000); // Check 2 seconds after user stops typing
        });
    }
});

window.checkForChanges = checkForChanges;
window.manualCheckChanges = manualCheckChanges;

console.log('✅ Track changes loaded');