// =====================================================
// FILE: app/static/js/screens/drafting/SCR_013_contract_creation.js
// Contract Creation - Complete Version with Content Save Fix - RESOLVED
// =====================================================

const API_BASE = '/api/contracts';
const AI_API_BASE = '/api/ai';

// Global state
let selectedProfile = 'client';
let selectedTemplate = null;
let selectedCreationMethod = 'template';
let availableTemplates = [];
let isLoading = false;
let generatedContractContent = null; // Store the AI-generated content

// =====================================================
// Initialization
// =====================================================

document.addEventListener('DOMContentLoaded', function () {
    initializeContractCreation();
});

async function initializeContractCreation() {
    try {
        // Show loading
        showLoader('Initializing contract creation...');

        // Get profile from URL if provided
        const urlParams = new URLSearchParams(window.location.search);
        const profileParam = urlParams.get('profile');

        if (profileParam && ['client', 'consultant', 'contractor', 'sub_contractor'].includes(profileParam)) {
            selectedProfile = profileParam;
            setProfileSelection(profileParam);
        }

        // Bind event listeners
        bindEventListeners();

        // Load creation options and templates
        await loadCreationOptions();

        hideLoader();

    } catch (error) {
        hideLoader();
        showError('Failed to initialize contract creation: ' + error.message);
        console.error('Initialization error:', error);
    }
}

// =====================================================
// Event Listeners
// =====================================================

function bindEventListeners() {
    // Profile selection
    const profileRadios = document.querySelectorAll('input[name="profile"]');
    profileRadios.forEach(radio => {
        radio.addEventListener('change', handleProfileChange);
    });

    // Creation method selection
    const methodButtons = document.querySelectorAll('.creation-method-btn');
    methodButtons.forEach(button => {
        button.addEventListener('click', handleCreationMethodChange);
    });

    // Template selection
    document.addEventListener('click', handleTemplateSelection);

    // Form submissions
    const templateForm = document.getElementById('template-form');
    if (templateForm) {
        templateForm.addEventListener('submit', handleTemplateSubmission);
    }

    const uploadForm = document.getElementById('upload-form');
    if (uploadForm) {
        uploadForm.addEventListener('submit', handleUploadSubmission);
    }

    const aiForm = document.getElementById('ai-form');
    if (aiForm) {
        aiForm.addEventListener('submit', handleAISubmission);
    }

    // File upload handling
    const fileInput = document.getElementById('contract-file');
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelection);
    }

    // Generate Contract Button
    const generateBtn = document.getElementById('generateContractBtn');
    if (generateBtn) {
        generateBtn.addEventListener('click', generateContract);
    }

    // Save button in modal
    const saveBtn = document.querySelector('#saveContractModal .btn-primary');
    if (saveBtn) {
        saveBtn.addEventListener('click', saveContract);
    }
}

// =====================================================
// Event Handlers
// =====================================================

async function handleProfileChange(event) {
    const newProfile = event.target.value;
    if (newProfile !== selectedProfile) {
        selectedProfile = newProfile;

        try {
            showLoader('Loading templates for ' + newProfile + '...');
            await loadCreationOptions();
            hideLoader();
        } catch (error) {
            hideLoader();
            showError('Failed to load templates: ' + error.message);
        }
    }
}

