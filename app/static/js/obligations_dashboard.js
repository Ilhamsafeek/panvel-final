// =============================================
// PRESET OBLIGATIONS LIBRARY
// =============================================
const PRESET_OBLIGATIONS = {
    contractor: [
        { title: "Payment", description: "Timely payment for the work completed as per the agreed terms.", category: "payment", priority: "high" },
        { title: "Provision of Information", description: "Provide necessary information and resources for the subcontractor to complete the work.", category: "coordination", priority: "medium" },
        { title: "Coordination", description: "Facilitate coordination with other Sub-contractors or stakeholders as needed.", category: "coordination", priority: "medium" },
        { title: "Support", description: "Offer reasonable support and assistance to the subcontractor.", category: "coordination", priority: "medium" },
        { title: "Inspection and Acceptance", description: "Conduct inspections of the work and accept it according to the agreement terms.", category: "inspection", priority: "high" },
        { title: "Dispute Resolution", description: "Establish a process for resolving disputes that may arise.", category: "other", priority: "high" },
        { title: "Compliance with Contractual Terms", description: "Ensure that the overall project complies with the terms of the main contract with client.", category: "compliance", priority: "high" }
    ],
    subcontractor: [
        { title: "Performance of Work", description: "Complete the specified work as detailed in the agreement.", category: "delivery", priority: "high" },
        { title: "Adherence to Standards", description: "Meet industry standards and any specific quality requirements.", category: "compliance", priority: "high" },
        { title: "Compliance with Laws", description: "Follow all applicable laws, regulations, and safety standards.", category: "compliance", priority: "high" },
        { title: "Timely Completion", description: "Deliver work within the agreed timeline and notify of any potential delays.", category: "delivery", priority: "high" },
        { title: "Reporting", description: "Provide regular updates on progress and any issues encountered.", category: "reporting", priority: "medium" },
        { title: "Subcontracting Limits", description: "Not subcontract further without the primary contractor's consent.", category: "compliance", priority: "high" },
        { title: "Bonds and Guarantee", description: "Maintain Bonds and Guarantees as per contractual requirement.", category: "insurance", priority: "high" },
        { title: "Insurance", description: "Maintain appropriate insurance coverage.", category: "insurance", priority: "high" },
        { title: "Indemnification", description: "Hold the primary contractor harmless from any claims.", category: "other", priority: "high" },
        { title: "Payment Terms", description: "Comply with the agreed payment terms and conditions.", category: "payment", priority: "high" },
        { title: "Confidentiality", description: "Keep sensitive information confidential as stipulated in the agreement.", category: "compliance", priority: "high" },
        { title: "Compliance with Contractual Terms", description: "Ensure that the overall project complies with the terms of the Agreement.", category: "compliance", priority: "high" },
        { title: "Sub-Contractor Responsibility", description: "Strictly abide with all sub-contractor responsibility as per agreement.", category: "other", priority: "high" }
    ]
};

function getAllPresetObligations() {
    return [...PRESET_OBLIGATIONS.contractor, ...PRESET_OBLIGATIONS.subcontractor];
}

// =============================================
// GLOBAL VARIABLES
// =============================================
let obligationsData = [];
let filteredData = [];
let aiGeneratedObligations = [];
let hasGeneratedAI = false;
let currentStats = {};

const API_BASE = '/api/obligations';

// =============================================
// INITIALIZATION
// =============================================
document.addEventListener('DOMContentLoaded', async function () {
    console.log('🚀 Initializing Obligations Dashboard...');
    await loadObligations();
    setupEventListeners();
});

// =============================================
// SETUP EVENT LISTENERS
// =============================================
function setupEventListeners() {
    let searchTimeout;
    document.getElementById('searchInput').addEventListener('input', function (e) {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => handleSearch(e), 300);
    });

    document.getElementById('statusFilter').addEventListener('change', handleFilter);
    document.getElementById('priorityFilter').addEventListener('change', handleFilter);
}

