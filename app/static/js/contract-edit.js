// =====================================================
// FILE: /app/static/js/contract-edit.js
// UPDATED VERSION WITH FULL BACKEND INTEGRATION
// =====================================================

// Global variables (keep existing)
// let trackChangesEnabled = false;
let draggedElement = null;

// =====================================================
// EXISTING FUNCTIONS - UPDATED WITH BACKEND CALLS
// =====================================================

// Configure the floating action button from base template
document.addEventListener('DOMContentLoaded', function() {
    const fab = document.querySelector('.floating-menu-toggle');
    if (fab) {
        fab.innerHTML = '<i class="ti ti-sparkles"></i>';
        fab.title = "AI Actions";
    }
    
    // Focus on editor
    document.getElementById('contractContent').focus();
    
    // Set up keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey || e.metaKey) {
            switch(e.key) {
                case 's':
                    e.preventDefault();
                    saveAsDraft();
                    break;
                case 'b':
                    e.preventDefault();
                    execCmd('bold');
                    break;
                case 'i':
                    e.preventDefault();
                    execCmd('italic');
                    break;
                case 'u':
                    e.preventDefault();
                    execCmd('underline');
                    break;
            }
        }
    });
});

// Editor functions
function execCmd(command, value = null) {
    document.execCommand(command, false, value);
    document.getElementById('contractContent').focus();
}

// Panel toggle
function togglePanel(panelId) {
    const panel = document.getElementById(panelId);
    panel.classList.toggle('collapsed');
    
    const icon = panel.querySelector('.panel-toggle i');
    if (panelId === 'clausePanel') {
        icon.className = panel.classList.contains('collapsed') ? 'ti ti-chevron-right' : 'ti ti-chevron-left';
    } else {
        icon.className = panel.classList.contains('collapsed') ? 'ti ti-chevron-left' : 'ti ti-chevron-right';
    }
}

// Category toggle
function toggleCategory(element) {
    element.parentElement.classList.toggle('expanded');
}

// Modal functions
function openModal(modalId) {
    document.getElementById(modalId).classList.add('show');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('show');
}

// =====================================================
// SAVE DRAFT - UPDATED WITH BACKEND
// =====================================================
// async function saveAsDraft() {
//     const status = document.querySelector('.document-status');
//     status.innerHTML = '<i class="ti ti-loader-2"></i> Saving...';
//     status.classList.remove('saved');
    
//     const content = document.getElementById('contractContent').innerHTML;
    
//     try {
//         const response = await fetch(`/api/contracts/save-draft/${contractId}`, {
//             method: 'POST',
//             headers: {
//                 'Content-Type': 'application/json'
//             },
//             body: JSON.stringify({ 
//                 content: content,
//                 auto_save: true 
//             })
//         });
        
//         const data = await response.json();
        
//         if (data.success) {
//             status.innerHTML = '<i class="ti ti-circle-check"></i> Auto-saved';
//             status.classList.add('saved');
//         } else {
//             throw new Error('Save failed');
//         }
//     } catch (error) {
//         console.error('Error saving draft:', error);
//         status.innerHTML = '<i class="ti ti-alert-circle"></i> Save failed';
//         status.classList.remove('saved');
//     }
// }