function handleCreationMethodChange(event) {
    const methodButton = event.target.closest('.creation-method-btn');
    if (!methodButton) return;

    const method = methodButton.dataset.method;
    if (method !== selectedCreationMethod) {
        selectedCreationMethod = method;

        // Update active states
        document.querySelectorAll('.creation-method-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        methodButton.classList.add('active');

        // Show appropriate form
        showCreationForm(method);
    }
}

function handleTemplateSelection(event) {
    const templateCard = event.target.closest('.template-card');
    if (!templateCard) return;

    const templateId = templateCard.dataset.templateId;
    const templateData = availableTemplates.find(t => t.id == templateId);

    if (templateData) {
        // Update selection
        document.querySelectorAll('.template-card').forEach(card => {
            card.classList.remove('selected');
        });
        templateCard.classList.add('selected');

        selectedTemplate = templateData;

        // Show template details
        displayTemplateDetails(templateData);

        // Enable proceed button
        const proceedBtn = document.getElementById('proceed-with-template');
        if (proceedBtn) {
            proceedBtn.disabled = false;
        }
    }
}

async function handleTemplateSubmission(event) {
    event.preventDefault();

    if (!selectedTemplate) {
        showError('Please select a template first');
        return;
    }

    try {
        const formData = new FormData(event.target);
        const contractData = {
            contract_title: formData.get('contract_title') || `${selectedTemplate.name} Contract`,
            profile_type: selectedProfile,
            contract_type: selectedTemplate.type,
            contract_value: formData.get('contract_value') ? parseFloat(formData.get('contract_value')) : null,
            currency: formData.get('currency') || 'QAR',
            start_date: formData.get('start_date'),
            end_date: formData.get('end_date')
        };

        const result = await createContractFromTemplate(selectedTemplate.id, contractData);
        console.log('Contract created:', result);

    } catch (error) {
        showError('Failed to create contract: ' + error.message);
    }
}

async function handleUploadSubmission(event) {
    event.preventDefault();

    const fileInput = document.getElementById('contract-file');
    if (!fileInput || !fileInput.files[0]) {
        showError('Please select a file to upload');
        return;
    }

    try {
        const formData = new FormData(event.target);
        const contractData = {
            contract_title: formData.get('contract_title'),
            profile_type: selectedProfile
        };

        const result = await uploadContract(fileInput.files[0], contractData);
        console.log('Contract uploaded:', result);

    } catch (error) {
        showError('Failed to upload contract: ' + error.message);
    }
}

async function handleAISubmission(event) {
    event.preventDefault();

    try {
        const formData = new FormData(event.target);
        const contractData = {
            contract_title: formData.get('contract_title'),
            contract_type: formData.get('contract_type'),
            profile_type: selectedProfile,
            contract_value: formData.get('contract_value') ? parseFloat(formData.get('contract_value')) : null,
            currency: formData.get('currency') || 'QAR',
            start_date: formData.get('start_date'),
            end_date: formData.get('end_date'),
            party_1_name: formData.get('party_1_name'),
            party_2_name: formData.get('party_2_name'),
            key_terms: formData.get('key_terms')
        };

        const result = await generateContractWithAI(contractData);
        console.log('AI Contract generated:', result);

    } catch (error) {
        showError('Failed to generate contract: ' + error.message);
    }
}

function handleFileSelection(event) {
    const file = event.target.files[0];
    if (file) {
        // Show file details
        const fileInfo = document.getElementById('file-info');
        if (fileInfo) {
            fileInfo.innerHTML = `
                <div class="alert alert-info">
                    <i class="ti ti-file"></i> Selected: ${file.name}
                    <br>Size: ${(file.size / 1024 / 1024).toFixed(2)} MB
                </div>
            `;
        }
    }
}

// =====================================================
// API Integration
// =====================================================

async function loadCreationOptions() {
    try {
        const response = await fetch(`${API_BASE}/creation-options?profile_type=${selectedProfile}`, {
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`Failed to load options: ${response.status}`);
        }

        const data = await response.json();

        // Update templates
        availableTemplates = data.template_categories?.[selectedProfile] || [];
        updateTemplateDisplay();

        // Update creation methods if needed
        if (data.creation_methods) {
            updateCreationMethods(data.creation_methods);
        }

        // Update AI capabilities info
        if (data.ai_capabilities) {
            updateAICapabilities(data.ai_capabilities);
        }

    } catch (error) {
        console.error('Error loading creation options:', error);
        // Don't throw, just log - allow page to work with defaults
    }
}

async function createContractFromTemplate(templateId, contractData) {
    try {
        showLoader('Creating contract from template...');

        const response = await fetch(`${API_BASE}/create-from-template`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                template_id: templateId,
                contract_data: contractData
            })
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Creation failed: ${response.status}`);
        }

        const result = await response.json();

        hideLoader();
        showSuccess('Contract created successfully!');

        // Redirect to contract editor
        setTimeout(() => {
            window.location.href = `/contracts/edit/${result.id}`;
        }, 1500);

        return result;

    } catch (error) {
        hideLoader();
        throw error;
    }
}

async function uploadContract(file, contractData) {
    try {
        showLoader('Uploading and analyzing contract...');

        const formData = new FormData();
        formData.append('file', file);
        formData.append('contract_data', JSON.stringify(contractData));

        const response = await fetch(`${API_BASE}/upload-contract`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`
            },
            body: formData
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `Upload failed: ${response.status}`);
        }

        const result = await response.json();

        hideLoader();
        showSuccess('Contract uploaded and analyzed successfully!');

        // Show AI analysis results
        displayAIResults(result.ai_analysis);

        // Redirect to contract editor
        setTimeout(() => {
            window.location.href = `/contracts/edit/${result.id}`;
        }, 2000);

        return result;

    } catch (error) {
        hideLoader();
        throw error;
    }
}

