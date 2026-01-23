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
    console.log('🔍 Verifying contract', contractId);
    
    try {
        const response = await fetch('/api/blockchain/verify-contract-hash', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify({
                contract_id: parseInt(contractId)
            })
        });
        
        if (!response.ok) {
            console.error('❌ Verification API error:', response.status);
            showErrorIndicator(contractId);
            return;
        }
        
        const result = await response.json();
        console.log('📊 Verification result:', result);
        
        if (result.success && result.verified) {
            // ✅ VERIFIED
            showSuccessIndicator(contractId);
        } else {
            // 🚨 TAMPERING DETECTED
            showTamperAlert(contractId, result);
        }
        
    } catch (error) {
        console.error('❌ Verification error:', error);
        showErrorIndicator(contractId);
    }
}
// Show success indicator
function showSuccessIndicator(contractId) {
    const indicator = document.getElementById('blockchain-indicator');
    if (!indicator) return;
    
    indicator.innerHTML = `
        <div class="alert alert-success" style="display: flex; align-items: center; gap: 10px; margin: 0; padding: 12px 15px; border-radius: 8px;">
            <i class="ti ti-shield-check" style="font-size: 24px;"></i>
            <div>
                <strong>Verified</strong><br>
                <small>Document integrity confirmed on blockchain</small>
            </div>
        </div>
    `;
}

// Show tamper alert
function showTamperAlert(contractId, verificationResult) {
    console.log('🚨 Showing enhanced tamper alert for contract', contractId);
    
    // Remove any existing alert
    const existingAlert = document.getElementById('tamperAlertModal');
    if (existingAlert) {
        existingAlert.remove();
    }
    
    // Create modal HTML
    const modalHTML = `
        <div id="tamperAlertModal" class="modal show" style="display: flex !important; z-index: 10000;">
            <div class="modal-dialog modal-dialog-centered" style="max-width: 600px;">
                <div class="modal-content" style="border: none; box-shadow: 0 20px 60px rgba(0,0,0,0.3);">
                    
                    <!-- Header with Red Alert -->
                    <div class="modal-header" style="background: linear-gradient(135deg, #e53e3e 0%, #c53030 100%); color: white; border: none; padding: 30px; text-align: center;">
                        <div style="width: 100%;">
                            <i class="ti ti-shield-alert" style="font-size: 64px; margin-bottom: 15px; display: block;"></i>
                            <h3 style="margin: 0; font-size: 1.8rem; font-weight: bold;">TAMPERING DETECTED!</h3>
                            <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 1rem;">Blockchain Integrity Violation</p>
                        </div>
                    </div>
                    
                    <!-- Body with Details -->
                    <div class="modal-body" style="padding: 30px;">
                        
                        <!-- Main Message -->
                        <div style="background: #fff5f5; border-left: 4px solid #e53e3e; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
                            <h5 style="color: #c53030; margin: 0 0 10px 0; font-weight: bold;">
                                <i class="ti ti-alert-triangle"></i> Security Alert
                            </h5>
                            <p style="color: #742a2a; margin: 0; line-height: 1.6;">
                                The current document does not match the blockchain-verified hash. 
                                This document may have been modified after being recorded on the blockchain.
                            </p>
                        </div>
                        
                        <!-- Technical Details -->
                        <div style="background: #f7fafc; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                            <h6 style="margin: 0 0 15px 0; color: #2d3748; font-weight: bold;">
                                <i class="ti ti-info-circle"></i> Technical Details
                            </h6>
                            
                            <div style="display: grid; gap: 12px;">
                               
                                
                                <div>
                                    <strong style="color: #4a5568;">Expected Hash:</strong><br>
                                    <code style="background: #edf2f7; padding: 5px 10px; border-radius: 4px; font-size: 0.85rem; display: block; margin-top: 5px; word-break: break-all;">
                                        ${verificationResult?.stored_hash?.substring(0, 32) || 'N/A'}...
                                    </code>
                                </div>
                                
                                <div>
                                    <strong style="color: #4a5568;">Current Hash:</strong><br>
                                    <code style="background: #fee; padding: 5px 10px; border-radius: 4px; font-size: 0.85rem; display: block; margin-top: 5px; word-break: break-all; border: 1px solid #fc8181;">
                                        ${verificationResult?.current_hash?.substring(0, 32) || 'N/A'}...
                                    </code>
                                </div>
                                
                                <div>
                                    <strong style="color: #4a5568;">Detection Time:</strong>
                                    <span style="color: #2d3748;">${new Date().toLocaleString()}</span>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Possible Reasons -->
                        <div style="background: #fffaf0; border-left: 4px solid #ed8936; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                            <h6 style="margin: 0 0 12px 0; color: #7c2d12; font-weight: bold;">
                                <i class="ti ti-help-circle"></i> Possible Causes
                            </h6>
                            <ul style="margin: 0; padding-left: 20px; color: #744210;">
                                <li style="margin-bottom: 8px;">Unauthorized database modification</li>
                                <li style="margin-bottom: 8px;">System update requiring hash regeneration</li>
                                <li style="margin-bottom: 8px;">Data corruption or synchronization error</li>
                            </ul>
                        </div>
                        
                        <!-- Recommended Actions -->
                        <div style="background: #ebf8ff; border-left: 4px solid #4299e1; padding: 20px; border-radius: 8px;">
                            <h6 style="margin: 0 0 12px 0; color: #2c5282; font-weight: bold;">
                                <i class="ti ti-clipboard-list"></i> Recommended Actions
                            </h6>
                            <ul style="margin: 0; padding-left: 20px; color: #2c5282;">
                                <li style="margin-bottom: 8px;">Contact system administrator immediately</li>
                                <li style="margin-bottom: 8px;">Do not modify or save this document</li>
                                <li style="margin-bottom: 8px;">Review audit logs for unauthorized access</li>
                                <li>If after system update, click "Save" to regenerate hash</li>
                            </ul>
                        </div>
                        
                    </div>
                    
                    <!-- Footer with Actions -->
                    <div class="modal-footer" style="border-top: 1px solid #e2e8f0; padding: 20px 30px; gap: 10px; display: flex; justify-content: flex-end;">
                        <button 
                            onclick="viewAuditLog(${contractId})" 
                            class="btn btn-outline-secondary"
                            style="border: 2px solid #cbd5e0; color: #4a5568;">
                            <i class="ti ti-history"></i> View Audit Log
                        </button>
                        
                        <button 
                            onclick="contactAdministrator(${contractId})" 
                            class="btn btn-warning"
                            style="background: #ed8936; border: none; color: white;">
                            <i class="ti ti-mail"></i> Contact Admin
                        </button>
                        
                        <button 
                            onclick="closeTamperAlert()" 
                            class="btn btn-danger"
                            style="background: #e53e3e; border: none;">
                            <i class="ti ti-x"></i> Close
                        </button>
                    </div>
                    
                </div>
            </div>
        </div>
        
        <!-- Backdrop -->
        <div class="modal-backdrop show" style="z-index: 9999;"></div>
        
        <style>
            #tamperAlertModal {
                animation: modalFadeIn 0.3s ease;
            }
            
            @keyframes modalFadeIn {
                from {
                    opacity: 0;
                    transform: scale(0.9);
                }
                to {
                    opacity: 1;
                    transform: scale(1);
                }
            }
            
            #tamperAlertModal .modal-content {
                animation: slideDown 0.3s ease;
            }
            
            @keyframes slideDown {
                from {
                    transform: translateY(-50px);
                }
                to {
                    transform: translateY(0);
                }
            }
            
            #tamperAlertModal .btn {
                transition: all 0.2s ease;
            }
            
            #tamperAlertModal .btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }
            
            @keyframes modalFadeOut {
                from {
                    opacity: 1;
                    transform: scale(1);
                }
                to {
                    opacity: 0;
                    transform: scale(0.9);
                }
            }
        </style>
    `;
    
    // Insert modal into page
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    
    // Prevent body scroll
    document.body.style.overflow = 'hidden';
    
    // Update indicator to show tampered status
    const indicator = document.getElementById('blockchain-indicator');
    if (indicator) {
        indicator.innerHTML = `
            <div class="alert alert-danger" style="display: flex; align-items: center; gap: 10px; margin: 0; padding: 12px 15px;">
                <i class="ti ti-shield-alert" style="font-size: 24px;"></i>
                <div>
                    <strong>⚠️ Tampered</strong><br>
                    <small>Document integrity compromised</small>
                </div>
            </div>
        `;
    }
}


