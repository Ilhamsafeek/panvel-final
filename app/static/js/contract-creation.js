// =====================================================
// FILE: app/static/js/contract-creation.js
// Contract Creation - Full Backend Integration with AI Assistant
// Version: 2.0 with AI Assistant
// Date: 2025-01-30
// =====================================================

const API_BASE = '/api/contracts';

// =====================================================
// Global State Management
// =====================================================
let selectedProfile = 'contractor';
let selectedTemplate = null;
let selectedCreationMethod = 'template';
let uploadedFile = null;
let selectedClauses = [];
let selectedContractType = '';
let aiAssistantOpen = false;

// =====================================================
// Initialization
// =====================================================

document.addEventListener('DOMContentLoaded', function () {
    initializeContractCreation();
});

async function initializeContractCreation() {
    try {
        console.log('🚀 Initializing contract creation...');

        // Bind event listeners
        bindEventListeners();

        // Load templates
        await loadTemplates();

        // Load projects for save modal
        await loadProjects();

        console.log(' Initialization complete');

    } catch (error) {
        console.error(' Initialization error:', error);
        showNotification('Failed to initialize contract creation', 'error');
    }
}

function bindEventListeners() {
    console.log('🔗 Binding event listeners...');

    // Profile selection
    const profileRadios = document.querySelectorAll('input[name="profile"]');
    profileRadios.forEach(radio => {
        radio.addEventListener('change', handleProfileChange);
    });

    // Tab switching
    const tabButtons = document.querySelectorAll('.tab-btn');
    tabButtons.forEach(button => {
        button.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();

            const btnText = this.textContent.trim().toLowerCase();
            let tabName = 'template';

            if (btnText.includes('template')) {
                tabName = 'template';
            } else if (btnText.includes('ai') || btnText.includes('generate')) {
                tabName = 'ai';
            } else if (btnText.includes('upload') || btnText.includes('existing')) {
                tabName = 'upload';
            }

            switchTab(tabName);
        });
    });

    // ==================== AI ASSISTANT BINDINGS ====================

    // Contract Type Selection Handler
    const contractTypeSelect = document.getElementById('contractTypeSelect');
    if (contractTypeSelect) {
        contractTypeSelect.addEventListener('change', handleContractTypeChange);
    }

    // AI Assistant Toggle Button
    const aiAssistantToggle = document.getElementById('aiAssistantToggle');
    if (aiAssistantToggle) {
        aiAssistantToggle.addEventListener('click', toggleAiAssistant);
    }

    // Add/Remove Clauses Button (inside AI Assistant)
    const addClausesBtn = document.getElementById('addClausesBtn');
    if (addClausesBtn) {
        addClausesBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            openClausesModal();
        });
    }

    // ==================== END AI ASSISTANT BINDINGS ====================

    // Preview button
    const previewBtn = document.getElementById('previewBtn');
    if (previewBtn) {
        previewBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('👁️ Preview button clicked');
            if (selectedTemplate) {
                openModal('templatePreviewModal');
            } else {
                showNotification('Please select a template first', 'error');
            }
        });
    }

    // Proceed button
    const proceedBtn = document.getElementById('proceedBtn');
    if (proceedBtn) {
        proceedBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            console.log('▶️ Proceed button clicked');
            proceedToNext();
        });
    }

    // File upload handlers
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('fileInput');

    if (uploadZone && fileInput) {
        uploadZone.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            fileInput.click();
        });

        uploadZone.addEventListener('dragover', handleDragOver);
        uploadZone.addEventListener('dragleave', handleDragLeave);
        uploadZone.addEventListener('drop', handleDrop);
        fileInput.addEventListener('change', handleFileSelect);
    }

    // Modal close buttons
    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            const modal = this.closest('.modal');
            if (modal) {
                closeModal(modal.id);
            }
        });
    });

    // Close modal on backdrop click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function (e) {
            if (e.target === this) {
                closeModal(this.id);
            }
        });
    });

    const removeFileBtn = document.getElementById('removeFileBtn');
    if (removeFileBtn) {
        removeFileBtn.addEventListener('click', removeFile);
    }

    console.log(' Event listeners bound');
}

// =====================================================
// AI ASSISTANT HANDLER FUNCTIONS
// =====================================================
function handleContractTypeChange(event) {
    selectedContractType = event.target.value;
    const aiAssistantToggle = document.getElementById('aiAssistantToggle');
    const aiHint = document.getElementById('aiHint');

    console.log('📋 Contract type changed to:', selectedContractType);

    if (selectedContractType && selectedContractType !== '') {
        // Enable AI Assistant button
        if (aiAssistantToggle) {
            aiAssistantToggle.disabled = false;
        }

        if (aiHint) {
            aiHint.textContent = 'Click AI Assistant to add details';
            aiHint.classList.add('success');
        }

        console.log(' AI Assistant enabled for contract type:', selectedContractType);
    } else {
        // Disable if no selection
        if (aiAssistantToggle) {
            aiAssistantToggle.disabled = true;
        }

        if (aiHint) {
            aiHint.textContent = 'Select contract type to enable AI Assistant';
            aiHint.classList.remove('success');
        }

        // Close AI Assistant panel if open
        const panel = document.getElementById('aiAssistantPanel');
        if (panel) {
            panel.style.display = 'none';
        }
        aiAssistantOpen = false;
    }
}

function toggleAiAssistant() {
    const panel = document.getElementById('aiAssistantPanel');
    const toggle = document.getElementById('aiAssistantToggle');

    if (!panel || !toggle) {
        console.error(' AI Assistant elements not found');
        return;
    }

    if (panel.style.display === 'none' || !panel.style.display) {
        // Open panel
        panel.style.display = 'block';
        aiAssistantOpen = true;

        // Update button appearance
        toggle.innerHTML = '<i class="ti ti-sparkles"></i> AI Assistant (Open)';

        console.log(' AI Assistant panel opened');
    } else {
        // Close panel
        panel.style.display = 'none';
        aiAssistantOpen = false;

        // Update button appearance
        toggle.innerHTML = '<i class="ti ti-sparkles"></i> AI Assistant';

        console.log(' AI Assistant panel closed');
    }
}