async function generateContractWithAI(contractData) {
    try {
        showLoader('AI is crafting your contract...');

        const response = await fetch(`${AI_API_BASE}/generate-contract`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(contractData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || `AI generation failed: ${response.status}`);
        }

        const result = await response.json();

        hideLoader();
        showSuccess('Contract generated successfully!');

        // Show AI generation results
        displayAIResults(result.ai_result);

        // Redirect to contract editor
        setTimeout(() => {
            window.location.href = `/contracts/edit/${result.contract.id}`;
        }, 2000);

        return result;

    } catch (error) {
        hideLoader();
        throw error;
    }
}

// =====================================================
// AI Contract Generation (Fixed for Content Save with Clauses)
// =====================================================

async function generateContract() {
    try {
        console.log('🤖 Starting AI contract generation...');
        showLoader('AI is generating your contract...');

        // Get contract details
        const contractTitle = document.getElementById('contractTitle')?.value ||
            document.querySelector('input[placeholder*="contract title"]')?.value;
        const contractType = document.getElementById('contractType')?.value ||
            document.querySelector('select')?.value;
        const startDate = document.getElementById('startDate')?.value;
        const endDate = document.getElementById('endDate')?.value;
        const contractValue = document.getElementById('contractValue')?.value;
        const parties = gatherPartyInformation();

        // Validate required fields
        if (!contractTitle) {
            hideLoader();
            showError('Please enter a contract title');
            return;
        }

        // Get clause selections - INTEGRATED FROM DEVELOP
        const clauseData = getClauseSelections();

        console.log('📋 Clause selections:', clauseData.selections);
        console.log('📋 Number of clauses selected:', clauseData.count);

        // Prepare AI request with clause support
        const requestData = {
            contract_title: contractTitle,
            contract_type: contractType || selectedTemplate || 'Service Agreement',
            profile_type: selectedProfile,
            parties: parties,
            start_date: startDate,
            end_date: endDate,
            contract_value: contractValue ? parseFloat(contractValue) : null,
            currency: 'QAR',
            selected_clauses: clauseData.selections,      // ✅ INCLUDED
            clause_descriptions: clauseData.descriptions,  // ✅ FOR AI CONTEXT
            jurisdiction: 'Qatar',
            language: 'en'
        };

        console.log('📤 Sending request to AI endpoint:', requestData);

        // Call AI generation endpoint (using correct API_BASE)
        const response = await fetch(`${API_BASE}/ai-generate`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getAuthToken()}`
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to generate contract');
        }

        const result = await response.json();
        console.log('✅ AI Contract generated successfully:', result);

        // Store the generated content - CRITICAL FIX
        generatedContractContent = result.contract_content ||
            result.contract_body ||
            result.ai_result?.contract_text ||
            result.content;

        if (!generatedContractContent) {
            hideLoader();
            showError('AI generated a response but no contract content was returned.');
            console.error('Response structure:', result);
            return;
        }

        console.log('✅ Contract content stored:', generatedContractContent.substring(0, 200) + '...');

        // Display the generated contract
        displayContractPreview(generatedContractContent);

        hideLoader();
        showSuccess('Contract generated successfully! Review and save when ready.');

        // Show the save contract modal after a brief delay
        setTimeout(() => {
            openSaveContractModal();
        }, 1000);

        return result;

    } catch (error) {
        hideLoader();
        showError('Error generating contract: ' + error.message);
        console.error('Generation error:', error);
    }
}

// =====================================================
// Clause Selection Helper
// =====================================================

function getClauseSelections() {
    const selections = [];
    const descriptions = [];

    // Find all checked clause checkboxes
    const checkedClauses = document.querySelectorAll('input[type="checkbox"][name^="clause_"]:checked');

    checkedClauses.forEach(checkbox => {
        const clauseKey = checkbox.name.replace('clause_', '');
        const clauseLabel = checkbox.closest('label')?.textContent?.trim() || clauseKey;

        selections.push({
            key: clauseKey,
            enabled: true,
            label: clauseLabel
        });

        descriptions.push(clauseLabel);

        console.log('✓ Selected clause:', clauseKey, '-', clauseLabel);
    });

    return {
        selections: selections,
        descriptions: descriptions,
        count: selections.length
    };
}

// =====================================================
// Project Management
// =====================================================

async function populateProjectDropdown() {
    console.log('📋 Populating project dropdown...');

    const projectSelect = document.querySelector('#saveContractModal select');
    if (!projectSelect) {
        console.error('❌ Project select element not found');
        return;
    }

    projectSelect.disabled = true;
    projectSelect.innerHTML = '<option value="">Loading projects...</option>';

    try {
        // Fetch projects from API
        const response = await fetch('/api/projects/list', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch projects: ${response.status}`);
        }

        const data = await response.json();
        console.log('📊 Fetched projects:', data);

        // Clear loading option
        projectSelect.innerHTML = '';

        // Add default option
        const defaultOption = document.createElement('option');
        defaultOption.value = '';
        defaultOption.textContent = 'Select a project';
        projectSelect.appendChild(defaultOption);

        // Check if we have projects
        const projects = Array.isArray(data) ? data : (data.projects || []);

        if (projects && projects.length > 0) {
            projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.id;

                const projectCode = project.project_code || project.code || '';
                const projectTitle = project.project_name || project.name || 'Untitled Project';

                option.textContent = projectCode ? `${projectCode} - ${projectTitle}` : projectTitle;

                projectSelect.appendChild(option);

                console.log('✅ Added project:', option.textContent);
            });

            // Add "Create New Project" option
            const createNewOption = document.createElement('option');
            createNewOption.value = 'create_new';
            createNewOption.textContent = '+ Create New Project...';
            createNewOption.style.fontWeight = '600';
            createNewOption.style.color = 'var(--primary-color)';
            projectSelect.appendChild(createNewOption);

            console.log('✅ Project dropdown populated successfully');
        } else {
            // No projects found
            const noProjectsOption = document.createElement('option');
            noProjectsOption.value = 'create_new';
            noProjectsOption.textContent = 'No projects found - Create New Project';
            noProjectsOption.style.color = 'var(--warning-color)';
            projectSelect.appendChild(noProjectsOption);

            console.warn('⚠️ No projects found in database');
        }

    } catch (error) {
        console.error('❌ Error loading projects:', error);
        projectSelect.innerHTML = '<option value="">Error loading projects</option>';

        const errorOption = document.createElement('option');
        errorOption.value = 'create_new';
        errorOption.textContent = '+ Create New Project...';
        errorOption.style.color = 'var(--primary-color)';
        projectSelect.appendChild(errorOption);
    }

    projectSelect.disabled = false;

    // 🔥 ADD EVENT LISTENER - Add this at the end
    projectSelect.removeEventListener('change', handleProjectSelectChange);
    projectSelect.addEventListener('change', handleProjectSelectChange);
}