// =====================================================
// SUBMIT FOR REVIEW - UPDATED WITH BACKEND
// =====================================================
async function submitInternalReview() {
    const specificEmails = document.getElementById('specificPersonnel').value;
    const masterWorkflow = document.getElementById('masterWorkflow').checked;
    
    if (!specificEmails && !masterWorkflow) {
        alert('Please enter email addresses or select Master Workflow');
        return;
    }
    
    const submitBtn = event.target;
    submitBtn.innerHTML = '<i class="ti ti-loader-2"></i> Sending...';
    submitBtn.disabled = true;
    
    try {
        const reviewData = {
            contract_id: parseInt(contractId),
            review_type: masterWorkflow ? 'masterWorkflow' : 'specific',
            personnel_emails: specificEmails ? specificEmails.split(',').map(e => e.trim()) : [],
            notes: document.querySelector('textarea[placeholder*="Add any notes"]')?.value || ''
        };
        
        const response = await fetch('/api/contracts/submit-review', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(reviewData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            closeModal('internalReviewModal');
            
            const status = document.querySelector('.document-status');
            status.innerHTML = '<i class="ti ti-check"></i> Sent for Internal Review';
            status.classList.add('saved');
            
            showNotification('Contract sent for internal review successfully!', 'success');
            
            setTimeout(() => {
                window.location.href = '/contract/review-status';
            }, 1500);
        } else {
            throw new Error('Failed to submit for review');
        }
    } catch (error) {
        console.error('Error submitting for review:', error);
        showNotification('Failed to submit for review', 'error');
        submitBtn.innerHTML = 'Submit';
        submitBtn.disabled = false;
    }
}

// =====================================================
// VERSION HISTORY - UPDATED WITH BACKEND
// =====================================================
async function showVersionHistory() {
    try {
        const response = await fetch(`/api/contracts/versions/${contractId}`);
        const data = await response.json();
        
        if (data.success && data.versions) {
            const versionContent = document.getElementById('versionHistoryContent');
            if (versionContent) {
                versionContent.innerHTML = data.versions.map((version, index) => `
                    <div style="padding: 1rem; background: ${index === 0 ? 'var(--background-light)' : 'white'}; border-radius: 8px; ${index === 0 ? 'border-left: 3px solid var(--primary-color);' : 'border: 1px solid var(--border-color);'} margin-bottom: 1rem;">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                            <strong>Version ${version.version} ${index === 0 ? '(Current)' : ''}</strong>
                            <span style="color: var(--text-muted); font-size: 0.875rem;">${new Date(version.created_at).toLocaleString()}</span>
                        </div>
                        <p style="font-size: 0.875rem; color: var(--text-muted); margin: 0.5rem 0;">${version.notes}</p>
                        <p style="font-size: 0.8rem; margin: 0;">Modified by: ${version.created_by}</p>
                    </div>
                `).join('');
            }
            openModal('versionModal');
        }
    } catch (error) {
        console.error('Error loading version history:', error);
        showNotification('Failed to load version history', 'error');
    }
}

async function compareVersions() {
    const v1 = prompt('Enter first version number:');
    const v2 = prompt('Enter second version number:');
    
    if (!v1 || !v2) return;
    
    try {
        const response = await fetch(`/api/contracts/versions/compare?contract_id=${contractId}&version1=${v1}&version2=${v2}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Found ${data.changes.length} changes between versions`, 'info');
            // Display changes in modal or side panel
        }
    } catch (error) {
        console.error('Error comparing versions:', error);
        showNotification('Failed to compare versions', 'error');
    }
}

// =====================================================
// EXPORT DOCUMENT - UPDATED WITH BACKEND
// =====================================================
function exportDocument() {
    openModal('exportModal');
}

async function executeExport() {
    const format = document.querySelector('input[name="exportFormat"]:checked')?.value || 'pdf';
    
    try {
        const response = await fetch(`/api/contracts/export/${contractId}?format=${format}`, {
            method: 'POST'
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `contract_${contractId}.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
            
            closeModal('exportModal');
            showNotification(`Document exported as ${format.toUpperCase()}`, 'success');
        }
    } catch (error) {
        console.error('Error exporting document:', error);
        showNotification('Failed to export document', 'error');
    }
}

// =====================================================
// TRACK CHANGES - UPDATED WITH BACKEND
// =====================================================
async function trackChanges() {
    const btn = event.target.closest('.toolbar-btn');
    const action = trackChangesEnabled ? 'disable' : 'enable';
    
    try {
        const response = await fetch(`/api/contracts/track-changes/${contractId}?action=${action}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            trackChangesEnabled = data.track_changes_enabled;
            btn.classList.toggle('active', trackChangesEnabled);
            
            if (trackChangesEnabled) {
                document.getElementById('contractContent').addEventListener('input', trackChange);
                showNotification('Track changes enabled', 'success');
            } else {
                document.getElementById('contractContent').removeEventListener('input', trackChange);
                showNotification('Track changes disabled', 'success');
            }
        }
    } catch (error) {
        console.error('Error toggling track changes:', error);
        showNotification('Failed to toggle track changes', 'error');
    }
}

function trackChange(e) {
    // Mark changed content
    const selection = window.getSelection();
    if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);
        const span = document.createElement('span');
        span.style.backgroundColor = 'rgba(255, 255, 0, 0.3)';
        span.style.borderBottom = '2px solid orange';
        
        try {
            range.surroundContents(span);
        } catch (e) {
            console.log('Complex selection, skipping highlight');
        }
    }
}

