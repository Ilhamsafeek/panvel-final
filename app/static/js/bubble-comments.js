// =====================================================
// BUBBLE COMMENTS - WITH DUPLICATE TEXT SUPPORT
// Handles same text appearing multiple times
// =====================================================

window.bcAllComments = [];
window.bcCurrentBubble = null;
window.bcContractId = null;
window.bcUserId = null;
window.bcLoaded = false;
window.bcHighlighted = false;
window.bcIsHighlighting = false;

// =====================================================
// INITIALIZE
// =====================================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Bubble comments initializing...');
    
    window.bcContractId = getContractId();
    window.bcUserId = getUserId();
    
    if (window.bcContractId) loadComments();
    
    setTimeout(function() {
        if (!window.bcContractId) {
            window.bcContractId = getContractId();
            if (window.bcContractId && !window.bcLoaded) loadComments();
        }
    }, 1500);
    
    waitForContractContent();
    
    document.addEventListener('click', function(e) {
        if (e.target.closest('.comment-icon')) return;
        if (e.target.closest('.comment-bubble')) return;
        if (e.target.closest('#commentBubble')) return;
        if (window.bcCurrentBubble) closeBubble();
    }, true);
    
    setupStrongIconProtection();
});

function waitForContractContent() {
    var checkInterval = setInterval(function() {
        var content = document.getElementById('contractContent');
        if (content && content.innerHTML.length > 100) {
            clearInterval(checkInterval);
            if (window.bcAllComments.length > 0 && !window.bcHighlighted) {
                setTimeout(highlightCommentsInDocument, 500);
            }
        }
    }, 500);
    setTimeout(function() { clearInterval(checkInterval); }, 30000);
}

// =====================================================
// ICON PROTECTION
// =====================================================
function setupStrongIconProtection() {
    var content = document.getElementById('contractContent');
    if (!content) { setTimeout(setupStrongIconProtection, 500); return; }

    function protectAllIcons() {
        content.querySelectorAll('.comment-icon').forEach(function(icon) {
            icon.setAttribute('contenteditable', 'false');
            icon.style.userSelect = 'none';
            icon.setAttribute('data-protected', 'true');
        });
    }
    protectAllIcons();

    content.addEventListener('keydown', function(e) {
        if (e.key !== 'Backspace' && e.key !== 'Delete') return;
        var sel = window.getSelection();
        if (!sel.rangeCount) return;
        var range = sel.getRangeAt(0);
        
        if (!range.collapsed) {
            var container = document.createElement('div');
            container.appendChild(range.cloneContents());
            if (container.querySelector('.comment-icon')) {
                e.preventDefault();
                e.stopImmediatePropagation();
                showNotification('⚠️ Cannot delete comment icon.', 'warning');
                range.collapse(false);
                return false;
            }
        }
        
        var node = range.startContainer;
        var offset = range.startOffset;
        
        if (e.key === 'Backspace' && range.collapsed) {
            if (node.nodeType === 3 && offset === 0) {
                var prev = node.previousSibling;
                if (prev && prev.classList && prev.classList.contains('comment-icon')) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    return false;
                }
            }
            if (node.nodeType === 1 && offset > 0) {
                var prevChild = node.childNodes[offset - 1];
                if (prevChild && prevChild.classList && prevChild.classList.contains('comment-icon')) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    return false;
                }
            }
        }
        
        if (e.key === 'Delete' && range.collapsed) {
            if (node.nodeType === 3 && offset === node.textContent.length) {
                var next = node.nextSibling;
                if (next && next.classList && next.classList.contains('comment-icon')) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    return false;
                }
            }
            if (node.nodeType === 1 && offset < node.childNodes.length) {
                var nextChild = node.childNodes[offset];
                if (nextChild && nextChild.classList && nextChild.classList.contains('comment-icon')) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    return false;
                }
            }
        }
    }, true);

    content.addEventListener('cut', function(e) {
        var sel = window.getSelection();
        if (sel.rangeCount) {
            var container = document.createElement('div');
            container.appendChild(sel.getRangeAt(0).cloneContents());
            if (container.querySelector('.comment-icon')) {
                e.preventDefault();
                showNotification('⚠️ Cannot cut comment icons.', 'warning');
            }
        }
    }, true);

    var observer = new MutationObserver(function(mutations) {
        if (window.bcIsHighlighting) return;
        var iconRemoved = false;
        mutations.forEach(function(m) {
            m.removedNodes.forEach(function(node) {
                if (node.classList && node.classList.contains('comment-icon')) iconRemoved = true;
                if (node.querySelector && node.querySelector('.comment-icon')) iconRemoved = true;
            });
        });
        if (iconRemoved && window.bcAllComments.length > 0) {
            setTimeout(highlightCommentsInDocument, 150);
        }
    });
    observer.observe(content, { childList: true, subtree: true });
    setInterval(protectAllIcons, 5000);
}