function hideAiAssistant() {
    const panel = document.getElementById('aiAssistantPanel');
    const toggle = document.getElementById('aiAssistantToggle');

    if (panel) {
        panel.style.display = 'none';
        aiAssistantOpen = false;
    }

    if (toggle) {
        toggle.innerHTML = '<i class="ti ti-sparkles"></i> AI Assistant';
    }

    console.log(' AI Assistant hidden');
}

function buildAIPrompt() {
    const contractType = document.getElementById('contractTypeSelect')?.value;
    const duration = document.getElementById('aiDuration')?.value;
    const paymentStructure = document.getElementById('aiPaymentStructure')?.value;
    const specialRequirements = document.getElementById('aiSpecialRequirements')?.value;

    console.log('🔨 Building AI prompt from inputs...');
    console.log('  Contract Type:', contractType);
    console.log('  Duration:', duration);
    console.log('  Payment Structure:', paymentStructure);
    console.log('  Special Requirements:', specialRequirements);
    console.log('  Selected Clauses:', selectedClauses);

    let fullPrompt = '';

    if (contractType) {
        const contractTypeSelect = document.getElementById('contractTypeSelect');
        const contractTypeText = contractTypeSelect.options[contractTypeSelect.selectedIndex].text;
        fullPrompt += `Create a ${contractTypeText}`;
    }

    if (duration) fullPrompt += ` with duration: ${duration}`;
    if (paymentStructure) fullPrompt += `, payment structure: ${paymentStructure}`;
    if (specialRequirements) fullPrompt += `. Special requirements: ${specialRequirements}`;
    if (selectedClauses.length > 0) {
        fullPrompt += `. Include the following clauses: ${selectedClauses.map(c => c.replace(/_/g, ' ')).join(', ')}`;
    }

    console.log(' Built AI prompt:', fullPrompt);

    return fullPrompt;
}

// =====================================================
// Template Management
// =====================================================

async function loadTemplates() {
    try {
        console.log('📋 Loading templates for profile:', selectedProfile);

        const templateGrid = document.getElementById('templateGrid');
        const loadingTemplates = document.getElementById('loadingTemplates');
        const noTemplates = document.getElementById('noTemplates');

        // Show loading state
        if (loadingTemplates) loadingTemplates.style.display = 'flex';
        if (noTemplates) noTemplates.style.display = 'none';

        const response = await authenticatedFetch(`${API_BASE}/templates/list?category=${selectedProfile}`);

        if (!response.ok) {
            throw new Error('Failed to load templates');
        }

        const data = await response.json();
        console.log(' Templates loaded:', data);

        // Hide loading state
        if (loadingTemplates) loadingTemplates.style.display = 'none';

        // Clear existing templates except loading/no-templates divs
        const existingCards = templateGrid.querySelectorAll('.template-card');
        existingCards.forEach(card => card.remove());

        if (data.templates && data.templates.length > 0) {
            // Render templates
            data.templates.forEach(template => {
                const templateCard = createTemplateCard(template);
                templateGrid.appendChild(templateCard);
            });
            console.log(` Rendered ${data.templates.length} templates`);
        } else {
            // Show no templates message
            if (noTemplates) noTemplates.style.display = 'flex';
            console.log(' No templates available');
        }

    } catch (error) {
        console.error(' Error loading templates:', error);

        const loadingTemplates = document.getElementById('loadingTemplates');
        if (loadingTemplates) loadingTemplates.style.display = 'none';

        showNotification('Failed to load templates', 'error');
    }
}

function createTemplateCard(template) {
    const card = document.createElement('div');
    card.className = 'template-card';
    card.setAttribute('data-template', template.id);

    // Add click handler
    card.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        selectTemplate(this);
    });

    // Comprehensive icon mapping
    const iconMap = {
        'confidentiality': 'lock',
        'service': 'briefcase',
        'procurement': 'shopping-cart',
        'master': 'file-text',
        'subcontract': 'git-branch',
        'construction': 'building-factory',
        'epc': 'crane',
        'design-build': 'pencil-bolt',
        'supply': 'truck-delivery',
        'consulting': 'user-check',
        'project-mgmt': 'clipboard-list',
        'supervision': 'eye-check',
        'technical': 'settings',
        'employment': 'id-badge',
        'freelance': 'user-bolt',
        'intern': 'school',
        'lease': 'home',
        'sale-purchase': 'home-dollar',
        'property-mgmt': 'building-estate',
        'software-dev': 'code',
        'saas': 'cloud',
        'maintenance': 'tool',
        'hosting': 'server',
        'partnership': 'handshake',
        'jv': 'building-community',
        'mou': 'file-certificate',
        'loan': 'coin',
        'investment': 'chart-arrows',
        'payment-plan': 'calendar-dollar',
        'marketing': 'ad',
        'agency': 'brand-adobe',
        'influencer': 'brand-instagram',
        'distribution': 'package',
        'reseller': 'refresh',
        'franchise': 'building-store',
        'licensing': 'license',
        'trademark': 'trademark',
        'copyright': 'copyright',
        'manufacturing': 'assembly',
        'oem': 'components',
        'insurance': 'shield-check',
        'warranty': 'certificate',
        'transport': 'truck',
        'logistics': 'route',
        'legal': 'scale',
        'accounting': 'calculator',
        'audit': 'report-search',
        'training': 'presentation',
        'education': 'book'
    };

    const icon = iconMap[template.type] || 'file-text';

    card.innerHTML = `
        <div class="template-icon"><i class="ti ti-${icon}"></i></div>
        <div class="template-info">
            <div class="template-name">${template.name}</div>
        </div>
    `;

    return card;
}

