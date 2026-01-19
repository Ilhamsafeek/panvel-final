// =====================================================
// BUBBLE COMMENTS - FINAL FIXED VERSION
// - Waits for contract content before highlighting
// - Strong icon protection (cannot delete with keyboard)
// =====================================================

window.bcAllComments = [];
window.bcCurrentBubble = null;
window.bcContractId = null;
window.bcUserId = null;
window.bcLoaded = false;
window.bcHighlighted = false;

// =====================================================
// INITIALIZE
// =====================================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Bubble comments initializing...');
    
    window.bcContractId = getContractId();
    window.bcUserId = getUserId();
    
    console.log('📋 Contract ID:', window.bcContractId);
    console.log('👤 User ID:', window.bcUserId);
    
    if (window.bcContractId) {
        loadComments();
    }
    
    // Retry loading if contract ID not found yet
    setTimeout(function() {
        if (!window.bcContractId) {
            window.bcContractId = getContractId();
            if (window.bcContractId && !window.bcLoaded) loadComments();
        }
    }, 1500);
    
    // Watch for contract content to be loaded (for dynamic loading)
    waitForContractContent();
    
    // Close bubble on outside click
    document.addEventListener('click', function(e) {
        if (e.target.closest('.comment-icon')) return;
        if (e.target.closest('.comment-bubble')) return;
        if (e.target.closest('#commentBubble')) return;
        if (window.bcCurrentBubble) closeBubble();
    }, true);
    
    // Setup strong icon protection
    setupStrongIconProtection();
});

// =====================================================
// WAIT FOR CONTRACT CONTENT TO LOAD
// =====================================================
function waitForContractContent() {
    var checkInterval = setInterval(function() {
        var content = document.getElementById('contractContent');
        if (content && content.innerHTML.length > 100) {
            console.log('📄 Contract content detected, length:', content.innerHTML.length);
            clearInterval(checkInterval);
            
            // Re-highlight after content loads
            if (window.bcAllComments.length > 0 && !window.bcHighlighted) {
                console.log('🔄 Re-highlighting after content load...');
                setTimeout(function() {
                    highlightCommentsInDocument();
                }, 500);
            }
        }
    }, 500);
    
    // Stop checking after 30 seconds
    setTimeout(function() { clearInterval(checkInterval); }, 30000);
}

