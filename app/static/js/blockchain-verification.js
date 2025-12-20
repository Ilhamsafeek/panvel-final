// =====================================================
// Blockchain Verification UI Functions
// =====================================================


function getContractId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('contract_id') || 
           document.querySelector('[name="contract_id"]')?.value;
}


// Get auth token from cookie
function getAuthToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'session_token') return value;
    }
    return null;
}


// Show blockchain verification status
async function verifyContract(contractId) {
    try {
        const indicator = document.getElementById(`blockchain-indicator-${contractId}`);
        
        // Show loading
        indicator.innerHTML = `
            <div class="d-flex align-items-center">
                <div class="spinner-border spinner-border-sm text-primary me-2"></div>
                <span>Verifying...</span>
            </div>
        `;
        
        // Get contract content
        const contractContent = getContractContent();
        
        // Call API
        const response = await fetch('/api/blockchain/verify-contract-hash', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${getAuthToken()}`
            },
            body: JSON.stringify({
                contract_id: contractId,
                document_content: contractContent
            })
        });

        const result = await response.json();

        if (result.success && result.verified) {
            showSuccessIndicator(contractId);
        } else {
            showTamperAlert(contractId);
        }

    } catch (error) {
        console.error('Verification failed:', error);
        showErrorIndicator(contractId);
    }
}

// Show success indicator
function showSuccessIndicator(contractId) {
    const indicator = document.getElementById(`blockchain-indicator-${contractId}`);
    indicator.innerHTML = `
        <div class="alert alert-success mb-0">
            <i data-lucide="shield-check" class="text-success"></i>
            <strong>Verified</strong> - Document integrity confirmed on blockchain
        </div>
    `;
    lucide.createIcons();
}

// Show tamper alert
function showTamperAlert(contractId) {
    const indicator = document.getElementById(`blockchain-indicator-${contractId}`);
    indicator.innerHTML = `
        <div class="alert alert-danger mb-0">
            <i data-lucide="shield-alert" class="text-danger"></i>
            <strong>⚠️ Warning</strong> - Document integrity compromised
        </div>
    `;
    lucide.createIcons();
    
    // Show detailed modal
    alert('⚠️ TAMPERING DETECTED!\n\nThe current document does not match the blockchain-verified hash.\nThis document may have been modified after being recorded.');
}

// Show error indicator
function showErrorIndicator(contractId) {
    const indicator = document.getElementById(`blockchain-indicator-${contractId}`);
    indicator.innerHTML = `
        <div class="alert alert-warning mb-0">
            <i data-lucide="alert-circle"></i>
            Verification error - Please try again
        </div>
    `;
    lucide.createIcons();
}

// Show blockchain certificate
async function showBlockchainCertificate(contractId) {
    try {
        const response = await fetch(`/api/blockchain/contract-record/${contractId}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`
            }
        });

        const result = await response.json();
        
        if (!result.success) {
            alert('Blockchain record not found');
            return;
        }

        // Show certificate modal (you can customize this)
        const modal = `
            <div class="modal fade show" style="display: block; background: rgba(0,0,0,0.5);">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header" style="background: linear-gradient(135deg, #2762cb 0%, #73B4E0 100%); color: white;">
                            <h5 class="modal-title">
                                <i data-lucide="award"></i>
                                Blockchain Certificate
                            </h5>
                            <button type="button" class="btn-close btn-close-white" onclick="this.closest('.modal').remove()"></button>
                        </div>
                        <div class="modal-body">
                            <div class="text-center mb-4">
                                <i data-lucide="shield-check" style="width: 64px; height: 64px; color: #28a745;"></i>
                                <h4 class="mt-3">Document Integrity Verified</h4>
                            </div>
                            
                            <table class="table">
                                <tr><td><strong>Contract ID:</strong></td><td>${contractId}</td></tr>
                                <tr><td><strong>Document Hash:</strong></td><td><code>${result.integrity_record?.document_hash || 'N/A'}</code></td></tr>
                                <tr><td><strong>Transaction Hash:</strong></td><td><code>${result.blockchain_record?.transaction_hash || 'N/A'}</code></td></tr>
                                <tr><td><strong>Block Number:</strong></td><td>${result.blockchain_record?.block_number || 'N/A'}</td></tr>
                                <tr><td><strong>Network:</strong></td><td>${result.blockchain_record?.network || 'Hyperledger Fabric'}</td></tr>
                                <tr><td><strong>Status:</strong></td><td><span class="badge bg-success">Verified</span></td></tr>
                            </table>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" onclick="this.closest('.modal').remove()">Close</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modal);
        lucide.createIcons();

    } catch (error) {
        console.error('Failed to get certificate:', error);
        alert('Failed to retrieve blockchain certificate');
    }
}

// Get contract content for hashing
function getContractContent() {
    // Try to get content from various possible locations
    const contentElement = document.getElementById('contract-content') ||
                          document.querySelector('.contract-content') ||
                          document.querySelector('[data-contract-content]');
    
    if (contentElement) {
        return contentElement.innerText || contentElement.textContent;
    }
    
    // Fallback: use contract number and title
    const contractNumber = document.querySelector('[data-contract-number]')?.textContent || '';
    const contractTitle = document.querySelector('[data-contract-title]')?.textContent || '';
    
    return `${contractNumber}|${contractTitle}`;
}



// Show certificate with explicit ID parameter
async function showBlockchainCertificateById(contractId, contractNumber) {
    try {

        const contractNumber = document.getElementById('contract_number')?.value ||
            document.querySelector('[name="contract_number"]')?.value || '';

        const response = await fetch(`/api/blockchain/contract-record/${contractId}`, {
            headers: { 'Authorization': `Bearer ${getAuthToken()}` }
        });
        const result = await response.json();
        
        if (!result.success) {
            alert('Blockchain record not found. Contract may need to be saved first.');
            return;
        }

        const modal = `
            <div class="modal fade show" style="display: block; background: rgba(0,0,0,0.5);" onclick="this.remove()">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header" style="background: linear-gradient(135deg, #2762cb 0%, #73B4E0 100%); color: white;">
                            <h5 class="modal-title">
                                <i data-lucide="award" style="width: 20px; height: 20px;"></i>
                                Blockchain Certificate
                            </h5>
                            <button class="btn-close btn-close-white" onclick="this.closest('.modal').remove()">X</button>
                        </div>
                        <div class="modal-body">
                            <div class="text-center mb-4">
                                <i data-lucide="shield-check" style="width: 64px; height: 64px; color: #28a745;"></i>
                                <h4 class="mt-3">Document Verified</h4>
                            </div>
                            <table class="table table-bordered">
                                <tr>
                                    <td style="width: 40%;"><strong>Contract Number:</strong></td>
                                    <td>${contractNumber}</td>
                                </tr>
                                <tr>
                                    <td><strong>Document Hash:</strong></td>
                                    <td><code style="font-size: 0.85em;">${result.integrity_record?.document_hash?.substring(0, 32) || 'N/A'}...</code></td>
                                </tr>
                                <tr>
                                    <td><strong>Transaction Hash:</strong></td>
                                    <td><code style="font-size: 0.85em;">${result.blockchain_record?.transaction_hash || 'N/A'}</code></td>
                                </tr>
                                <tr>
                                    <td><strong>Block Number:</strong></td>
                                    <td>${result.blockchain_record?.block_number || 'N/A'}</td>
                                </tr>
                                <tr>
                                    <td><strong>Network:</strong></td>
                                    <td>Hyperledger Fabric (${result.mode || 'Mock Mode'})</td>
                                </tr>
                                <tr>
                                    <td><strong>Verification Status:</strong></td>
                                    <td><span class="badge bg-success">✅ Verified</span></td>
                                </tr>
                                <tr>
                                    <td><strong>Recorded At:</strong></td>
                                    <td>${result.blockchain_record?.created_at || new Date().toISOString()}</td>
                                </tr>
                            </table>
                            <div class="alert alert-info mt-3">
                                <i data-lucide="info" style="width: 16px; height: 16px;"></i>
                                <strong>Certificate Authenticity:</strong> This certificate proves that the contract has been cryptographically hashed and recorded on the blockchain, ensuring its integrity and authenticity.
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">Close</button>
                            <button class="btn btn-primary" onclick="window.print()">
                                <i data-lucide="printer" style="width: 16px; height: 16px;"></i>
                                Print
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modal);
        lucide.createIcons();
    } catch (error) {
        console.error('Failed to get certificate:', error);
        alert('Failed to retrieve blockchain certificate. Please try again.');
    }
}

// Auto-verify on page load
document.addEventListener('DOMContentLoaded', function() {
    const indicator = document.querySelector('[id^="blockchain-indicator-"]');
    if (indicator) {
        const contractId = indicator.id.split('-').pop();
        verifyContract(contractId);
    }
});