// =====================================================
// Save Contract (FIXED to Save Content)
// =====================================================

async function saveContract() {
    try {
        console.log('💾 Saving contract with content...');

        // Get form values
        const contractNameInput = document.querySelector('#saveContractModal input[type="text"]');
        const projectSelect = document.querySelector('#saveContractModal select');
        const tagsInputs = document.querySelectorAll('#saveContractModal input[type="text"]');
        const tagsInput = tagsInputs.length > 1 ? tagsInputs[1] : null;

        if (!contractNameInput || !projectSelect) {
            console.error('❌ Form elements not found');
            showError('Form elements not found. Please refresh the page.');
            return;
        }

        const contractName = contractNameInput.value.trim();
        const projectId = projectSelect.value;
        const tags = tagsInput ? tagsInput.value.split(',').map(tag => tag.trim()).filter(Boolean) : [];

        // Validate inputs
        if (!contractName) {
            showError('Please enter a contract name');
            return;
        }

        // if (!projectId || projectId === '') {
        //     showError('Please select a project');
        //     return;
        // }

        // Check if we have generated content - CRITICAL CHECK
        if (!generatedContractContent) {
            showError('No contract content to save. Please generate a contract first.');
            return;
        }

        showLoader('AI is writing your contract...This may take a while');

        // Prepare contract data
        const contractData = {
            contract_title: contractName,
            contract_type: selectedTemplate || 'Service Agreement',
            profile_type: selectedProfile,
            project_id: projectId && projectId !== 'create_new' && projectId !== ''
                ? parseInt(projectId)
                : null,
            template_id: null,
            status: 'draft',
            tags: tags,
            // Get dates and value from form if available
            start_date: document.getElementById('startDate')?.value || null,
            end_date: document.getElementById('endDate')?.value || null,
            contract_value: document.getElementById('contractValue')?.value ?
                parseFloat(document.getElementById('contractValue').value) : null,
            currency: 'QAR'
        };

        console.log('📤 Creating contract record:', contractData);

        // Step 1: Create the contract record
        const createResponse = await fetch(`${API_BASE}/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getAuthToken()}`
            },
            body: JSON.stringify(contractData)
        });

        if (!createResponse.ok) {
            const error = await createResponse.json();
            throw new Error(error.detail || 'Failed to create contract');
        }

        const createdContract = await createResponse.json();
        console.log('✅ Contract record created:', createdContract);

        // Step 2: CRITICAL - Save the actual contract content as a version
        const contentData = {
            content: generatedContractContent,  // The actual AI-generated HTML/text content
            version_type: 'draft',
            change_summary: 'Initial AI-generated contract'
        };

        console.log('📤 Saving contract content to database...');
        console.log('Content length:', generatedContractContent.length, 'characters');

        const contentResponse = await fetch(`${API_BASE}/${createdContract.id}/content`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getAuthToken()}`
            },
            body: JSON.stringify(contentData)
        });

        if (!contentResponse.ok) {
            const error = await contentResponse.json();
            console.error('Failed to save contract content:', error);
            // Don't throw here, contract is created but content save failed
            showWarning('Contract created but content save failed. Please try editing the contract.');
        } else {
            const contentResult = await contentResponse.json();
            console.log('✅ Contract content saved successfully:', contentResult);
            console.log('Version number:', contentResult.version_number);
            console.log('Content length saved:', contentResult.content_length);
        }

        hideLoader();
        showSuccess(`Contract "${contractName}" saved successfully!`);

        // Close modal
        closeSaveContractModal();

        // Clear the generated content
        generatedContractContent = null;

        // Redirect to contract editor
        setTimeout(() => {
            window.location.href = `/contract/edit/${createdContract.id}`;
        }, 1500);

        return createdContract;

    } catch (error) {
        hideLoader();
        showError('Error saving contract: ' + error.message);
        console.error('Save error:', error);
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
        console.error('❌ Create project modal not found');
        showError('Create project modal not found. Please refresh the page.');
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
        console.log('📝 Creating new project...');
        
        const titleInput = document.getElementById('newProjectTitle');
        const codeInput = document.getElementById('newProjectCode');
        const descriptionInput = document.getElementById('newProjectDescription');
        
        if (!titleInput || !codeInput) {
            showError('Form elements not found');
            return;
        }
        
        const title = titleInput.value.trim();
        const code = codeInput.value.trim();
        const description = descriptionInput ? descriptionInput.value.trim() : '';
        
        // Validate
        if (!title) {
            showError('Please enter a project title');
            titleInput.focus();
            return;
        }
        
        if (!code) {
            showError('Please enter a project code');
            codeInput.focus();
            return;
        }
        
        showLoader('Creating project...');
        
        // Create project via API
        const response = await fetch('/api/projects/', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`,
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
        console.log('✅ Project created:', result);
        
        hideLoader();
        showSuccess('Project created successfully!');
        
        // Close create project modal
        closeCreateProjectModal();
        
        // Reload projects dropdown
        await populateProjectDropdown();
        
        // Auto-select the newly created project
        const projectSelect = document.querySelector('#saveContractModal select');
        if (projectSelect && result.id) {
            projectSelect.value = result.id;
        }
        
    } catch (error) {
        hideLoader();
        showError('Error creating project: ' + error.message);
        console.error('Create project error:', error);
    }
}
// =====================================================
// Modal Functions
// =====================================================