// =============================================
// LOAD OBLIGATIONS FROM DATABASE
// =============================================
async function loadObligations() {
    try {
        showLoading(true);

        console.log('📡 Fetching obligations from API...');

        // Fetch obligations and stats in parallel
        const [obligationsResponse, statsResponse] = await Promise.all([
            fetch(`${API_BASE}/all`, {
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                }
            }),
            fetch(`${API_BASE}/stats`, {
                credentials: 'include',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
        ]);

        if (!obligationsResponse.ok) {
            throw new Error(`HTTP error! status: ${obligationsResponse.status}`);
        }

        if (!statsResponse.ok) {
            console.warn('Stats API failed, continuing with obligations only');
        }

        const obligationsResult = await obligationsResponse.json();
        const statsResult = statsResponse.ok ? await statsResponse.json() : {};

        console.log('📦 Raw API response:', {
            obligations: obligationsResult,
            stats: statsResult
        });

        // FIXED: Handle both direct array and wrapped {data: [...]} formats
        obligationsData = Array.isArray(obligationsResult)
            ? obligationsResult
            : (obligationsResult.data || []);

        filteredData = [...obligationsData];

        // FIXED: Stats are returned directly, not wrapped
        currentStats = statsResult;

        console.log('✅ Data loaded:', {
            obligations: obligationsData.length,
            stats: currentStats
        });

        // Update UI
        updateStats();
        renderTable();

        showToast(`Loaded ${obligationsData.length} obligations successfully`, 'success');

    } catch (error) {
        console.error('❌ Error loading obligations:', error);
        showToast('Failed to load obligations: ' + error.message, 'error');

        // Show error in table
        const tbody = document.getElementById('obligationsTableBody');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" style="text-align: center; padding: 2rem; color: var(--danger-color);">
                        <i class="ti ti-alert-circle" style="font-size: 2rem;"></i>
                        <div style="margin-top: 0.5rem;">Failed to load obligations</div>
                        <div style="font-size: 0.875rem; color: var(--text-muted); margin-top: 0.25rem;">
                            ${error.message}
                        </div>
                        <button class="btn btn-primary" style="margin-top: 1rem;" onclick="loadObligations()">
                            <i class="ti ti-refresh"></i> Retry
                        </button>
                    </td>
                </tr>
            `;
        }
    } finally {
        showLoading(false);
    }
}
// =============================================
// UPDATE STATISTICS
// =============================================
function updateStats() {
    console.log('📊 Updating stats display:', currentStats);

    // Handle both wrapped and direct stats formats
    const stats = currentStats.data || currentStats;

    const totalEl = document.getElementById('statTotal');
    const inProgressEl = document.getElementById('statInProgress');
    const completedEl = document.getElementById('statCompleted');
    const overdueEl = document.getElementById('statOverdue');

    if (totalEl) totalEl.textContent = stats.total || 0;
    if (inProgressEl) inProgressEl.textContent = stats.pending || 0;
    if (completedEl) completedEl.textContent = stats.completed || 0;
    if (overdueEl) overdueEl.textContent = stats.overdue || 0;
}

// =============================================
// RENDER TABLE
// =============================================
function renderTable() {
    const tbody = document.getElementById('obligationsTableBody');

    if (filteredData.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; padding: 2rem;">
                    <i class="ti ti-clipboard-off" style="font-size: 2rem; color: var(--text-muted);"></i>
                    <div style="margin-top: 0.5rem; color: var(--text-muted);">No obligations found</div>
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = filteredData.map((obligation, index) => {
        const dueDate = obligation.due_date ? new Date(obligation.due_date) : null;
        const daysUntilDue = obligation.days_until_due;

        const dateClass = obligation.is_overdue ? 'danger' :
            (daysUntilDue !== null && daysUntilDue <= 7) ? 'warning' : '';

        const dateLabel = obligation.is_overdue ? `${Math.abs(daysUntilDue)} days overdue` :
            daysUntilDue === 0 ? 'Due today' :
                daysUntilDue !== null ? `In ${daysUntilDue} days` : '';

        const ownerInitials = obligation.owner_name ?
            obligation.owner_name.split(' ').map(n => n[0]).join('').toUpperCase() : 'UN';

        const sourceType = obligation.is_ai_generated ? 'ai' : obligation.is_preset ? 'preset' : 'manual';

        return `
            <tr>
                <td>
                    <div class="obligation-number">${index + 1}</div>
                </td>
                <td>
                    <div class="obligation-info">
                        <div class="obligation-title">${escapeHtml(obligation.obligation_title)}</div>
                        <div class="obligation-description">
                            ${escapeHtml(obligation.description || 'No description')}
                        </div>
                        <span class="source-badge badge-${sourceType}">
                            <i class="ti ti-${sourceType === 'ai' ? 'robot' : sourceType === 'preset' ? 'star' : 'user'}"></i>
                            ${sourceType === 'ai' ? 'AI' : sourceType === 'preset' ? 'Preset' : 'Custom'}
                        </span>
                    </div>
                </td>
                <td>
                    <div class="owner-info">
                        <div class="owner-avatar">${ownerInitials}</div>
                        <div class="owner-name">${obligation.owner_name || 'Unassigned'}</div>
                    </div>
                </td>
                <td>
                    <span class="status-badge ${obligation.status}">
                        <i class="ti ti-${getStatusIcon(obligation.status)}"></i>
                        ${formatStatus(obligation.status)}
                    </span>
                </td>
                <td>
                    <span class="priority-badge priority-${obligation.priority || 'low'}"></span>
                    ${capitalize(obligation.priority || 'low')}
                </td>
                <td>
                    <div class="date-info">
                        <div class="date-value ${dateClass}">
                            ${dueDate ? formatDate(dueDate) : 'Not set'}
                        </div>
                        ${dateLabel ? `<div class="date-label">${dateLabel}</div>` : ''}
                    </div>
                </td>
                <td>
                    <div class="table-actions">
                        <button class="action-btn" onclick="viewObligation(${obligation.id})" title="View">
                            <i class="ti ti-eye"></i>
                        </button>
                        <button class="action-btn delete" onclick="deleteObligation(${obligation.id})" title="Delete">
                            <i class="ti ti-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// =============================================
// SEARCH & FILTER
// =============================================
function handleSearch(e) {
    const searchTerm = e.target.value.toLowerCase();

    filteredData = obligationsData.filter(obligation => {
        return obligation.obligation_title?.toLowerCase().includes(searchTerm) ||
            obligation.description?.toLowerCase().includes(searchTerm) ||
            obligation.owner_name?.toLowerCase().includes(searchTerm);
    });

    applyFilters();
}

function handleFilter() {
    applyFilters();
}

function applyFilters() {
    const statusFilter = document.getElementById('statusFilter').value;
    const priorityFilter = document.getElementById('priorityFilter').value;
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();

    filteredData = obligationsData.filter(obligation => {
        const statusMatch = statusFilter === 'all' || obligation.status === statusFilter ||
            (statusFilter === 'overdue' && obligation.is_overdue);

        const priorityMatch = priorityFilter === 'all' || obligation.priority === priorityFilter;

        const searchMatch = !searchTerm ||
            obligation.obligation_title?.toLowerCase().includes(searchTerm) ||
            obligation.description?.toLowerCase().includes(searchTerm) ||
            obligation.owner_name?.toLowerCase().includes(searchTerm);

        return statusMatch && priorityMatch && searchMatch;
    });

    renderTable();
}

function filterByStatus(status) {
    document.getElementById('statusFilter').value = status;
    handleFilter();

    const title = document.getElementById('tableTitle');
    if (status === 'all') {
        title.textContent = 'All Obligations';
    } else {
        title.textContent = `${formatStatus(status)} Obligations`;
    }
}

// =============================================
// ADD PRESET OBLIGATION
// =============================================
function addObligationFromPreset() {
    const modalHTML = `
        <div class="modal active" id="presetModal" onclick="if(event.target === this) closePresetModal()">
            <div class="modal-content ai-modal-content">
                <div class="modal-header">
                    <h3 class="modal-title">
                        <i class="ti ti-star"></i>
                        <span>Select Preset Obligation</span>
                    </h3>
                    <button class="modal-close" onclick="closePresetModal()">
                        <i class="ti ti-x"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <div style="margin-bottom: 2rem;">
                        <h4 style="font-weight: 700; color: var(--text-color); margin-bottom: 1rem;">Contractor Obligations</h4>
                        <div style="display: grid; gap: 0.75rem;">
                            ${PRESET_OBLIGATIONS.contractor.map((preset, i) => `
                                <div class="ai-obligation-item" onclick="selectPreset(${i})">
                                    <div class="ai-obligation-content">
                                        <h5 class="ai-obligation-title">${escapeHtml(preset.title)}</h5>
                                        <p class="ai-obligation-desc">${escapeHtml(preset.description)}</p>
                                        <div class="ai-obligation-meta">
                                            <span class="category-badge">${preset.category}</span>
                                            <span class="source-badge badge-preset">${preset.priority} priority</span>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                    <div>
                        <h4 style="font-weight: 700; color: var(--text-color); margin-bottom: 1rem;">Sub-Contractor Obligations</h4>
                        <div style="display: grid; gap: 0.75rem;">
                            ${PRESET_OBLIGATIONS.subcontractor.map((preset, i) => `
                                <div class="ai-obligation-item" onclick="selectPreset(${PRESET_OBLIGATIONS.contractor.length + i})">
                                    <div class="ai-obligation-content">
                                        <h5 class="ai-obligation-title">${escapeHtml(preset.title)}</h5>
                                        <p class="ai-obligation-desc">${escapeHtml(preset.description)}</p>
                                        <div class="ai-obligation-meta">
                                            <span class="category-badge">${preset.category}</span>
                                            <span class="source-badge badge-preset">${preset.priority} priority</span>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    document.getElementById('presetModalContainer').innerHTML = modalHTML;
}

window.closePresetModal = function () {
    document.getElementById('presetModalContainer').innerHTML = '';
};

window.selectPreset = async function (index) {
    const allPresets = getAllPresetObligations();
    const preset = allPresets[index];

    closePresetModal();

    try {
        showLoading(true);

        const payload = {
            contract_id: null,
            obligation_title: preset.title,
            description: preset.description,
            obligation_type: preset.category,
            priority: preset.priority,
            owner_user_id: null,
            escalation_user_id: null,
            threshold_date: null,
            due_date: null,
            status: "initiated",
            is_ai_generated: false,
            is_preset: true
        };

        const response = await fetch(`${API_BASE}/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        showToast('Preset obligation added!', 'success');
        await loadObligations();

    } catch (error) {
        console.error('❌ Save error:', error);
        showToast(`Save failed: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
};

// =============================================
// SAVE CUSTOM OBLIGATION
// =============================================
async function saveCustomObligation(event) {
    event.preventDefault();

    const title = document.getElementById('obligationTitle').value.trim();
    const description = document.getElementById('obligationDescription').value.trim();
    const category = document.getElementById('obligationCategory').value;
    const priority = document.getElementById('obligationPriority').value;

    if (!title || !description) {
        showToast('Fill all required fields', 'error');
        return;
    }

    closeObligationModal();

    try {
        showLoading(true);

        const obligationData = {
            contract_id: null,
            obligation_title: title,
            description: description,
            obligation_type: category,
            priority: priority,
            owner_user_id: null,
            escalation_user_id: null,
            threshold_date: null,
            due_date: null,
            status: "initiated",
            is_ai_generated: false,
            is_preset: false
        };

        const response = await fetch(`${API_BASE}/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(obligationData)
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
        }

        showToast('Custom obligation created!', 'success');
        await loadObligations();

    } catch (error) {
        console.error('❌ Save error:', error);
        showToast(`Save failed: ${error.message}`, 'error');
    } finally {
        showLoading(false);
    }
}

// =============================================
// AI GENERATION
// =============================================
async function generateObligationsAI() {
    try {
        const generateBtn = document.getElementById('generateAIBtn');
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="ti ti-loader" style="animation: spin 1s linear infinite;"></i><span>Analyzing...</span>';

        // Simulate AI generation (replace with actual API call)
        await new Promise(resolve => setTimeout(resolve, 2000));

        aiGeneratedObligations = [
            {
                id: 'ai_1',
                title: 'Payment Terms',
                description: 'Timely payment for the work completed as per the agreed terms.',
                category: 'payment',
                priority: 'high',
                confidence: 95,
                clause_reference: 'Clause 5.1',
                selected: false
            },
            {
                id: 'ai_2',
                title: 'Provision of Information',
                description: 'Provide necessary information and resources for the subcontractor.',
                category: 'coordination',
                priority: 'medium',
                confidence: 92,
                clause_reference: 'Clause 3.4',
                selected: false
            },
            {
                id: 'ai_3',
                title: 'Coordination',
                description: 'Facilitate coordination with other Sub-contractors or stakeholders.',
                category: 'coordination',
                priority: 'medium',
                confidence: 88,
                clause_reference: 'Clause 7.2',
                selected: false
            },
            {
                id: 'ai_4',
                title: 'Inspection and Acceptance',
                description: 'Conduct inspections of the work and accept it according to the agreement.',
                category: 'inspection',
                priority: 'high',
                confidence: 94,
                clause_reference: 'Clause 8.1',
                selected: false
            },
            {
                id: 'ai_5',
                title: 'Performance Bond',
                description: 'Maintain a performance bond of 10% of contract value.',
                category: 'insurance',
                priority: 'high',
                confidence: 96,
                clause_reference: 'Clause 15.2',
                selected: false
            }
        ];

        hasGeneratedAI = true;
        displayAIObligations();
        showToast(`AI extracted ${aiGeneratedObligations.length} obligations`, 'success');

    } catch (error) {
        console.error('❌ AI generation error:', error);
        showToast('AI generation failed: ' + error.message, 'error');
    } finally {
        const generateBtn = document.getElementById('generateAIBtn');
        generateBtn.disabled = false;
        generateBtn.innerHTML = '<i class="ti ti-sparkles"></i><span>Generate (AI)</span>';
    }
}

function displayAIObligations() {
    const aiList = document.getElementById('aiObligationsList');

    aiList.innerHTML = aiGeneratedObligations.map((obligation, index) => `
        <div class="ai-obligation-item" onclick="toggleAIObligationSelection(${index})">
            <div class="ai-obligation-header">
                <input type="checkbox" class="ai-obligation-checkbox" id="ai-checkbox-${index}" 
                       onclick="event.stopPropagation(); toggleAIObligationSelection(${index})">
                <div class="ai-obligation-content">
                    <h4 class="ai-obligation-title">${escapeHtml(obligation.title)}</h4>
                    <div class="ai-obligation-desc">${escapeHtml(obligation.description)}</div>
                    <div class="ai-obligation-meta">
                        <span class="category-badge">${escapeHtml(obligation.category)}</span>
                        <span class="ai-confidence-badge">
                            <i class="ti ti-chart-line"></i>
                            ${Math.round(obligation.confidence)}%
                        </span>
                        ${obligation.clause_reference ? `
                            <span class="clause-reference">
                                <i class="ti ti-link"></i>
                                ${escapeHtml(obligation.clause_reference)}
                            </span>
                        ` : ''}
                        <button class="edit-ai-btn" onclick="event.stopPropagation(); editAIObligation(${index})">
                            <i class="ti ti-edit"></i> Edit
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `).join('');

    document.getElementById('aiObligationsModal').classList.add('active');
}

function toggleAIObligationSelection(index) {
    const checkbox = document.getElementById(`ai-checkbox-${index}`);
    checkbox.checked = !checkbox.checked;

    const item = checkbox.closest('.ai-obligation-item');
    if (checkbox.checked) {
        item.classList.add('selected');
        aiGeneratedObligations[index].selected = true;
    } else {
        item.classList.remove('selected');
        aiGeneratedObligations[index].selected = false;
    }
}

function editAIObligation(index) {
    const obligation = aiGeneratedObligations[index];

    document.getElementById('editAIObligationIndex').value = index;
    document.getElementById('editAIObligationTitle').value = obligation.title;
    document.getElementById('editAIObligationDescription').value = obligation.description;
    document.getElementById('editAIObligationCategory').value = obligation.category;
    document.getElementById('editAIObligationPriority').value = obligation.priority || 'medium';
    document.getElementById('editAIObligationClause').value = obligation.clause_reference || 'N/A';

    document.getElementById('editAIObligationModal').classList.add('active');
}

function saveEditedAIObligation(event) {
    event.preventDefault();

    const index = parseInt(document.getElementById('editAIObligationIndex').value);
    const title = document.getElementById('editAIObligationTitle').value.trim();
    const description = document.getElementById('editAIObligationDescription').value.trim();
    const category = document.getElementById('editAIObligationCategory').value;
    const priority = document.getElementById('editAIObligationPriority').value;

    if (!title || !description) {
        showToast('Fill all required fields', 'error');
        return;
    }

    aiGeneratedObligations[index].title = title;
    aiGeneratedObligations[index].description = description;
    aiGeneratedObligations[index].category = category;
    aiGeneratedObligations[index].priority = priority;

    closeEditAIModal();
    displayAIObligations();

    setTimeout(() => {
        const checkbox = document.getElementById(`ai-checkbox-${index}`);
        if (checkbox) {
            const item = checkbox.closest('.ai-obligation-item');
            const wasSelected = item.classList.contains('selected');
            if (wasSelected) checkbox.checked = true;
        }
    }, 100);

    showToast('AI obligation updated', 'success');
}

async function addSelectedObligations() {
    const selectedObligations = aiGeneratedObligations.filter(o => o.selected);

    if (selectedObligations.length === 0) {
        showToast('Select at least one obligation', 'warning');
        return;
    }

    closeAIModal();

    try {
        showLoading(true);

        let successCount = 0;

        for (const obligation of selectedObligations) {
            try {
                const obligationData = {
                    contract_id: null,
                    obligation_title: obligation.title,
                    description: obligation.description,
                    obligation_type: obligation.category,
                    priority: obligation.priority || 'medium',
                    owner_user_id: null,
                    escalation_user_id: null,
                    threshold_date: null,
                    due_date: null,
                    status: "initiated",
                    is_ai_generated: true
                };

                const response = await fetch(`${API_BASE}/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(obligationData)
                });

                if (response.ok) successCount++;

            } catch (error) {
                console.error('Error adding obligation:', error);
            }
        }

        if (successCount > 0) {
            showToast(`Added ${successCount} obligation(s)`, 'success');
            await loadObligations();
        }

    } catch (error) {
        console.error('Error adding obligations:', error);
        showToast('Error adding obligations', 'error');
    } finally {
        showLoading(false);
    }
}

// =============================================
// VIEW & DELETE
// =============================================
function viewObligation(id) {
    const obligation = obligationsData.find(o => o.id === id);
    if (!obligation) return;

    alert(`View Obligation: ${obligation.obligation_title}\n\nDescription: ${obligation.description || 'N/A'}\nStatus: ${obligation.status}\nOwner: ${obligation.owner_name || 'Unassigned'}`);
}

async function deleteObligation(id) {
    if (!confirm('Delete this obligation?')) return;

    try {
        showLoading(true);

        const response = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

        showToast('Deleted successfully', 'success');
        await loadObligations();

    } catch (error) {
        console.error('Error deleting:', error);
        showToast('Delete failed', 'error');
    } finally {
        showLoading(false);
    }
}

// =============================================
// MODAL FUNCTIONS
// =============================================
function openNewObligationModal() {
    document.getElementById('obligationForm').reset();
    document.getElementById('obligationModal').classList.add('active');
}

function closeObligationModal() {
    document.getElementById('obligationModal').classList.remove('active');
}

function closeAIModal() {
    document.getElementById('aiObligationsModal').classList.remove('active');
}

function closeEditAIModal() {
    document.getElementById('editAIObligationModal').classList.remove('active');
}

// =============================================
// UTILITY FUNCTIONS
// =============================================
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');
    const toastIcon = toast.querySelector('.toast-icon');

    toastMessage.textContent = message;
    toast.className = `toast ${type} show`;

    const icons = {
        success: 'check-circle',
        error: 'alert-circle',
        warning: 'alert-triangle',
        info: 'info-circle'
    };
    toastIcon.className = `toast-icon ti ti-${icons[type]}`;

    setTimeout(() => toast.classList.remove('show'), 3000);
}

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

function formatStatus(status) {
    if (!status) return 'Unknown';
    return status.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ');
}

function getStatusIcon(status) {
    const icons = {
        'completed': 'circle-check',
        'in-progress': 'clock',
        'pending': 'hourglass',
        'initiated': 'hourglass',
        'overdue': 'alert-circle'
    };
    return icons[status] || 'circle';
}

function formatDate(date) {
    if (!date) return 'N/A';
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${months[date.getMonth()]} ${date.getDate()}, ${date.getFullYear()}`;
}

function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

console.log('✅ Obligations dashboard initialized');