function selectTemplate(element) {
    console.log('🎯 Template selected');

    const templateId = element.getAttribute('data-template');

    // Remove previous selection
    document.querySelectorAll('.template-card').forEach(card => {
        card.classList.remove('selected');
    });

    // Add new selection
    element.classList.add('selected');
    selectedTemplate = templateId;

    console.log(' Template ID:', templateId);

    // Show preview button
    const previewBtn = document.getElementById('previewBtn');
    if (previewBtn) {
        previewBtn.style.display = 'block';
    }

    // Update action hint
    const actionHint = document.getElementById('actionHint');
    if (actionHint) {
        const templateName = element.querySelector('.template-name').textContent;
        actionHint.textContent = `Selected: ${templateName}`;
    }
}

// =====================================================
// Project Management
// =====================================================

async function loadProjects() {
    try {
        console.log('📁 Loading projects...');

        const response = await authenticatedFetch('/api/projects/my-projects');

        if (!response.ok) {
            throw new Error('Failed to load projects');
        }

        const data = await response.json();
        console.log(' Projects loaded:', data);
        populateProjectSelect(data.projects || []);

    } catch (error) {
        console.error(' Error loading projects:', error);
    }
}


function populateProjectSelect(projects) {
    const projectSelect = document.getElementById('projectSelect');
    if (!projectSelect) return;

    // Clear existing options
    projectSelect.innerHTML = '<option value="">Select Project (Optional)</option>'; // ← UPDATED

    // Add projects
    projects.forEach(project => {
        const option = document.createElement('option');
        option.value = project.id;
        option.textContent = `${project.project_code} - ${project.project_name}`;
        projectSelect.appendChild(option);
    });

    // Add "Create New Project" option
    const createOption = document.createElement('option');
    createOption.value = 'create_new';
    createOption.textContent = '+ Create New Project';
    createOption.style.fontWeight = 'bold';
    createOption.style.color = 'var(--primary-color)';
    projectSelect.appendChild(createOption);

    console.log(` Populated ${projects.length} projects`);

    // 🔥 ADD EVENT LISTENER - Add these 2 lines
    projectSelect.removeEventListener('change', handleProjectSelectChange);
    projectSelect.addEventListener('change', handleProjectSelectChange);
}


// =====================================================
// Event Handlers
// =====================================================

function handleProfileChange(event) {
    selectedProfile = event.target.value;
    const profileText = event.target.closest('.profile-option').querySelector('.profile-name').textContent;
    document.getElementById('selectedProfileText').textContent = profileText;

    console.log('👤 Profile changed to:', selectedProfile);

    // Reload templates for selected profile
    loadTemplates();
}

function switchTab(tabName) {
    selectedCreationMethod = tabName;

    console.log('📑 Switching to tab:', tabName);

    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Find and activate the correct button
    const activeBtn = Array.from(document.querySelectorAll('.tab-btn')).find(btn => {
        const btnText = btn.textContent.trim().toLowerCase();
        if (tabName === 'template' && btnText.includes('template')) return true;
        if (tabName === 'ai' && (btnText.includes('ai') || btnText.includes('generate'))) return true;
        if (tabName === 'upload' && (btnText.includes('upload') || btnText.includes('existing'))) return true;
        return false;
    });

    if (activeBtn) {
        activeBtn.classList.add('active');
    }

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });

    const targetTab = document.getElementById(`${tabName}-tab`);
    if (targetTab) {
        targetTab.classList.add('active');
    }

    // Reset selections
    if (tabName === 'template') {
        selectedTemplate = null;
        document.querySelectorAll('.template-card').forEach(card => {
            card.classList.remove('selected');
        });
        const previewBtn = document.getElementById('previewBtn');
        if (previewBtn) previewBtn.style.display = 'none';
    } else if (tabName === 'upload') {
        uploadedFile = null;
    }

    // Update action hint
    const actionHint = document.getElementById('actionHint');
    if (actionHint) {
        if (tabName === 'template') {
            actionHint.textContent = 'Select a template to proceed';
        } else if (tabName === 'upload') {
            actionHint.textContent = 'Upload a contract file to proceed';
        } else if (tabName === 'ai') {
            actionHint.textContent = 'Select contract type and fill AI Assistant to proceed';
        }
    }
}

// =====================================================
// File Upload Handlers
// =====================================================

function handleDragOver(event) {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.classList.add('drag-over');
}

function handleDragLeave(event) {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.classList.remove('drag-over');
}

function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.classList.remove('drag-over');

    const files = event.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFileSelect(event) {
    const files = event.target.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
}

function handleFile(file) {
    console.log('📎 File selected:', file.name);

    // Validate file
    const validTypes = [
        'application/pdf',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    ];
    const maxSize = 50 * 1024 * 1024; // 50MB

    if (!validTypes.includes(file.type)) {
        showNotification('Please upload a PDF, DOC, or DOCX file', 'error');
        return;
    }

    if (file.size > maxSize) {
        showNotification('File size must be less than 50MB', 'error');
        return;
    }

    uploadedFile = file;

    // Update UI
    document.getElementById('uploadZone').style.display = 'none';
    const filePreview = document.getElementById('filePreview');
    filePreview.style.display = 'flex';
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatFileSize(file.size);

    // Update action hint
    const actionHint = document.getElementById('actionHint');
    if (actionHint) {
        actionHint.textContent = `File ready: ${file.name}`;
    }

    console.log(' File ready for upload');
}