// =====================================================
// GET IDS
// =====================================================
function getContractId() {
    var urlParams = new URLSearchParams(window.location.search);
    var id = urlParams.get('id');
    if (id) return id;
    var match = window.location.pathname.match(/\/contract\/edit\/(\d+)/);
    if (match) return match[1];
    if (typeof contractId !== 'undefined' && contractId) return contractId;
    if (window.contractId) return window.contractId;
    var input = document.getElementById('contractId');
    if (input && input.value) return input.value;
    return null;
}

function getUserId() {
    var el = document.getElementById('currentUserId');
    if (el) return parseInt(el.value || el.dataset.userId || 0);
    if (window.currentUserId) return window.currentUserId;
    return null;
}

// =====================================================
// LOAD COMMENTS
// =====================================================
function loadComments() {
    if (!window.bcContractId) window.bcContractId = getContractId();
    if (!window.bcContractId) return;
    
    fetch('/api/contracts/comments/' + window.bcContractId, { credentials: 'include' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.success) {
            window.bcAllComments = data.comments || [];
            window.bcLoaded = true;
            if (data.current_user_id) window.bcUserId = data.current_user_id;
            console.log('📥 Loaded', window.bcAllComments.length, 'comments');
            
            var content = document.getElementById('contractContent');
            if (content && content.innerHTML.length > 100) {
                setTimeout(highlightCommentsInDocument, 300);
            }
            updateCommentsPanel();
            updateCommentBadge();
        }
    })
    .catch(function(err) { console.error('Load error:', err); });
}

// =====================================================
// HIGHLIGHT COMMENTS - Process from end to start
// =====================================================
function highlightCommentsInDocument() {
    var content = document.getElementById('contractContent');
    if (!content || content.innerHTML.length < 100) {
        setTimeout(highlightCommentsInDocument, 500);
        return;
    }
    
    window.bcIsHighlighting = true;
    console.log('🎨 Highlighting', window.bcAllComments.length, 'comments...');
    
    // Remove existing highlights
    content.querySelectorAll('.comment-highlight, .track-insert, .track-delete').forEach(function(el) {
        var icon = el.querySelector('.comment-icon');
        if (icon) icon.remove();
        var parent = el.parentNode;
        while (el.firstChild) parent.insertBefore(el.firstChild, el);
        parent.removeChild(el);
    });
    content.querySelectorAll('.comment-icon').forEach(function(i) { i.remove(); });
    content.normalize();
    
    // Sort by position DESCENDING - process from end to start
    // This prevents position shifts from affecting earlier comments
    var sortedComments = window.bcAllComments.slice().sort(function(a, b) {
        return (b.position_start || 0) - (a.position_start || 0);
    });
    
    var successCount = 0;
    sortedComments.forEach(function(comment) {
        if (applyHighlight(content, comment)) successCount++;
    });
    
    console.log('✅ Highlighted', successCount, '/', window.bcAllComments.length, 'comments');
    window.bcHighlighted = true;
    
    content.querySelectorAll('.comment-icon').forEach(function(icon) {
        icon.setAttribute('contenteditable', 'false');
        icon.style.userSelect = 'none';
        icon.setAttribute('data-protected', 'true');
    });
    
    setTimeout(function() { window.bcIsHighlighting = false; }, 300);
}