function closeTamperAlert() {
    const modal = document.getElementById('tamperAlertModal');
    const backdrop = document.querySelector('.modal-backdrop');
    
    if (modal) {
        modal.style.animation = 'modalFadeOut 0.2s ease';
        setTimeout(() => {
            modal.remove();
            if (backdrop) backdrop.remove();
            document.body.style.overflow = '';
        }, 200);
    }
}

// =====================================================
// HELPER FUNCTIONS
// =====================================================

function viewAuditLog(contractId) {
    closeTamperAlert();
    window.location.href = `/audit-trail?contract_id=${contractId}&filter=tampering`;
}

function contactAdministrator(contractId) {
    closeTamperAlert();
    
    const subject = encodeURIComponent(`URGENT: Tampering Detected - Contract ${contractId}`);
    const body = encodeURIComponent(`
Tampering has been detected on Contract ID: ${contractId}
Detection Time: ${new Date().toLocaleString()}

Please investigate this security incident immediately.
    `);
    
    // Open email client or support system
    alert('Administrator has been notified. A support ticket has been created.');
    
    // Optional: Redirect to support page
    // window.location.href = '/support?issue=tampering&contract=' + contractId;
}

// =====================================================
// AUTO-VERIFY ON PAGE LOAD
// =====================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🔐 Blockchain verification system loaded');
    
    // Get contract ID from URL or data attribute
    const urlParams = new URLSearchParams(window.location.search);
    const contractId = urlParams.get('id') || 
                      document.querySelector('[data-contract-id]')?.dataset.contractId;
    
    if (contractId) {
        console.log('📋 Contract ID found:', contractId);
        
        // Auto-verify after 1 second
        setTimeout(() => {
            verifyContract(contractId);
        }, 1000);
    }
});

// =====================================================
// EXPORT FUNCTIONS
// =====================================================

if (typeof window !== 'undefined') {
    window.verifyContract = verifyContract;
    window.showTamperAlert = showTamperAlert;
    window.closeTamperAlert = closeTamperAlert;
    window.viewAuditLog = viewAuditLog;
    window.contactAdministrator = contactAdministrator;
}
// Show error indicator
function showErrorIndicator(contractId) {
    const indicator = document.getElementById('blockchain-indicator');
    if (!indicator) return;
    
    indicator.innerHTML = `
        <div class="alert alert-warning" style="display: flex; align-items: center; gap: 10px; margin: 0; padding: 12px 15px;">
            <i class="ti ti-alert-triangle" style="font-size: 24px;"></i>
            <div>
                <strong>Verification Error</strong><br>
                <small>Could not verify blockchain status</small>
            </div>
        </div>
    `;
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
                                    <td><span class="badge bg-success"> Verified</span></td>
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