function removeFile() {
    uploadedFile = null;
    document.getElementById('uploadZone').style.display = 'flex';
    document.getElementById('filePreview').style.display = 'none';
    document.getElementById('fileInput').value = '';

    const actionHint = document.getElementById('actionHint');
    if (actionHint) {
        actionHint.textContent = 'Upload a contract file to proceed';
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

// =====================================================
// Modal Management
// =====================================================

function openModal(modalId) {
    console.log('🔓 Opening modal:', modalId);
    const modal = document.getElementById(modalId);
    if (!modal) {
        console.error(' Modal not found:', modalId);
        return;
    }

    // Special handling for template preview
    if (modalId === 'templatePreviewModal' && selectedTemplate) {
        updateTemplatePreview();
    }

    // Force display using inline style (overrides CSS)
    modal.setAttribute('style', 'display: block !important;');
    modal.classList.add('show');

    // Lock body scroll
    document.body.setAttribute('style', 'overflow: hidden !important;');
    document.body.classList.add('modal-open');

    console.log(' Modal opened successfully');
}

function closeModal(modalId) {
    console.log('🔒 Closing modal:', modalId);
    const modal = document.getElementById(modalId);
    if (!modal) {
        console.error(' Modal not found:', modalId);
        return;
    }

    // Remove inline styles - let CSS take over
    modal.removeAttribute('style');
    modal.classList.remove('show');

    // Restore body scroll
    document.body.removeAttribute('style');
    document.body.classList.remove('modal-open');

    // Remove any backdrops
    const backdrops = document.querySelectorAll('.modal-backdrop');
    backdrops.forEach(backdrop => backdrop.remove());

    // Reset form if exists
    const form = modal.querySelector('form');
    if (form) form.reset();

    console.log(' Modal closed successfully');
}

// ESC key handler
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        const openModals = document.querySelectorAll('.modal.show');
        openModals.forEach(modal => {
            closeModal(modal.id);
        });
    }
});

function confirmProfile() {
    closeModal('profileModal');
    showNotification('Profile confirmed as ' + selectedProfile, 'success');
}

function useSelectedTemplate() {
    closeModal('templatePreviewModal');
    openModal('saveContractModal');
}

async function updateTemplatePreview() {
    try {
        const templateCard = document.querySelector('.template-card.selected');
        const previewName = document.getElementById('previewTemplateName');
        const contentDiv = document.getElementById('previewContent');

        if (!selectedTemplate) return;

        // Set title from selected card
        if (templateCard && previewName) {
            const templateName = templateCard.querySelector('.template-name')?.textContent || 'Template';
            previewName.textContent = templateName + ' Template';
        }

        // Show loading state
        if (contentDiv) {
            contentDiv.innerHTML = `
                <div style="display:flex; align-items:center; gap:8px; color: var(--text-muted);">
                    <i class="ti ti-loader"></i>
                    <span>Loading template content...</span>
                </div>
            `;
        }

        // Fetch template details from backend
        const resp = await authenticatedFetch(`/api/templates/${selectedTemplate}`);
        if (!resp.ok) {
            throw new Error(`Failed to fetch template (${resp.status})`);
        }
        const data = await resp.json();

        // Render HTML content
        if (contentDiv) {
            const html = data.template_content || data.content;
            if (html && html !== 'Template content not available') {
                contentDiv.innerHTML = html;
            } else {
                contentDiv.innerHTML = `
                    <div style="padding: 3rem; text-align: center; background: rgba(255, 193, 7, 0.1); border-radius: 8px; border: 1px dashed #ffc107;">
                        <i class="ti ti-alert-triangle" style="font-size: 3rem; color: #856404;"></i>
                        <p style="color: #856404; margin-top: 1rem; font-weight: 600;">No template content available</p>
                        <p style="color: #856404; margin-top: 0.5rem; font-size: 0.9rem;">This template doesn't have preview content yet.</p>
                    </div>
                `;
            }
        }

    } catch (err) {
        console.error('Error updating template preview:', err);
        const contentDiv = document.getElementById('previewContent');
        if (contentDiv) {
            contentDiv.innerHTML = `
                <div style="padding: 1rem; background: rgba(220,53,69,0.08); border: 1px solid rgba(220,53,69,0.25); border-radius: 8px; color: #842029;">
                    Failed to load template preview. Please try again.
                </div>
            `;
        }
        showNotification('Failed to load template preview', 'error');
    }
}

// =====================================================
// Clause Selection
// =====================================================

function openClausesModal() {
    console.log('📋 Opening clauses modal...');

    // Restore previously selected clauses
    if (selectedClauses.length > 0) {
        selectedClauses.forEach(clauseKey => {
            const checkbox = document.querySelector(`input[name="clause_${clauseKey}"]`);
            if (checkbox) {
                checkbox.checked = true;
                console.log(`  ✓ Restored selection: ${clauseKey}`);
            }
        });
    }

    openModal('clausesModal');
}

function openAIPromptModal() {
    openModal('aiPromptModal');
}

function applyClauseSelection() {
    console.log(' Applying clause selection...');

    // Clear previous selections
    selectedClauses = [];

    // Get all checked checkboxes from the clauses modal
    const checkedBoxes = document.querySelectorAll('#clausesModal input[type="checkbox"]:checked');

    console.log(`📊 Found ${checkedBoxes.length} checked checkboxes`);

    checkedBoxes.forEach(checkbox => {
        // Extract clause key from name attribute
        const clauseKey = checkbox.name.replace('clause_', '');

        if (clauseKey && clauseKey !== '') {
            selectedClauses.push(clauseKey);
            console.log(`  ✓ Selected: ${clauseKey}`);
        }
    });

    console.log(`📋 Total clauses selected: ${selectedClauses.length}`);
    console.log('📋 Selected clauses:', selectedClauses);

    closeModal('clausesModal');

    // Show confirmation notification
    if (selectedClauses.length > 0) {
        showNotification(`${selectedClauses.length} clause(s) selected for AI generation`, 'success');
    } else {
        showNotification('No clauses selected. Contract will be generated with default clauses.', 'warning');
    }
}