function applyHighlight(container, comment) {
    var className = comment.change_type === 'insert' ? 'track-insert' : comment.change_type === 'delete' ? 'track-delete' : 'comment-highlight';
    var text = comment.selected_text;
    if (!text) return false;
    
    if (container.querySelector('[data-comment-id="' + comment.id + '"]')) return true;
    
    return findAndWrapText(container, text, comment.id, className, comment.position_start);
}

// =====================================================
// FIND AND WRAP TEXT - With position-based matching
// =====================================================
function findAndWrapText(container, searchText, commentId, className, positionStart) {
    if (!searchText || !container) return false;
    if (container.querySelector('[data-comment-id="' + commentId + '"]')) return true;
    
    // Primary: Position-based search for accurate matching
    if (typeof positionStart === 'number' && positionStart >= 0) {
        var found = findAndWrapByPosition(container, searchText, commentId, className, positionStart);
        if (found) return true;
    }
    
    // Fallback: Single-node search
    var found = findAndWrapSingleNode(container, searchText, commentId, className);
    if (found) return true;
    
    // Fallback: Multi-node search
    found = findAndWrapMultiNode(container, searchText, commentId, className);
    if (found) return true;
    
    console.warn('⚠️ Could not highlight comment', commentId);
    return false;
}

// =====================================================
// POSITION-BASED SEARCH - For duplicate text
// =====================================================
function findAndWrapByPosition(container, searchText, commentId, className, targetPosition) {
    var textNodes = [];
    var fullText = '';
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    var node;
    
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
    
    // Find ALL occurrences
    var occurrences = [];
    var idx = 0;
    while ((idx = fullText.indexOf(searchText, idx)) !== -1) {
        occurrences.push(idx);
        idx++;
    }
    
    // Try normalized search if no matches
    if (occurrences.length === 0) {
        var normFull = fullText.replace(/\s+/g, ' ');
        var normSearch = searchText.replace(/\s+/g, ' ');
        idx = 0;
        while ((idx = normFull.indexOf(normSearch, idx)) !== -1) {
            occurrences.push(idx);
            idx++;
        }
    }
    
    if (occurrences.length === 0) return false;
    
    // Find closest occurrence to target position
    var bestMatch = occurrences[0];
    var bestDiff = Math.abs(occurrences[0] - targetPosition);
    
    for (var i = 1; i < occurrences.length; i++) {
        var diff = Math.abs(occurrences[i] - targetPosition);
        if (diff < bestDiff) {
            bestDiff = diff;
            bestMatch = occurrences[i];
        }
    }
    
    console.log('📍 Comment', commentId, '- Target:', targetPosition, 'Found:', bestMatch, 'Diff:', bestDiff, 'Occurrences:', occurrences.length);
    
    var matchEnd = bestMatch + searchText.length;
    var startNode = null, startOffset = 0, endNode = null, endOffset = 0;
    
    for (var i = 0; i < textNodes.length; i++) {
        var tn = textNodes[i];
        if (!startNode && bestMatch >= tn.start && bestMatch < tn.end) {
            startNode = tn.node;
            startOffset = bestMatch - tn.start;
        }
        if (matchEnd > tn.start && matchEnd <= tn.end) {
            endNode = tn.node;
            endOffset = matchEnd - tn.start;
            break;
        }
        if (matchEnd === tn.end) {
            endNode = tn.node;
            endOffset = tn.node.textContent.length;
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
        console.error('Position wrap error:', e);
        return false;
    }
}

function findAndWrapSingleNode(container, searchText, commentId, className) {
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    var node;
    
    while (node = walker.nextNode()) {
        var parent = node.parentElement;
        if (parent && (
            parent.classList.contains('comment-highlight') ||
            parent.classList.contains('track-insert') ||
            parent.classList.contains('track-delete') ||
            parent.classList.contains('comment-icon')
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
            } catch (e) { continue; }
        }
    }
    return false;
}

function findAndWrapMultiNode(container, searchText, commentId, className) {
    var textNodes = [];
    var fullText = '';
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    var node;
    
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
    
    var searchIdx = fullText.indexOf(searchText);
    if (searchIdx === -1) {
        var normFull = fullText.replace(/\s+/g, ' ');
        var normSearch = searchText.replace(/\s+/g, ' ');
        searchIdx = normFull.indexOf(normSearch);
    }
    if (searchIdx === -1) return false;
    
    var searchEnd = searchIdx + searchText.length;
    var startNode = null, startOffset = 0, endNode = null, endOffset = 0;
    
    for (var i = 0; i < textNodes.length; i++) {
        var tn = textNodes[i];
        if (!startNode && searchIdx >= tn.start && searchIdx < tn.end) {
            startNode = tn.node;
            startOffset = searchIdx - tn.start;
        }
        if (searchEnd > tn.start && searchEnd <= tn.end) {
            endNode = tn.node;
            endOffset = searchEnd - tn.start;
            break;
        }
    }
    
    if (!startNode || !endNode) return false;
    
    try {
        var range = document.createRange();
        range.setStart(startNode, startOffset);
        range.setEnd(endNode, endOffset);
        
        var wrapper = document.createElement('span');
        wrapper.className = className;
        wrapper.dataset.commentId = commentId;
        
        var contents = range.extractContents();
        wrapper.appendChild(contents);
        wrapper.appendChild(createCommentIcon(commentId));
        range.insertNode(wrapper);
        return true;
    } catch (e) { return false; }
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
    icon.setAttribute('data-protected', 'true');
    icon.style.cssText = 'display:inline-flex !important;align-items:center;justify-content:center;width:18px;height:18px;margin-left:2px;background:linear-gradient(135deg,#ffc107,#ff9800);color:#000;border-radius:50%;font-size:10px;cursor:pointer;vertical-align:middle;user-select:none !important;-webkit-user-select:none !important;box-shadow:0 2px 4px rgba(0,0,0,0.2);z-index:100;pointer-events:auto;';
    
    var cid = parseInt(commentId);
    icon.onclick = function(e) { e.preventDefault(); e.stopPropagation(); showBubble(cid, e); return false; };
    icon.onkeydown = function(e) { e.preventDefault(); return false; };
    icon.onselectstart = function(e) { e.preventDefault(); return false; };
    icon.ondragstart = function(e) { e.preventDefault(); return false; };
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
    
    var start = 0;
    if (content) {
        try {
            var pre = document.createRange();
            pre.selectNodeContents(content);
            pre.setEnd(range.startContainer, range.startOffset);
            start = pre.toString().length;
        } catch (e) {}
    }
    
    window.commentSelection = { text: text, absoluteStart: start, absoluteEnd: start + text.length };
    console.log('📝 Selected at position:', start, '-', start + text.length);
    
    var modal = document.getElementById('commentModal');
    if (modal) {
        modal.style.display = 'flex';
        var ta = document.getElementById('commentText');
        if (ta) { ta.value = ''; setTimeout(function() { ta.focus(); }, 100); }
        var prev = document.getElementById('selectedTextPreview');
        if (prev) prev.textContent = text.length > 200 ? text.substring(0, 200) + '...' : text;
        var newTextEl = document.getElementById('newText');
        if (newTextEl) newTextEl.value = '';
    }
}

function submitComment() {
    var ta = document.getElementById('commentText');
    var commentText = ta ? ta.value.trim() : '';
    
    if (!commentText) { showNotification('Enter a comment', 'warning'); return; }
    if (!window.commentSelection || !window.commentSelection.text) { showNotification('No text selected', 'warning'); return; }
    if (!window.bcContractId) window.bcContractId = getContractId();
    if (!window.bcContractId) { showNotification('No contract ID', 'error'); return; }
    
    var typeEl = document.querySelector('input[name="changeType"]:checked');
    var changeType = typeEl ? typeEl.value : 'comment';
    var newEl = document.getElementById('newText');
    var newText = newEl ? newEl.value.trim() : null;
    
    if (changeType === 'insert' && !newText) { showNotification('Enter new text', 'warning'); return; }
    
    var selectedText = window.commentSelection.text;
    var posStart = window.commentSelection.absoluteStart;
    
    console.log('📤 Submitting at position:', posStart);
    
    fetch('/api/contracts/comments/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
            contract_id: parseInt(window.bcContractId),
            comment_text: commentText,
            selected_text: selectedText,
            position_start: posStart,
            position_end: window.commentSelection.absoluteEnd || 0,
            start_xpath: '',
            change_type: changeType,
            original_text: selectedText,
            new_text: newText
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.success && d.comment) {
            var newComment = d.comment;
            newComment.position_start = posStart;
            newComment.position_end = window.commentSelection.absoluteEnd;
            window.bcAllComments.push(newComment);
            
            closeModal('commentModal');
            window.getSelection().removeAllRanges();
            
            window.bcIsHighlighting = true;
            var content = document.getElementById('contractContent');
            var className = changeType === 'insert' ? 'track-insert' : changeType === 'delete' ? 'track-delete' : 'comment-highlight';
            
            var success = findAndWrapText(content, selectedText, newComment.id, className, posStart);
            console.log('🎨 Highlight:', success ? 'success' : 'failed');
            
            setTimeout(function() { window.bcIsHighlighting = false; }, 300);
            
            updateCommentsPanel();
            updateCommentBadge();
            showNotification('Comment added', 'success');
            window.commentSelection = null;
        } else {
            showNotification('Failed to add comment', 'error');
        }
    })
    .catch(function(e) { console.error('Submit error:', e); showNotification('Error adding comment', 'error'); });
}