// =====================================================
// STRONG ICON PROTECTION - CANNOT DELETE WITH KEYBOARD
// =====================================================
function setupStrongIconProtection() {
    // Use capture phase to intercept before other handlers
    document.addEventListener('keydown', function(e) {
        if (e.key !== 'Backspace' && e.key !== 'Delete') return;
        
        var sel = window.getSelection();
        if (!sel.rangeCount) return;
        
        var range = sel.getRangeAt(0);
        var content = document.getElementById('contractContent');
        if (!content || !content.contains(range.commonAncestorContainer)) return;
        
        // Check 1: Selection contains icon
        var cloned = range.cloneContents();
        if (cloned.querySelector && cloned.querySelector('.comment-icon')) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            showNotification('Cannot delete comment icon. Use the comment bubble.', 'warning');
            return false;
        }
        
        // Check 2: Cursor is right before/after icon (Backspace case)
        if (e.key === 'Backspace' && range.collapsed) {
            var node = range.startContainer;
            var offset = range.startOffset;
            
            // If at start of text node, check previous sibling
            if (node.nodeType === 3 && offset === 0) {
                var prev = node.previousSibling;
                if (prev && (prev.classList && prev.classList.contains('comment-icon'))) {
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    showNotification('Cannot delete comment icon.', 'warning');
                    return false;
                }
                // Check if previous sibling contains icon at end
                if (prev && prev.querySelector && prev.querySelector('.comment-icon:last-child')) {
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    showNotification('Cannot delete comment icon.', 'warning');
                    return false;
                }
            }
            
            // If in element, check child before cursor
            if (node.nodeType === 1 && offset > 0) {
                var prevChild = node.childNodes[offset - 1];
                if (prevChild && prevChild.classList && prevChild.classList.contains('comment-icon')) {
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    showNotification('Cannot delete comment icon.', 'warning');
                    return false;
                }
            }
        }
        
        // Check 3: Delete key - cursor is right before icon
        if (e.key === 'Delete' && range.collapsed) {
            var node = range.startContainer;
            var offset = range.startOffset;
            
            // If at end of text node, check next sibling
            if (node.nodeType === 3 && offset === node.textContent.length) {
                var next = node.nextSibling;
                if (next && next.classList && next.classList.contains('comment-icon')) {
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    showNotification('Cannot delete comment icon.', 'warning');
                    return false;
                }
            }
            
            // If in element, check child after cursor
            if (node.nodeType === 1 && offset < node.childNodes.length) {
                var nextChild = node.childNodes[offset];
                if (nextChild && nextChild.classList && nextChild.classList.contains('comment-icon')) {
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    showNotification('Cannot delete comment icon.', 'warning');
                    return false;
                }
            }
        }
        
        // Check 4: Check if inside a highlight span and trying to delete the icon
        var parentHighlight = range.startContainer.nodeType === 3 
            ? range.startContainer.parentElement 
            : range.startContainer;
        
        while (parentHighlight && parentHighlight !== content) {
            if (parentHighlight.classList && 
                (parentHighlight.classList.contains('comment-highlight') || 
                 parentHighlight.classList.contains('track-insert') || 
                 parentHighlight.classList.contains('track-delete'))) {
                
                var icon = parentHighlight.querySelector('.comment-icon');
                if (icon) {
                    // Check if about to delete the icon
                    var iconRect = icon.getBoundingClientRect();
                    var rangeRect = range.getBoundingClientRect();
                    
                    if (e.key === 'Backspace') {
                        // If cursor is right after icon
                        var textAfterIcon = icon.nextSibling;
                        if (!textAfterIcon || (textAfterIcon.nodeType === 3 && textAfterIcon.textContent === '')) {
                            if (range.startContainer === parentHighlight || 
                                range.startContainer.previousSibling === icon) {
                                e.preventDefault();
                                e.stopPropagation();
                                e.stopImmediatePropagation();
                                showNotification('Cannot delete comment icon.', 'warning');
                                return false;
                            }
                        }
                    }
                }
                break;
            }
            parentHighlight = parentHighlight.parentElement;
        }
    }, true); // Capture phase
    
    // Also prevent cut operations that include icons
    document.addEventListener('cut', function(e) {
        var sel = window.getSelection();
        if (!sel.rangeCount) return;
        var range = sel.getRangeAt(0);
        var cloned = range.cloneContents();
        if (cloned.querySelector && cloned.querySelector('.comment-icon')) {
            e.preventDefault();
            showNotification('Cannot cut comment icons.', 'warning');
        }
    }, true);
    
    // MutationObserver to restore accidentally deleted icons
    var content = document.getElementById('contractContent');
    if (content) {
        var observer = new MutationObserver(function(mutations) {
            var needsRestore = false;
            mutations.forEach(function(m) {
                m.removedNodes.forEach(function(node) {
                    if (node.classList && node.classList.contains('comment-icon')) {
                        needsRestore = true;
                    }
                    if (node.querySelector && node.querySelector('.comment-icon')) {
                        needsRestore = true;
                    }
                });
            });
            if (needsRestore && window.bcAllComments.length > 0) {
                console.log('⚠️ Icon removed, restoring...');
                setTimeout(highlightCommentsInDocument, 100);
            }
        });
        observer.observe(content, { childList: true, subtree: true });
    }
}

// =====================================================
// GET CONTRACT ID
// =====================================================
function getContractId() {
    var urlParams = new URLSearchParams(window.location.search);
    var id = urlParams.get('id');
    if (id) return id;
    
    var match = window.location.pathname.match(/\/contract\/edit\/(\d+)/);
    if (match) return match[1];
    
    if (typeof contractId !== 'undefined' && contractId) return contractId;
    if (window.contractId) return window.contractId;
    if (window.currentContractId) return window.currentContractId;
    
    var input = document.getElementById('contractId');
    if (input && input.value) return input.value;
    
    return null;
}

// =====================================================
// GET USER ID
// =====================================================
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
    if (!window.bcContractId) {
        console.error('❌ No contract ID');
        return;
    }
    
    console.log('📥 Loading comments for:', window.bcContractId);
    
    fetch('/api/contracts/comments/' + window.bcContractId, { credentials: 'include' })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        console.log('📥 API response:', data);
        
        if (data.success) {
            window.bcAllComments = data.comments || [];
            window.bcLoaded = true;
            
            if (data.current_user_id) {
                window.bcUserId = data.current_user_id;
            }
            
            console.log('✅ Loaded', window.bcAllComments.length, 'comments');
            
            // Check if content is ready
            var content = document.getElementById('contractContent');
            if (content && content.innerHTML.length > 100) {
                setTimeout(highlightCommentsInDocument, 300);
            } else {
                // Content not ready, waitForContractContent will handle it
                console.log('⏳ Waiting for contract content...');
            }
            
            updateCommentsPanel();
            updateCommentBadge();
        }
    })
    .catch(function(err) {
        console.error('❌ Load error:', err);
    });
}