// =====================================================
// AI FUNCTIONS - NEW WITH BACKEND
// =====================================================
async function runAIAnalysis() {
    const messagesContainer = document.querySelector('.ai-messages');
    const aiPanel = document.getElementById('aiPanel');
    
    if (aiPanel.classList.contains('collapsed')) {
        togglePanel('aiPanel');
    }
    
    try {
        // Call risk analysis endpoint
        const response = await fetch(`/api/contracts/risk-analysis/${contractId}`, {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success && data.analysis) {
            const analysisMessage = document.createElement('div');
            analysisMessage.className = 'ai-message assistant';
            analysisMessage.innerHTML = `
                <div class="message-avatar">
                    <i class="ti ti-robot"></i>
                </div>
                <div class="message-content">
                    <strong>AI Risk Analysis Complete!</strong><br><br>
                    Overall Risk Score: <strong>${data.analysis.overall_score}/100</strong><br>
                    High Risks: <span style="color: var(--danger-color);">${data.analysis.high_risks}</span><br>
                    Medium Risks: <span style="color: var(--warning-color);">${data.analysis.medium_risks}</span><br>
                    Low Risks: <span style="color: var(--success-color);">${data.analysis.low_risks}</span><br><br>
                    ${data.analysis.risk_items ? 
                        '<strong>Key Issues:</strong><ul style="margin: 0.5rem 0 0 1rem;">' +
                        data.analysis.risk_items.slice(0, 3).map(item => 
                            `<li>${item.issue}: ${item.description}</li>`
                        ).join('') + '</ul>' : ''
                    }
                </div>
            `;
            messagesContainer.appendChild(analysisMessage);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    } catch (error) {
        console.error('Error running AI analysis:', error);
        showNotification('Failed to run AI analysis', 'error');
    }
}

async function askAI(query) {
    const input = document.getElementById('aiInput');
    input.value = query;
    await sendToAI();
}

async function sendToAI() {
    const input = document.getElementById('aiInput');
    const message = input.value.trim();
    
    if (!message) return;
    
    const messagesContainer = document.querySelector('.ai-messages');
    
    // Add user message
    const userMessage = document.createElement('div');
    userMessage.className = 'ai-message user';
    userMessage.innerHTML = `
        <div class="message-avatar">
            <i class="ti ti-user"></i>
        </div>
        <div class="message-content">${message}</div>
    `;
    messagesContainer.appendChild(userMessage);
    
    input.value = '';
    
    // Get selected text if asking about a clause
    const selection = window.getSelection();
    const selectedText = selection.toString();
    
    try {
        // Call clause suggestions endpoint
        const response = await fetch('/api/contracts/clause-suggestions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                clause_text: selectedText || message,
                clause_type: 'general',
                contract_id: parseInt(contractId)
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.suggestions && data.suggestions.length > 0) {
            const aiMessage = document.createElement('div');
            aiMessage.className = 'ai-message assistant';
            aiMessage.innerHTML = `
                <div class="message-avatar">
                    <i class="ti ti-robot"></i>
                </div>
                <div class="message-content">
                    <strong>AI Suggestion:</strong><br><br>
                    ${data.suggestions[0].suggested}<br><br>
                    <em>Reasoning: ${data.suggestions[0].reasoning}</em>
                </div>
            `;
            messagesContainer.appendChild(aiMessage);
        }
    } catch (error) {
        console.error('Error getting AI suggestions:', error);
        
        // Fallback response
        const aiMessage = document.createElement('div');
        aiMessage.className = 'ai-message assistant';
        aiMessage.innerHTML = `
            <div class="message-avatar">
                <i class="ti ti-robot"></i>
            </div>
            <div class="message-content">
                I'm analyzing your request: "${message}"<br><br>
                Please select specific text in the contract for detailed suggestions.
            </div>
        `;
        messagesContainer.appendChild(aiMessage);
    }
    
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// =====================================================
// NOTIFICATION HELPER
// =====================================================
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    
    const colors = {
        success: 'var(--success-bg)',
        error: 'var(--danger-bg)',
        warning: 'var(--warning-bg)',
        info: 'var(--info-bg)'
    };
    
    const textColors = {
        success: 'var(--success-color)',
        error: 'var(--danger-color)',
        warning: 'var(--warning-color)',
        info: 'var(--info-color)'
    };
    
    const icons = {
        success: 'check',
        error: 'alert-circle',
        warning: 'alert-triangle',
        info: 'info-circle'
    };
    
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        background: ${colors[type] || colors.info};
        color: ${textColors[type] || textColors.info};
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        z-index: 3000;
        animation: slideIn 0.3s ease;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    `;
    
    notification.innerHTML = `
        <i class="ti ti-${icons[type] || icons.info}"></i>
        ${message}
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// =====================================================
// KEEP EXISTING FUNCTIONS AS-IS
// =====================================================

// Clause Library Search
document.getElementById('clauseSearch')?.addEventListener('input', function(e) {
    const searchTerm = e.target.value.toLowerCase();
    const clauseItems = document.querySelectorAll('.clause-item');
    
    clauseItems.forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(searchTerm) ? 'block' : 'none';
    });
});

// Drag and Drop for clauses
document.querySelectorAll('.clause-item').forEach(item => {
    item.addEventListener('dragstart', function(e) {
        draggedElement = this;
        this.classList.add('dragging');
    });
    
    item.addEventListener('dragend', function(e) {
        this.classList.remove('dragging');
    });
});

document.getElementById('contractContent')?.addEventListener('dragover', function(e) {
    e.preventDefault();
});

document.getElementById('contractContent')?.addEventListener('drop', function(e) {
    e.preventDefault();
    if (draggedElement) {
        const clauseText = draggedElement.textContent.trim();
        const selection = window.getSelection();
        if (selection.rangeCount) {
            const range = selection.getRangeAt(0);
            const newClause = document.createElement('div');
            newClause.className = 'contract-clause track-changes';
            newClause.innerHTML = `<p><span class="clause-number">X.X</span> [New ${clauseText} clause to be customized]</p>`;
            range.insertNode(newClause);
        }
    }
});

// Auto-save every 30 seconds
// setInterval(() => {
//     const content = document.getElementById('contractContent');
//     if (content && content.textContent.length > 0) {
//         saveAsDraft();
//     }
// }, 30000);

// Add comment
function addComment() {
    const selection = window.getSelection();
    if (selection.rangeCount && selection.toString()) {
        const range = selection.getRangeAt(0);
        const comment = prompt('Add your comment:');
        if (comment) {
            const commentIndicator = document.createElement('span');
            commentIndicator.className = 'comment-indicator';
            commentIndicator.style.cssText = 'background: #ffffcc; border-bottom: 2px dotted #ffc107; cursor: help;';
            commentIndicator.textContent = selection.toString();
            commentIndicator.title = comment;
            range.deleteContents();
            range.insertNode(commentIndicator);
        }
    } else {
        alert('Please select text to add a comment');
    }
}

// Find and Replace
function findReplace() {
    const find = prompt('Find:');
    if (find) {
        const replace = prompt('Replace with:');
        if (replace !== null) {
            const content = document.getElementById('contractContent');
            const regex = new RegExp(find.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
            content.innerHTML = content.innerHTML.replace(regex, `<span style="background: #90EE90;">${replace}</span>`);
            
            // Remove highlight after 3 seconds
            setTimeout(() => {
                content.querySelectorAll('span[style*="#90EE90"]').forEach(span => {
                    span.style.backgroundColor = '';
                });
            }, 3000);
        }
    }
}

// Insert Table
function insertTable() {
    const rows = prompt('Number of rows:', '3');
    const cols = prompt('Number of columns:', '3');
    
    if (rows && cols) {
        let table = '<table border="1" style="width: 100%; border-collapse: collapse; margin: 1rem 0;">';
        for (let i = 0; i < parseInt(rows); i++) {
            table += '<tr>';
            for (let j = 0; j < parseInt(cols); j++) {
                table += '<td style="padding: 8px; border: 1px solid #ddd;" contenteditable="true">&nbsp;</td>';
            }
            table += '</tr>';
        }
        table += '</table>';
        execCmd('insertHTML', table);
    }
}

// Helper functions for existing UI
function toggleReviewOption() {
    const masterWorkflow = document.getElementById('masterWorkflow').checked;
    const workflowPreview = document.getElementById('workflowPreview');
    const personnelInput = document.getElementById('specificPersonnel');
    
    if (masterWorkflow) {
        workflowPreview.style.display = 'block';
        personnelInput.value = '';
        personnelInput.disabled = true;
        personnelInput.style.opacity = '0.5';
    } else {
        workflowPreview.style.display = 'none';
        personnelInput.disabled = false;
        personnelInput.style.opacity = '1';
    }
}

function handlePersonnelInput() {
    const input = document.getElementById('specificPersonnel');
    const suggestions = document.getElementById('emailSuggestions');
    
    document.getElementById('masterWorkflow').checked = false;
    document.getElementById('workflowPreview').style.display = 'none';
    
    if (input.value.length > 2) {
        const sampleEmails = [
            'john.doe@company.com',
            'jane.smith@company.com',
            'legal.dept@company.com',
            'finance.team@company.com',
            'director@company.com'
        ];
        
        const filtered = sampleEmails.filter(email => 
            email.toLowerCase().includes(input.value.toLowerCase())
        );
        
        if (filtered.length > 0 && suggestions) {
            suggestions.innerHTML = filtered.map(email => 
                `<div onclick="addEmail('${email}')" style="padding: 0.5rem; cursor: pointer; border-radius: 4px;" 
                     onmouseover="this.style.background='var(--background-light)'" 
                     onmouseout="this.style.background='transparent'">
                    <i class="ti ti-mail" style="margin-right: 0.5rem; color: var(--primary-color);"></i>${email}
                </div>`
            ).join('');
            suggestions.style.display = 'block';
        } else if (suggestions) {
            suggestions.style.display = 'none';
        }
    } else if (suggestions) {
        suggestions.style.display = 'none';
    }
}

function addEmail(email) {
    const input = document.getElementById('specificPersonnel');
    const currentValue = input.value;
    
    if (currentValue) {
        input.value = currentValue + ', ' + email;
    } else {
        input.value = email;
    }
    
    document.getElementById('emailSuggestions').style.display = 'none';
}

// Legacy function mapping
function submitReview() {
    submitInternalReview();
}

function openClauseLibrary() {
    openModal('clauseModal');
}

function startCollaboration() {
    alert('Collaboration feature will open the live negotiation interface');
}

function insertClause() {
    closeModal('clauseModal');
    showNotification('Clause inserted successfully!', 'success');
}

// Close modals on outside click
document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', function(e) {
        if (e.target === this) {
            this.classList.remove('show');
        }
    });
});

// Animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes spin {
        to { transform: rotate(360deg); }
    }
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