function getClauseSelections() {
    console.log('🔍 Getting clause selections for API...');

    // Map clause keys to detailed descriptions for better AI generation
    const clauseDescriptions = {
        "performance_bond": "Performance Bond - Contractor shall provide a performance bond as security",
        "retention_amount": "Retention Amount - Percentage of payment retained until completion",
        "payment_terms": "Payment Terms - Payment schedule and conditions",
        "timeline": "Timeline & Milestones - Project schedule and deliverables",
        "back_to_back": "Back-to-Back Terms - Terms flow down from main contract",
        "intellectual_property": "Intellectual Property Rights - Clear ownership and licensing terms",
        "non_compete": "Non-Compete - Restrictions on competing business activities",
        "data_protection": "Data Protection (GDPR) - Compliance with data protection regulations",
        "insurance": "Insurance Requirements - Comprehensive insurance coverage required",
        "liability": "Liability Limitation - Limits on liability exposure",
        "indemnification": "Indemnification - Protection against claims and losses",
        "force_majeure": "Force Majeure - Relief from obligations due to unforeseen events",
        "termination": "Termination Conditions - Conditions for ending the contract",
        "arbitration": "Arbitration Clause - Disputes resolved through arbitration",
        "mediation": "Mediation Clause - Mediation required before arbitration",
        "liquidated_damages": "Liquidated Damages - Pre-determined compensation for delays",
        "kpi": "Key Performance Indicators - Measurable performance metrics",
        "governing_law": "Governing Law - Applicable legal jurisdiction"
    };

    const clauseSelectionArray = [];

    if (selectedClauses && selectedClauses.length > 0) {
        selectedClauses.forEach(clauseKey => {
            clauseSelectionArray.push({
                key: clauseKey,
                enabled: true,
                description: clauseDescriptions[clauseKey] || `${clauseKey.replace('_', ' ').toUpperCase()} clause`
            });
            console.log(`  ✓ Preparing clause: ${clauseKey}`);
        });
    } else {
        console.warn(' No clauses selected by user');
    }

    console.log(`📊 Returning ${clauseSelectionArray.length} clauses for API`);
    console.log('📊 Clause data:', JSON.stringify(clauseSelectionArray, null, 2));

    return {
        selections: clauseSelectionArray,
        count: clauseSelectionArray.length
    };
}

function generateAIPrompt() {
    const selects = document.querySelectorAll('#aiPromptModal select');
    const inputs = document.querySelectorAll('#aiPromptModal input[type="text"]');
    const textarea = document.querySelector('#aiPromptModal textarea');

    if (selects.length >= 2 && inputs.length > 0 && textarea) {
        const contractType = selects[0].value;
        const duration = inputs[0].value;
        const paymentStructure = selects[1].value;
        const specialReq = textarea.value;

        const prompt = `Create a ${contractType} with the following details:
- Duration: ${duration}
- Payment Structure: ${paymentStructure}
- Special Requirements: ${specialReq}`;

        const aiPrompt = document.getElementById('aiPrompt');
        if (aiPrompt) {
            aiPrompt.value = prompt;
        }
    }

    closeModal('aiPromptModal');
}

// =====================================================
// Contract Creation Workflow
// =====================================================

async function proceedToNext() {
    console.log('🚀 proceedToNext called');
    console.log('Method:', selectedCreationMethod);
    console.log('Profile:', selectedProfile);
    console.log('Template:', selectedTemplate);
    console.log('File:', uploadedFile);
    console.log('Contract Type:', selectedContractType);

    try {
        // Prevent multiple clicks
        const proceedBtn = document.getElementById('proceedBtn');
        if (proceedBtn) {
            proceedBtn.disabled = true;
            proceedBtn.innerHTML = '<i class="ti ti-loader"></i> Processing...';
        }

        // Validate based on selected method
        if (selectedCreationMethod === 'template') {
            console.log('Validating template selection...');
            if (!selectedTemplate) {
                console.warn('No template selected');
                showNotification('Please select a template first', 'error');
                if (proceedBtn) {
                    proceedBtn.disabled = false;
                    proceedBtn.innerHTML = '<i class="ti ti-arrow-right"></i> Proceed to Editor';
                }
                return;
            }
            console.log(' Template validation passed');

        } else if (selectedCreationMethod === 'upload') {
            console.log('Validating file upload...');
            if (!uploadedFile) {
                console.warn('No file uploaded');
                showNotification('Please upload a contract file first', 'error');
                if (proceedBtn) {
                    proceedBtn.disabled = false;
                    proceedBtn.innerHTML = '<i class="ti ti-arrow-right"></i> Proceed to Editor';
                }
                return;
            }
            console.log(' Upload validation passed');

        } else if (selectedCreationMethod === 'ai') {
            console.log('Validating AI generation...');

            // Check contract type first
            if (!selectedContractType || selectedContractType === '') {
                console.warn('No contract type selected');
                showNotification('Please select a contract type first', 'error');
                if (proceedBtn) {
                    proceedBtn.disabled = false;
                    proceedBtn.innerHTML = '<i class="ti ti-arrow-right"></i> Proceed to Editor';
                }
                return;
            }

            // Build and validate prompt
            const fullPrompt = buildAIPrompt();
            if (!fullPrompt || fullPrompt.trim() === '') {
                console.warn('No AI requirements provided');
                showNotification('Please provide contract requirements', 'error');
                if (proceedBtn) {
                    proceedBtn.disabled = false;
                    proceedBtn.innerHTML = '<i class="ti ti-arrow-right"></i> Proceed to Editor';
                }
                return;
            }

            console.log(' AI validation passed');
            console.log('  Full prompt:', fullPrompt);
        }

        // Re-enable button before opening modal
        if (proceedBtn) {
            proceedBtn.disabled = false;
            proceedBtn.innerHTML = '<i class="ti ti-arrow-right"></i> Proceed to Editor';
        }

        // Open save contract modal
        console.log('📂 Opening save modal...');
        openModal('saveContractModal');
        console.log(' Modal opened');

    } catch (error) {
        console.error(' Error in proceedToNext:', error);

        // Re-enable button
        const proceedBtn = document.getElementById('proceedBtn');
        if (proceedBtn) {
            proceedBtn.disabled = false;
            proceedBtn.innerHTML = '<i class="ti ti-arrow-right"></i> Proceed to Editor';
        }

        showNotification('An error occurred: ' + error.message, 'error');
    }
}