// =====================================================
// HIGHLIGHT COMMENTS
// =====================================================
function highlightCommentsInDocument() {
    var content = document.getElementById('contractContent');
    if (!content) {
        console.error('❌ contractContent not found');
        return;
    }
    
    if (content.innerHTML.length < 100) {
        console.log('⏳ Content not ready yet, waiting...');
        setTimeout(highlightCommentsInDocument, 500);
        return;
    }
    
    console.log('🎨 Highlighting', window.bcAllComments.length, 'comments');
    
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
    
    // Apply highlights
    var successCount = 0;
    window.bcAllComments.forEach(function(comment, idx) {
        var success = applyHighlight(content, comment);
        if (success) successCount++;
        console.log('  [' + (idx+1) + '] ID ' + comment.id + ':', success ? '✅' : '⚠️');
    });
    
    window.bcHighlighted = true;
    console.log('✅ Highlighted', successCount, '/', window.bcAllComments.length, 'comments');
}

function applyHighlight(container, comment) {
    var className = comment.change_type === 'insert' ? 'track-insert' : comment.change_type === 'delete' ? 'track-delete' : 'comment-highlight';
    var text = comment.selected_text;
    if (!text) return false;
    
    var walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
    var node;
    
    while (node = walker.nextNode()) {
        var idx = node.textContent.indexOf(text);
        if (idx !== -1) {
            try {
                var range = document.createRange();
                range.setStart(node, idx);
                range.setEnd(node, idx + text.length);
                
                var wrapper = document.createElement('span');
                wrapper.className = className;
                wrapper.dataset.commentId = comment.id;
                
                var icon = createCommentIcon(comment.id);
                var contents = range.extractContents();
                wrapper.appendChild(contents);
                wrapper.appendChild(icon);
                range.insertNode(wrapper);
                return true;
            } catch (e) { continue; }
        }
    }
    return false;
}

// =====================================================
// CREATE PROTECTED COMMENT ICON
// =====================================================
function createCommentIcon(commentId) {
    var icon = document.createElement('span');
    icon.className = 'comment-icon';
    icon.dataset.commentId = commentId;
    icon.innerHTML = '<i class="ti ti-message-circle-filled"></i>';
    icon.title = 'Click to view comment';
    
    // CRITICAL: Make completely non-editable
    icon.contentEditable = 'false';
    icon.setAttribute('contenteditable', 'false');
    icon.setAttribute('unselectable', 'on');
    icon.setAttribute('data-protected', 'true');
    
    icon.style.cssText = 'display:inline-flex !important;align-items:center;justify-content:center;width:18px;height:18px;margin-left:2px;background:linear-gradient(135deg,#ffc107,#ff9800);color:#000;border-radius:50%;font-size:10px;cursor:pointer;vertical-align:middle;user-select:none;-webkit-user-select:none;-moz-user-select:none;box-shadow:0 2px 4px rgba(0,0,0,0.2);z-index:100;pointer-events:auto;';
    
    var cid = parseInt(commentId);
    
    // Click handler
    icon.onclick = function(e) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        console.log('🖱️ Icon clicked:', cid);
        showBubble(cid, e);
        return false;
    };
    
    // Prevent all keyboard actions on icon
    icon.onkeydown = function(e) {
        e.preventDefault();
        e.stopPropagation();
        return false;
    };
    
    // Prevent selection
    icon.onselectstart = function(e) {
        e.preventDefault();
        return false;
    };
    
    // Prevent drag
    icon.ondragstart = function(e) {
        e.preventDefault();
        return false;
    };
    
    return icon;
}