// =====================================================
// SHOW BUBBLE
// =====================================================
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
    var initials = name.split(' ').map(function(n) { return n[0]; }).join('').toUpperCase().substring(0, 2);
    
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
    if (comment.change_type === 'delete') {
        details = '<div style="margin-top:10px;padding:10px;background:#f8f9fa;border-radius:8px;"><div style="color:#dc3545;font-weight:600;font-size:12px;margin-bottom:6px;">🗑️ Delete:</div><div style="padding:8px;background:#fee2e2;border-radius:6px;color:#991b1b;text-decoration:line-through;max-height:100px;overflow:auto;">' + escapeHtml(comment.selected_text) + '</div></div>';
    } else if (comment.change_type === 'insert') {
        details = '<div style="margin-top:10px;padding:10px;background:#f8f9fa;border-radius:8px;"><div style="color:#6c757d;font-weight:600;font-size:12px;margin-bottom:6px;">✏️ Change:</div><div style="padding:8px;background:#fee2e2;border-radius:6px;color:#991b1b;text-decoration:line-through;margin-bottom:6px;max-height:60px;overflow:auto;">' + escapeHtml(comment.original_text || comment.selected_text) + '</div><div style="text-align:center;">↓</div><div style="padding:8px;background:#d1fae5;border-radius:6px;color:#166534;max-height:60px;overflow:auto;">' + escapeHtml(comment.new_text) + '</div></div>';
    }
    
    var badge = comment.change_type === 'delete' ? 'background:#fee2e2;color:#991b1b' : comment.change_type === 'insert' ? 'background:#d1fae5;color:#166534' : 'background:#fff3cd;color:#856404';
    var label = comment.change_type === 'delete' ? '🗑️ Deletion' : comment.change_type === 'insert' ? '✏️ Modification' : '💬 Comment';
    
    bubble.innerHTML =
        '<div style="padding:12px;background:linear-gradient(135deg,#fff9e6,#fff3cd);border-radius:10px 10px 0 0;display:flex;justify-content:space-between;align-items:center;">' +
            '<div style="display:flex;align-items:center;gap:10px;"><div style="width:36px;height:36px;background:linear-gradient(135deg,#ffc107,#ff9800);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;">' + initials + '</div><div style="font-weight:600;">' + escapeHtml(name) + '</div></div>' +
            '<div style="display:flex;gap:4px;">' + actions + '</div>' +
        '</div>' +
        '<div style="padding:15px;max-height:300px;overflow:auto;"><div style="color:#333;line-height:1.6;">' + escapeHtml(comment.comment_text) + '</div>' + details + '</div>' +
        '<div style="padding:10px 15px;background:#f8f9fa;border-radius:0 0 10px 10px;display:flex;gap:10px;">' +
            '<span style="font-size:11px;padding:4px 10px;border-radius:20px;' + badge + ';font-weight:600;">' + label + '</span>' +
            (isOwner ? '<span style="font-size:11px;padding:4px 10px;border-radius:20px;background:#e0e7ff;color:#4338ca;">Your comment</span>' : '') +
        '</div>';
    
    document.body.appendChild(bubble);
    window.bcCurrentBubble = bubble;
    
    var rect = event && event.target ? event.target.getBoundingClientRect() : { bottom: 200, left: 200, top: 180 };
    var top = rect.bottom + 10, left = rect.left;
    if (left + 350 > window.innerWidth) left = window.innerWidth - 370;
    if (top + 300 > window.innerHeight) top = rect.top - 310;
    bubble.style.top = Math.max(10, top) + 'px';
    bubble.style.left = Math.max(10, left) + 'px';
    bubble.onclick = function(e) { e.stopPropagation(); };
}