// =====================================================
// Updated saveContract() Function with Loading Indicator
// Replace the existing saveContract() in contract-creation.js
// =====================================================

async function saveContract() {
    // Get the save button
    const saveButton = document.querySelector('#saveContractModal .btn-primary');
    const originalButtonHTML = '<i class="ti ti-device-floppy"></i> Save & Continue';

    try {
        console.log(' Starting contract save process...');
        console.log('Current method:', selectedCreationMethod);
        console.log('Selected template:', selectedTemplate);
        console.log('Uploaded file:', uploadedFile);

        // Get form elements
        const contractNameInput = document.getElementById('contractNameInput');
        const projectSelect = document.getElementById('projectSelect');
        const tagsInput = document.getElementById('tagsInput');

        if (!contractNameInput || !projectSelect) {
            console.error(' Form elements not found');
            showNotification('Form elements not found. Please refresh the page.', 'error');
            return;
        }

        const contractName = contractNameInput.value.trim();
        const projectId = projectSelect.value;
        const tags = tagsInput ? tagsInput.value.split(',').map(t => t.trim()).filter(Boolean) : [];

        // Validate
        if (!contractName) {
            showNotification('Please enter a contract name', 'error');
            contractNameInput.focus();
            return;
        }

        // 🔥 DISABLE BUTTON AND SHOW LOADING
        if (saveButton) {
            saveButton.disabled = true;
            saveButton.innerHTML = '<i class="ti ti-loader" style="animation: spin 1s linear infinite;"></i> Saving Contract...';
        }

        // Show loader overlay
        // showLoader('AI is writing your contract...This may take a while...');

        let contractId = null;

        // Handle different creation methods
        if (selectedCreationMethod === 'template' && selectedTemplate) {
            // Create from template
            console.log('📋 Creating from template:', selectedTemplate);
            contractId = await createContractFromTemplate(selectedTemplate);

        } else if (selectedCreationMethod === 'upload' && uploadedFile) {
            // Upload and create
            console.log(' Uploading contract file...');
            const formData = new FormData();
            formData.append('file', uploadedFile);
            formData.append('contract_title', contractName);
            formData.append('profile_type', selectedProfile);
            if (projectId && projectId !== 'create_new' && projectId !== '') {
                formData.append('project_id', projectId);
            }

            const response = await authenticatedFetch('/api/contracts/upload-contract', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to upload contract');
            }

            const result = await response.json();
            contractId = result.id || result.contract_id;

        } else if (selectedCreationMethod === 'ai') {
            // AI-generated contract - CREATE METADATA ONLY, STREAM CONTENT IN EDITOR
            console.log(' Creating AI-generated contract metadata...');

            // Gather all form data
            const contractValue = document.getElementById('contractValue')?.value;
            const currency = document.getElementById('currency')?.value || 'QAR';
            const startDate = document.getElementById('startDate')?.value;
            const endDate = document.getElementById('endDate')?.value;
            const paymentTerms = document.getElementById('paymentTerms')?.value;
            const partyAName = document.getElementById('partyAName')?.value || 'Party A';
            const partyBName = document.getElementById('partyBName')?.value || 'Party B';

            // Build AI prompt from modal if exists
            const aiPromptField = document.getElementById('aiPrompt');
            const additionalPrompt = aiPromptField ? aiPromptField.value : '';

            // Prepare comprehensive contract data for AI generation
            const contractData = {
                contract_title: contractName,
                contract_type: selectedContractType || 'service',
                profile_type: selectedProfile || 'contractor',
                parties: {
                    party_a: { name: partyAName },
                    party_b: { name: partyBName }
                },
                start_date: startDate,
                end_date: endDate,
                contract_value: contractValue ? parseFloat(contractValue) : null,
                currency: currency,
                selected_clauses: selectedClauses ?
                    (Array.isArray(selectedClauses) ?
                        selectedClauses.reduce((acc, clause) => {
                            if (typeof clause === 'object' && clause.key) {
                                acc[clause.key] = clause.enabled || false;
                            }
                            return acc;
                        }, {})
                        : selectedClauses
                    ) : {},
                jurisdiction: 'Qatar',
                language: 'en',
                project_id: projectId && projectId !== 'create_new' && projectId !== ''
                    ? parseInt(projectId)
                    : null,
                metadata: {
                    payment_terms: paymentTerms,
                    prompt: buildAIPrompt(),
                    additional_requirements: additionalPrompt,
                    tags: tags
                }
            };

            console.log('📤 Sending AI contract data:', contractData);

            const response = await authenticatedFetch('/api/contracts/ai-generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(contractData)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to create contract');
            }

            const result = await response.json();
            contractId = result.id || result.contract_id;

            console.log('✅ Contract metadata created with ID:', contractId);

            // Hide loader
            hideLoader();

            // Re-enable button
            if (saveButton) {
                saveButton.disabled = false;
                saveButton.innerHTML = originalButtonHTML;
            }

            // Close modal
            closeModal('saveContractModal');

            // Show success message
            showNotification('Contract created! Preparing AI generation...', 'success');

            // Redirect to editor - AI will auto-generate from database params
            setTimeout(() => {
                window.location.href = `/contract/editor?id=${contractId}`;
            }, 800);

            return contractId; // Stop here - streaming happens in editor

        } else {
            // Standard contract creation
            console.log(' Creating standard contract...');

            const contractData = {
                contract_title: contractName,
                contract_type: selectedContractType || 'general',
                profile_type: selectedProfile || 'contractor',
                template_id: selectedTemplate ? parseInt(selectedTemplate) : null,
                project_id: projectId && projectId !== 'create_new' && projectId !== ''
                    ? parseInt(projectId)
                    : null,
                tags: tags,
                status: 'draft'
            };

            console.log(' Sending contract data:', contractData);

            const response = await authenticatedFetch('/api/contracts/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(contractData)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to create contract');
            }

            const result = await response.json();
            contractId = result.id || result.contract_id;
        }

        // Verify we got a contract ID
        if (!contractId) {
            throw new Error('Contract created but no ID returned from server');
        }

        console.log(' Contract created with ID:', contractId);

        // Hide loader
        hideLoader();

        // 🔥 RE-ENABLE BUTTON AND RESTORE TEXT
        if (saveButton) {
            saveButton.disabled = false;
            saveButton.innerHTML = originalButtonHTML;
        }

        // Show success message
        showNotification('Contract saved successfully! Redirecting...', 'success');

        // Close modal
        closeModal('saveContractModal');

        // Redirect to contract editor
        setTimeout(() => {
            window.location.href = `/contract/edit/${contractId}`;
        }, 1000);

        return contractId;

    } catch (error) {
        console.error(' Error saving contract:', error);

        // Hide loader
        hideLoader();

        // 🔥 RE-ENABLE BUTTON AND RESTORE TEXT ON ERROR
        if (saveButton) {
            saveButton.disabled = false;
            saveButton.innerHTML = originalButtonHTML;
        }

        // Show error
        showNotification(error.message || 'Failed to save contract. Please try again.', 'error');

        return null;
    }
}