// =====================================================
// SHOW BUBBLE
// =====================================================
function showBubble(commentId, event) {
    console.log('💬 showBubble:', commentId);
    
    var comment = findComment(commentId);
    if (!comment) {
        console.error('❌ Comment not found:', commentId);
        return;
    }
    
    console.log('✅ Found:', comment);
    closeBubble();
    
    var isOwner = (comment.user_id == window.bcUserId);
    var isChange = comment.change_type && comment.change_type !== 'comment';
    
    var bubble = document.createElement('div');
    bubble.id = 'commentBubble';
    bubble.style.cssText = 'position:fixed;background:white;border:2px solid #ffc107;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,0.25);min-width:320px;max-width:420px;z-index:99999;';
    
    var name = comment.user_name || 'User';
    var initials = name.split(' ').map(function(n) { return n[0]; }).join('').toUpperCase().substring(0, 2);
    var time = formatTime(new Date(comment.created_at));
    
    // Actions - Owner can only DELETE
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
        details = '<div style="margin-top:10px;padding:10px;background:#f8f9fa;border-radius:8px;"><div style="color:#dc3545;font-weight:600;font-size:12px;margin-bottom:6px;">🗑️ Delete:</div><div style="padding:8px;background:#fee2e2;border-radius:6px;color:#991b1b;text-decoration:line-through;">' + escapeHtml(comment.selected_text) + '</div></div>';
    } else if (comment.change_type === 'insert') {
        details = '<div style="margin-top:10px;padding:10px;background:#f8f9fa;border-radius:8px;"><div style="color:#6c757d;font-weight:600;font-size:12px;margin-bottom:6px;">✏️ Change:</div><div style="padding:8px;background:#fee2e2;border-radius:6px;color:#991b1b;text-decoration:line-through;margin-bottom:6px;">' + escapeHtml(comment.original_text || comment.selected_text) + '</div><div style="text-align:center;">↓</div><div style="padding:8px;background:#d1fae5;border-radius:6px;color:#166534;">' + escapeHtml(comment.new_text) + '</div></div>';
    }
    
    var badge = comment.change_type === 'delete' ? 'background:#fee2e2;color:#991b1b' : comment.change_type === 'insert' ? 'background:#d1fae5;color:#166534' : 'background:#fff3cd;color:#856404';
    var label = comment.change_type === 'delete' ? '🗑️ Deletion' : comment.change_type === 'insert' ? '✏️ Modification' : '💬 Comment';
    
    bubble.innerHTML = 
        '<div style="padding:12px;background:linear-gradient(135deg,#fff9e6,#fff3cd);border-radius:10px 10px 0 0;display:flex;justify-content:space-between;align-items:center;">' +
            '<div style="display:flex;align-items:center;gap:10px;">' +
                '<div style="width:36px;height:36px;background:linear-gradient(135deg,#ffc107,#ff9800);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;">' + initials + '</div>' +
                '<div><div style="font-weight:600;">' + escapeHtml(name) + '</div><div style="font-size:11px;color:#7f8c8d;">' + time + '</div></div>' +
            '</div>' +
            '<div style="display:flex;gap:4px;">' + actions + '</div>' +
        '</div>' +
        '<div style="padding:15px;">' +
            '<div style="color:#333;line-height:1.6;">' + escapeHtml(comment.comment_text) + '</div>' +
            details +
        '</div>' +
        '<div style="padding:10px 15px;background:#f8f9fa;border-radius:0 0 10px 10px;display:flex;gap:10px;">' +
            '<span style="font-size:11px;padding:4px 10px;border-radius:20px;' + badge + ';font-weight:600;">' + label + '</span>' +
            (isOwner ? '<span style="font-size:11px;padding:4px 10px;border-radius:20px;background:#e0e7ff;color:#4338ca;">Your comment</span>' : '') +
        '</div>';
    
    document.body.appendChild(bubble);
    window.bcCurrentBubble = bubble;
    
    // Position
    var rect = event && event.target ? event.target.getBoundingClientRect() : { bottom: 200, left: 200, top: 180 };
    var top = rect.bottom + 10;
    var left = rect.left;
    if (left + 350 > window.innerWidth) left = window.innerWidth - 370;
    if (top + 300 > window.innerHeight) top = rect.top - 310;
    bubble.style.top = Math.max(10, top) + 'px';
    bubble.style.left = Math.max(10, left) + 'px';
    
    console.log('✅ Bubble shown');
    
    bubble.onclick = function(e) { e.stopPropagation(); };
}