function closeBubble() {
    if (window.bcCurrentBubble) { window.bcCurrentBubble.remove(); window.bcCurrentBubble = null; }
    document.querySelectorAll('#commentBubble').forEach(function(b) { b.remove(); });
}

// =====================================================
// ACTIONS
// =====================================================
function deleteComment(id) {
    var c = findComment(id);
    if (!c) return;
    if (c.user_id != window.bcUserId) { showNotification('You can only delete your own comments', 'warning'); return; }
    if (!confirm('Delete this comment?')) return;
    removeHighlight(id);
    deleteFromDB(id);
    showNotification('Comment deleted', 'success');
}

function acceptChange(id) {
    var c = findComment(id);
    if (!c) return;
    if (c.user_id == window.bcUserId) { showNotification('Cannot accept your own change', 'warning'); return; }
    if (!confirm('Accept this change?')) return;
    
    window.bcIsHighlighting = true;
    var el = document.querySelector('[data-comment-id="' + id + '"].comment-highlight, [data-comment-id="' + id + '"].track-insert, [data-comment-id="' + id + '"].track-delete');
    if (el) {
        var p = el.parentNode;
        var icon = el.querySelector('.comment-icon');
        if (icon) icon.remove();
        if (c.change_type === 'delete') p.removeChild(el);
        else if (c.change_type === 'insert' && c.new_text) p.replaceChild(document.createTextNode(c.new_text), el);
        else { while (el.firstChild) p.insertBefore(el.firstChild, el); p.removeChild(el); }
        p.normalize();
    }
    setTimeout(function() { window.bcIsHighlighting = false; }, 200);
    deleteFromDB(id);
    if (typeof saveAsDraft === 'function') saveAsDraft();
    showNotification('Change accepted', 'success');
}