// =====================================================
// Project Select Change Handler
// =====================================================

function handleProjectSelectChange(event) {
    const selectedValue = event.target.value;

    console.log('📌 Project select changed:', selectedValue);

    if (selectedValue === 'create_new') {
        // Reset the select to empty
        event.target.value = '';

        // Open the create project modal
        openCreateProjectModal();
    }
}

// =====================================================
// Create Project Modal Functions
// =====================================================

function openCreateProjectModal() {
    console.log('🚀 Opening create project modal...');

    const modal = document.getElementById('createProjectModal');
    if (!modal) {
        console.error(' Create project modal not found');
        showNotification('Create project modal not found. Please refresh the page.', 'error');
        return;
    }

    // Reset form
    const form = document.getElementById('createProjectForm');
    if (form) {
        form.reset();
    }

    // Generate project code
    const projectCode = generateProjectCode();
    const projectCodeInput = document.getElementById('newProjectCode');
    if (projectCodeInput) {
        projectCodeInput.value = projectCode;
    }

    // Show modal
    modal.style.display = 'flex';

    // Focus on title input
    setTimeout(() => {
        const titleInput = document.getElementById('newProjectTitle');
        if (titleInput) {
            titleInput.focus();
        }
    }, 100);
}

function closeCreateProjectModal() {
    const modal = document.getElementById('createProjectModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function generateProjectCode() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const random = Math.floor(Math.random() * 1000).toString().padStart(3, '0');
    return `PRJ-${year}${month}-${random}`;
}

async function createNewProject() {
    try {
        console.log(' Creating new project...');

        const titleInput = document.getElementById('newProjectTitle');
        const codeInput = document.getElementById('newProjectCode');
        const descriptionInput = document.getElementById('newProjectDescription');

        if (!titleInput || !codeInput) {
            showNotification('Form elements not found', 'error');
            return;
        }

        const title = titleInput.value.trim();
        const code = codeInput.value.trim();
        const description = descriptionInput ? descriptionInput.value.trim() : '';

        // Validate
        if (!title) {
            showNotification('Please enter a project title', 'error');
            titleInput.focus();
            return;
        }

        if (!code) {
            showNotification('Please enter a project code', 'error');
            codeInput.focus();
            return;
        }

        showLoader('Creating project...');

        // Create project via API
        const response = await authenticatedFetch('/api/projects/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: title,
                code: code,
                description: description,
                status: 'planning'
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to create project');
        }

        const result = await response.json();
        console.log(' Project created:', result);

        hideLoader();
        showNotification('Project created successfully!', 'success');

        // Close create project modal
        closeCreateProjectModal();

        // Reload projects dropdown
        await loadProjects();

        // Auto-select the newly created project
        const projectSelect = document.getElementById('projectSelect');
        if (projectSelect && result.id) {
            projectSelect.value = result.id;
        }

    } catch (error) {
        hideLoader();
        showNotification('Error creating project: ' + error.message, 'error');
        console.error('Create project error:', error);
    }
}


async function createContractFromTemplate(templateId) {
    try {
        console.log(`📋 Creating contract from template ID: ${templateId}`);
        showLoader('Creating contract from template...');

        // Prepare contract data
        const contractData = {
            contract_title: document.getElementById('contractNameInput')?.value || `Contract from Template ${templateId}`,
            contract_type: 'general',
            profile_type: selectedProfile || 'contractor',
            template_id: parseInt(templateId),
            project_id: document.getElementById('projectSelect')?.value || null,
            tags: []
        };

        console.log(' Creating contract:', contractData);

        // Create the contract
        const response = await authenticatedFetch('/api/contracts/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(contractData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to create contract');
        }

        const result = await response.json();
        console.log(' Contract created:', result);

        // CRITICAL: Check for ID in response
        const contractId = result.id || result.contract?.id;

        if (!contractId) {
            console.error(' Response missing ID:', result);
            throw new Error('Contract created but no ID returned from server');
        }

        hideLoader();
        showNotification(`Contract created successfully! ID: ${contractId}`, 'success');

        // Redirect to edit page
        setTimeout(() => {
            window.location.href = `/contract/edit/${contractId}`;
        }, 1500);

        return contractId;

    } catch (error) {
        console.error(' Error creating contract from template:', error);
        hideLoader();
        showNotification(error.message || 'Failed to create contract', 'error');
        return null;
    }
}