// =====================================================
// CLOSE BUBBLE
// =====================================================
function closeBubble() {
    if (window.bcCurrentBubble) {
        window.bcCurrentBubble.remove();
        window.bcCurrentBubble = null;
    }
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
    
    var el = document.querySelector('[data-comment-id="' + id + '"].comment-highlight, [data-comment-id="' + id + '"].track-insert, [data-comment-id="' + id + '"].track-delete');
    if (el) {
        var p = el.parentNode;
        var icon = el.querySelector('.comment-icon');
        if (icon) icon.remove();
        if (c.change_type === 'delete') p.removeChild(el);
        else if (c.change_type === 'insert' && c.new_text) p.replaceChild(document.createTextNode(c.new_text), el);
        else { while (el.firstChild) p.insertBefore(el.firstChild, el); p.removeChild(el); }
    }
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
// ADD COMMENT
// =====================================================
function openAddCommentModal() {
    var sel = window.getSelection();
    if (!sel.rangeCount || !sel.toString().trim()) { showNotification('Select text first', 'warning'); return; }
    
    var text = sel.toString().trim();
    var range = sel.getRangeAt(0).cloneRange();
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
    
    window.commentSelection = { text: text, range: range, absoluteStart: start, absoluteEnd: start + text.length };
    
    var modal = document.getElementById('commentModal');
    if (modal) {
        modal.style.display = 'flex';
        var ta = document.getElementById('commentText');
        if (ta) { ta.value = ''; setTimeout(function() { ta.focus(); }, 100); }
        var prev = document.getElementById('selectedTextPreview');
        if (prev) prev.textContent = text;
    }
}

function submitComment() {
    var ta = document.getElementById('commentText');
    var text = ta ? ta.value.trim() : '';
    if (!text || !window.commentSelection) { showNotification('Enter a comment', 'warning'); return; }
    
    if (!window.bcContractId) window.bcContractId = getContractId();
    if (!window.bcContractId) { showNotification('No contract ID', 'error'); return; }
    
    var typeEl = document.querySelector('input[name="changeType"]:checked');
    var type = typeEl ? typeEl.value : 'comment';
    var newEl = document.getElementById('newText');
    var newText = newEl ? newEl.value.trim() : null;
    
    if (type === 'insert' && !newText) { showNotification('Enter new text', 'warning'); return; }
    
    fetch('/api/contracts/comments/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
            contract_id: parseInt(window.bcContractId),
            comment_text: text,
            selected_text: window.commentSelection.text,
            position_start: window.commentSelection.absoluteStart || 0,
            position_end: window.commentSelection.absoluteEnd || 0,
            start_xpath: '',
            change_type: type,
            original_text: window.commentSelection.text,
            new_text: newText
        })
    })
    .then(function(r) { return r.json(); })
    .then(function(d) {
        if (d.success) {
            d.comment.position_start = window.commentSelection.absoluteStart;
            d.comment.position_end = window.commentSelection.absoluteEnd;
            window.bcAllComments.push(d.comment);
            
            try {
                var className = type === 'insert' ? 'track-insert' : type === 'delete' ? 'track-delete' : 'comment-highlight';
                var wrapper = document.createElement('span');
                wrapper.className = className;
                wrapper.dataset.commentId = d.comment.id;
                var icon = createCommentIcon(d.comment.id);
                var contents = window.commentSelection.range.extractContents();
                wrapper.appendChild(contents);
                wrapper.appendChild(icon);
                window.commentSelection.range.insertNode(wrapper);
            } catch (e) { console.error('Wrap error:', e); }
            
            closeModal('commentModal');
            updateCommentsPanel();
            updateCommentBadge();
            showNotification('Comment added', 'success');
        }
    })
    .catch(function(e) { showNotification('Error adding comment', 'error'); });
}

// =====================================================
// HELPERS
// =====================================================
function formatTime(d) {
    var s = Math.floor((new Date() - d) / 1000);
    if (s < 60) return 'Just now';
    var m = Math.floor(s / 60); if (m < 60) return m + 'm ago';
    var h = Math.floor(m / 60); if (h < 24) return h + 'h ago';
    return Math.floor(h / 24) + 'd ago';
}

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

function toggleCommentsPanel() {
    var p = document.getElementById('commentsPanel');
    if (p) p.classList.toggle('open');
}

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
        h += '<div onclick="scrollToComment(' + c.id + ')" style="padding:10px;background:#f8f9fa;border-radius:8px;margin-bottom:8px;cursor:pointer;border-left:3px solid #ffc107;"><div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;"><div style="width:24px;height:24px;background:#ffc107;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;">' + i + '</div><span style="font-weight:600;font-size:13px;">' + escapeHtml(c.user_name) + '</span></div><div style="font-size:12px;color:#666;">' + escapeHtml(c.comment_text.substring(0, 60)) + '</div></div>';
    });
    p.innerHTML = h;
}

function scrollToComment(id) {
    var el = document.querySelector('[data-comment-id="' + id + '"]');
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function updateCommentBadge() {
    document.querySelectorAll('#commentsBadge, #commentsBadge2, .comment-badge').forEach(function(b) {
        b.textContent = window.bcAllComments.length;
        b.style.display = window.bcAllComments.length > 0 ? 'flex' : 'none';
    });
}

function showNotification(msg, type) {
    var e = document.querySelector('.bc-notification');
    if (e) e.remove();
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
window.allComments = window.bcAllComments;

console.log('✅ Bubble comments loaded (final version)');