function rejectChange(id) {
    var c = findComment(id);
    if (!c) return;
    if (c.user_id == window.bcUserId) { showNotification('Cannot reject your own change', 'warning'); return; }
    if (!confirm('Reject this change?')) return;
    removeHighlight(id);
    deleteFromDB(id);
    showNotification('Change rejected', 'info');
}

function resolveComment(id) {
    var c = findComment(id);
    if (!c) return;
    if (c.user_id == window.bcUserId) { showNotification('Cannot resolve your own comment', 'warning'); return; }
    if (!confirm('Mark as resolved?')) return;
    removeHighlight(id);
    deleteFromDB(id);
    showNotification('Comment resolved', 'success');
}

function removeHighlight(id) {
    window.bcIsHighlighting = true;
    var el = document.querySelector('[data-comment-id="' + id + '"]');
    if (el && el.classList.contains('comment-icon')) el = el.closest('.comment-highlight, .track-insert, .track-delete');
    if (el) {
        var p = el.parentNode;
        var icon = el.querySelector('.comment-icon');
        if (icon) icon.remove();
        while (el.firstChild) p.insertBefore(el.firstChild, el);
        p.removeChild(el);
        p.normalize();
    }
    setTimeout(function() { window.bcIsHighlighting = false; }, 200);
}