function openSaveContractModal() {
    console.log('🚀 Opening save contract modal...');

    // Make sure we have content to save
    if (!generatedContractContent) {
        showError('Please generate a contract first before saving.');
        return;
    }

    // Populate projects when modal opens
    populateProjectDropdown();

    const modal = document.getElementById('saveContractModal');
    if (modal) {
        modal.style.display = 'flex';

        // Focus on contract name input
        setTimeout(() => {
            const contractNameInput = document.querySelector('#saveContractModal input[type="text"]');
            if (contractNameInput) {
                contractNameInput.focus();
            }
        }, 100);
    } else {
        console.error('❌ Save contract modal not found');
    }
}

function closeSaveContractModal() {
    const modal = document.getElementById('saveContractModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// =====================================================
// Display Functions
// =====================================================

function displayContractPreview(content) {
    console.log('👁️ Displaying contract preview...');

    // Find or create preview container
    let previewContainer = document.getElementById('contractPreview');
    if (!previewContainer) {
        previewContainer = document.querySelector('.contract-preview');
    }
    if (!previewContainer) {
        previewContainer = document.querySelector('.preview-section');
    }

    if (previewContainer) {
        // Set the content
        previewContainer.innerHTML = `
            <div class="contract-document">
                <div class="contract-header">
                    <h2>${selectedTemplate || 'Service Agreement'}</h2>
                    <span class="badge badge-warning">AI Generated - Draft</span>
                </div>
                <div class="contract-body">
                    ${content}
                </div>
                <div class="contract-footer">
                    <p class="text-muted">Generated on ${new Date().toLocaleString()}</p>
                </div>
            </div>
        `;

        // Show the preview container
        previewContainer.style.display = 'block';

        // Scroll to preview
        previewContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
        console.warn('⚠️ No preview container found, creating modal...');
        showContractInModal(content);
    }
}

function showContractInModal(content) {
    // Create a modal to show the contract
    const modal = document.createElement('div');
    modal.className = 'modal fade show';
    modal.style.display = 'block';
    modal.style.backgroundColor = 'rgba(0,0,0,0.5)';
    modal.innerHTML = `
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Generated Contract Preview</h5>
                    <button type="button" class="btn-close" onclick="this.closest('.modal').remove()"></button>
                </div>
                <div class="modal-body" style="max-height: 70vh; overflow-y: auto;">
                    ${content}
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="this.closest('.modal').remove()">Close</button>
                    <button type="button" class="btn btn-primary" onclick="openSaveContractModal()">
                        <i class="ti ti-device-floppy"></i> Save Contract
                    </button>
                </div>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function displayTemplateDetails(templateData) {
    const detailsContainer = document.getElementById('template-details');
    if (detailsContainer) {
        detailsContainer.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <h5>${templateData.name}</h5>
                    <p>${templateData.description || 'No description available'}</p>
                    <div class="mt-3">
                        <span class="badge bg-primary">${templateData.category || 'General'}</span>
                        <span class="badge bg-secondary">${templateData.type}</span>
                    </div>
                </div>
            </div>
        `;
    }
}

function displayAIResults(aiResults) {
    if (!aiResults) return;

    const resultsContainer = document.getElementById('ai-results');
    if (resultsContainer) {
        resultsContainer.innerHTML = `
            <div class="alert alert-success">
                <h5>AI Analysis Complete</h5>
                <p>Contract has been analyzed and processed successfully.</p>
                ${aiResults.summary ? `<p>Summary: ${aiResults.summary}</p>` : ''}
                ${aiResults.risk_score ? `<p>Risk Score: ${aiResults.risk_score}/100</p>` : ''}
            </div>
        `;
        resultsContainer.style.display = 'block';
    }
}

function updateTemplateDisplay() {
    const container = document.getElementById('template-container');
    if (!container) return;

    container.innerHTML = '';

    availableTemplates.forEach(template => {
        const card = document.createElement('div');
        card.className = 'col-md-4 mb-3';
        card.innerHTML = `
            <div class="template-card card" data-template-id="${template.id}">
                <div class="card-body">
                    <h6>${template.name}</h6>
                    <p class="small text-muted">${template.description || ''}</p>
                    <span class="badge bg-info">${template.category}</span>
                </div>
            </div>
        `;
        container.appendChild(card);
    });
}

function updateCreationMethods(methods) {
    // Update creation method buttons if needed
    console.log('Creation methods:', methods);
}

function updateAICapabilities(capabilities) {
    // Update AI capabilities display if needed
    console.log('AI capabilities:', capabilities);
}

function showCreationForm(method) {
    // Hide all forms
    document.querySelectorAll('.creation-form').forEach(form => {
        form.style.display = 'none';
    });

    // Show selected form
    const formId = `${method}-form`;
    const form = document.getElementById(formId);
    if (form) {
        form.style.display = 'block';
    }
}

function setProfileSelection(profile) {
    // Update radio buttons
    const radio = document.querySelector(`input[name="profile"][value="${profile}"]`);
    if (radio) {
        radio.checked = true;
    }

    // Update any profile-specific UI elements
    document.querySelectorAll('[data-profile]').forEach(element => {
        element.style.display = element.dataset.profile === profile ? 'block' : 'none';
    });
}

// =====================================================
// Helper Functions
// =====================================================

function gatherPartyInformation() {
    const parties = [];

    // Get party 1 (Company/Initiator)
    const party1Name = document.getElementById('party1Name')?.value ||
        document.querySelector('input[placeholder*="company name"]')?.value;
    const party1Email = document.getElementById('party1Email')?.value;

    if (party1Name) {
        parties.push({
            party_type: 'initiator',
            party_name: party1Name,
            party_email: party1Email,
            is_primary: true
        });
    }

    // Get party 2 (Counterparty)
    const party2Name = document.getElementById('party2Name')?.value ||
        document.querySelector('input[placeholder*="counterparty"]')?.value;
    const party2Email = document.getElementById('party2Email')?.value;

    if (party2Name) {
        parties.push({
            party_type: 'counterparty',
            party_name: party2Name,
            party_email: party2Email,
            is_primary: false
        });
    }

    return parties;
}

function getAuthToken() {
    return localStorage.getItem('access_token') || sessionStorage.getItem('access_token') || '';
}

// =====================================================
// UI Notification Functions
// =====================================================

function showLoader(message = 'Loading...') {
    const loader = document.getElementById('loader');
    if (loader) {
        loader.style.display = 'flex';
        const loaderText = loader.querySelector('.loader-text');
        if (loaderText) {
            loaderText.textContent = message;
        }
    } else {
        // Create a simple loader if it doesn't exist
        const loaderDiv = document.createElement('div');
        loaderDiv.id = 'loader';
        loaderDiv.className = 'loader-overlay';
        loaderDiv.innerHTML = `
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">${message}</span>
            </div>
            <div class="loader-text mt-2">${message}</div>
        `;
        document.body.appendChild(loaderDiv);
    }
}

function hideLoader() {
    const loader = document.getElementById('loader');
    if (loader) {
        loader.style.display = 'none';
    }
}

function showSuccess(message) {
    const alertContainer = document.getElementById('alertContainer') || createAlertContainer();
    const alert = document.createElement('div');
    alert.className = 'alert alert-success alert-dismissible fade show';
    alert.innerHTML = `
        <i class="ti ti-check"></i> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    alertContainer.appendChild(alert);

    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

function showError(message) {
    const alertContainer = document.getElementById('alertContainer') || createAlertContainer();
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show';
    alert.innerHTML = `
        <i class="ti ti-x"></i> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    alertContainer.appendChild(alert);

    // Auto-dismiss after 7 seconds
    setTimeout(() => {
        alert.remove();
    }, 7000);
}

function showWarning(message) {
    const alertContainer = document.getElementById('alertContainer') || createAlertContainer();
    const alert = document.createElement('div');
    alert.className = 'alert alert-warning alert-dismissible fade show';
    alert.innerHTML = `
        <i class="ti ti-alert-triangle"></i> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    alertContainer.appendChild(alert);

    // Auto-dismiss after 6 seconds
    setTimeout(() => {
        alert.remove();
    }, 6000);
}

function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alertContainer';
    container.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        max-width: 400px;
    `;
    document.body.appendChild(container);
    return container;
}

// =====================================================
// Utility Functions
// =====================================================

function bindButton(buttonId, callback) {
    const button = document.getElementById(buttonId);
    if (button) {
        button.addEventListener('click', callback);
    }
}

function formatDate(date) {
    if (!date) return '';
    const d = new Date(date);
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
}

function formatCurrency(amount, currency = 'QAR') {
    if (!amount) return '';
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

// =====================================================
// Export functions for use in other modules
// =====================================================

window.contractCreation = {
    generateContract,
    saveContract,
    openSaveContractModal,
    closeSaveContractModal,
    loadCreationOptions,
    createContractFromTemplate,
    uploadContract,
    generateContractWithAI,
    populateProjectDropdown,
    getClauseSelections
};

console.log('✅ SCR_013 Contract Creation script loaded successfully');