async function proceedWithReview() {
    closeModal('importModal');
    showNotification('Starting AI review...', 'info');

    setTimeout(() => {
        window.location.href = `/contract/editor?mode=review`;
    }, 1000);
}

// =====================================================
// Utility Functions
// =====================================================

function showLoader(message = 'Please wait...') {
    hideLoader(); // Remove existing loader

    const loader = document.createElement('div');
    loader.id = 'contractLoader';
    loader.className = 'contract-loader';
    loader.innerHTML = `
        <div class="loader-content">
             <div class="ai-loader"></div>
            <p class="mt-3">${message}</p>
        </div>
    `;

    if (!document.getElementById('loaderStyles')) {
        const style = document.createElement('style');
        style.id = 'loaderStyles';
        style.textContent = `
            .contract-loader {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.5);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
            }
            .loader-content {
                background: white;
                padding: 30px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            .spinner-border {
                width: 3rem;
                height: 3rem;
                border-width: 0.3em;
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(loader);
}

function hideLoader() {
    const loader = document.getElementById('contractLoader');
    if (loader) {
        loader.remove();
    }
}

function showSuccess(message) {
    showNotification(message, 'success');
}

function showError(message) {
    showNotification(message, 'error');
}

function showWarning(message) {
    showNotification(message, 'warning');
}

function showNotification(message, type = 'info') {
    // Remove any existing notifications
    const existingNotifications = document.querySelectorAll('.contract-notification');
    existingNotifications.forEach(n => n.remove());

    const notification = document.createElement('div');
    notification.className = `contract-notification alert alert-${type} alert-dismissible fade show`;
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;

    if (!document.getElementById('notificationStyles')) {
        const style = document.createElement('style');
        style.id = 'notificationStyles';
        style.textContent = `
            .contract-notification {
                position: fixed;
                top: 20px;
                right: 20px;
                min-width: 300px;
                max-width: 500px;
                z-index: 10000;
                animation: slideIn 0.3s ease-out;
            }
            @keyframes slideIn {
                from {
                    transform: translateX(100%);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
        `;
        document.head.appendChild(style);
    }

    document.body.appendChild(notification);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 150);
    }, 5000);
}

function getNotificationIcon(type) {
    const icons = {
        success: 'check',
        error: 'alert-circle',
        warning: 'alert-triangle',
        info: 'info-circle'
    };
    return icons[type] || 'info-circle';
}

async function authenticatedFetch(url, options = {}) {
    const token = getAuthToken();

    const defaultOptions = {
        headers: {
            ...options.headers
        },
        credentials: 'include'
    };

    if (token && !defaultOptions.headers['Authorization']) {
        defaultOptions.headers['Authorization'] = `Bearer ${token}`;
    }

    // Don't set Content-Type for FormData
    if (options.body instanceof FormData) {
        delete defaultOptions.headers['Content-Type'];
    }

    return fetch(url, { ...defaultOptions, ...options });
}

function getAuthToken() {
    return localStorage.getItem('access_token') || sessionStorage.getItem('access_token') || '';
}

function debugClauseSelection() {
    console.log('🔍 CLAUSE SELECTION DEBUG');
    console.log('========================');
    console.log('1. Global selectedClauses:', selectedClauses);
    console.log('2. Checkboxes in modal:', document.querySelectorAll('#clausesModal input[type="checkbox"]').length);
    console.log('3. Checked checkboxes:', document.querySelectorAll('#clausesModal input[name^="clause_"]:checked').length);

    const checkedBoxes = document.querySelectorAll('#clausesModal input[name^="clause_"]:checked');
    console.log('4. Checked clause keys:');
    checkedBoxes.forEach(cb => {
        console.log('   -', cb.name.replace('clause_', ''));
    });

    console.log('5. getClauseSelections() result:', getClauseSelections());
    console.log('========================');
}



// =====================================================
// Global Exports
// =====================================================

window.contractCreation = {
    openClausesModal,
    applyClauseSelection,
    getClauseSelections,
    selectedClauses,
    handleContractTypeChange,
    toggleAiAssistant,
    hideAiAssistant,
    buildAIPrompt,
    handleProjectSelectChange,
    openCreateProjectModal,
    closeCreateProjectModal,
    createNewProject,
    generateProjectCode
};

window.openModal = openModal;
window.closeModal = closeModal;
window.switchTab = switchTab;
window.confirmProfile = confirmProfile;
window.useSelectedTemplate = useSelectedTemplate;
window.openClausesModal = openClausesModal;
window.openAIPromptModal = openAIPromptModal;
window.applyClauseSelection = applyClauseSelection;
window.generateAIPrompt = generateAIPrompt;
window.removeFile = removeFile;
window.proceedToNext = proceedToNext;
window.saveContract = saveContract;
window.createContractFromTemplate = createContractFromTemplate;
window.proceedWithReview = proceedWithReview;
window.debugClauseSelection = debugClauseSelection;
window.hideAiAssistant = hideAiAssistant;
window.toggleAiAssistant = toggleAiAssistant;
window.handleContractTypeChange = handleContractTypeChange;
window.handleProjectSelectChange = handleProjectSelectChange;
window.openCreateProjectModal = openCreateProjectModal;
window.closeCreateProjectModal = closeCreateProjectModal;
window.createNewProject = createNewProject;

console.log(' Contract creation script loaded successfully with AI Assistant');