function deleteFromDB(id) {
    fetch('/api/contracts/comments/' + id, { method: 'DELETE', credentials: 'include' })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.success) {
            window.bcAllComments = window.bcAllComments.filter(function(c) { return c.id != id; });
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
// HELPERS
// =====================================================
function escapeHtml(t) { if (!t) return ''; var d = document.createElement('div'); d.textContent = t; return d.innerHTML; }
function closeModal(id) { var m = document.getElementById(id); if (m) m.style.display = 'none'; }
function toggleCommentsPanel() { var p = document.getElementById('commentsPanel'); if (p) p.classList.toggle('open'); }

function updateCommentsPanel() {
    var p = document.getElementById('commentsPanelBody');
    if (!p) return;
    if (window.bcAllComments.length === 0) {
        p.innerHTML = '<div style="text-align:center;padding:40px;color:#999;"><i class="ti ti-message-off" style="font-size:40px;display:block;margin-bottom:10px;"></i>No comments</div>';
        return;
    }
    var h = '';
    window.bcAllComments.forEach(function(c) {
        var i = (c.user_name || 'U')[0].toUpperCase();
        h += '<div onclick="scrollToComment(' + c.id + ')" style="padding:10px;background:#f8f9fa;border-radius:8px;margin-bottom:8px;cursor:pointer;border-left:3px solid #ffc107;"><div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;"><div style="width:24px;height:24px;background:#ffc107;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;">' + i + '</div><span style="font-weight:600;font-size:13px;">' + escapeHtml(c.user_name) + '</span></div><div style="font-size:12px;color:#666;">' + escapeHtml((c.comment_text || '').substring(0, 60)) + '</div></div>';
    });
    p.innerHTML = h;
}

function scrollToComment(id) { var el = document.querySelector('[data-comment-id="' + id + '"]'); if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' }); }

function updateCommentBadge() {
    document.querySelectorAll('#commentsBadge, #commentsBadge2, .comment-badge').forEach(function(b) {
        b.textContent = window.bcAllComments.length;
        b.style.display = window.bcAllComments.length > 0 ? 'flex' : 'none';
    });
}

function showNotification(msg, type) {
    var e = document.querySelector('.bc-notification'); if (e) e.remove();
    var colors = { success: '#28a745', error: '#dc3545', warning: '#ffc107', info: '#17a2b8' };
    var n = document.createElement('div');
    n.className = 'bc-notification';
    n.style.cssText = 'position:fixed;top:20px;right:20px;padding:12px 20px;background:' + (colors[type] || '#17a2b8') + ';color:' + (type === 'warning' ? '#000' : '#fff') + ';border-radius:8px;z-index:100000;box-shadow:0 4px 12px rgba(0,0,0,0.15);font-size:14px;';
    n.textContent = msg;
    document.body.appendChild(n);
    setTimeout(function() { n.remove(); }, 3000);
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
window.findComment = findComment;
window.getContractId = getContractId;
window.createCommentIcon = createCommentIcon;
window.findAndWrapText = findAndWrapText;

console.log('✅ Bubble comments loaded (duplicate text support)');