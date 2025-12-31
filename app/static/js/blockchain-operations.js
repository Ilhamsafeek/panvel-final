/* =====================================================
   BLOCKCHAIN OPERATIONS MONITOR - JavaScript (REAL DATA)
   File: app/static/js/blockchain-operations.js
   ===================================================== */

// Global Variables
let logRefreshInterval = null;
let isRefreshing = false;
let currentContractId = null;

// =====================================================
// MODAL CONTROL FUNCTIONS
// =====================================================
function openBlockchainOperations() {
    console.log('Opening blockchain modal...');

    const modal = document.getElementById('blockchainOperationsModal');
    if (!modal) {
        alert('Modal not found!');
        return;
    }

    modal.style.display = 'flex';
    modal.style.zIndex = '999999';
    document.body.style.overflow = 'hidden';

    // Load data
    setTimeout(() => {
        switchTab('docker-containers');
    }, 100);
}


function closeBlockchainOperations() {
    const modal = document.getElementById('blockchainOperationsModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
    stopLogRefresh();
}

function switchTab(tabId) {
    // Update tab buttons
    document.querySelectorAll('.blockchain-ops-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabId}"]`)?.classList.add('active');

    // Update panels
    document.querySelectorAll('.blockchain-ops-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`tab-${tabId}`)?.classList.add('active');

    // Stop log refresh when switching away
    if (tabId !== 'blockchain-logs') {
        stopLogRefresh();
    }
}

// =====================================================
// TAB 1: BLOCKCHAIN RECORDS (Real Data)
// =====================================================

async function runDockerCommand() {
    const terminalId = 'terminal-docker-output';
    const terminal = document.getElementById(terminalId);

    terminal.innerHTML = `
        <div class="terminal-line command">$ Fetching blockchain records from database...</div>
        <div class="terminal-line dim">Querying blockchain_records...</div>
    `;

    try {
        const response = await fetch('/api/blockchain/terminal/blockchain-records?limit=20', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            displayBlockchainRecords(terminalId, data);
        } else {
            terminal.innerHTML += `<div class="terminal-line error">Error: ${data.message || 'Failed to fetch records'}</div>`;
        }
    } catch (error) {
        console.error('Error fetching blockchain records:', error);
        terminal.innerHTML += `
            <div class="terminal-line error">Error: ${error.message}</div>
            <div class="terminal-line dim">Make sure the API endpoint is available.</div>
        `;
    }
}

function displayBlockchainRecords(terminalId, data) {
    const terminal = document.getElementById(terminalId);
    terminal.innerHTML = '';

    // Header
    terminal.innerHTML = `
        <div class="terminal-line success">✓ Retrieved blockchain records </div>
       
        <div class="terminal-line dim">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
        <div class="terminal-line" style="color: #00d9ff; font-weight: bold;">
            ${'TX HASH'.padEnd(22)} ${'BLOCK'.padEnd(12)} ${'STATUS'.padEnd(12)} CONTRACT
        </div>
        <div class="terminal-line dim">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
    `;

    if (data.records.length === 0) {
        terminal.innerHTML += `
            <div class="terminal-line warning">No blockchain records found.</div>
            <div class="terminal-line dim">Create or sign a contract to generate blockchain records.</div>
        `;
        return;
    }

    data.records.forEach(record => {
        const txHash = (record.transaction_hash || '').substring(0, 20) + '...';
        const block = (record.block_number || 'Pending').toString().padEnd(12);
        const status = (record.status || 'unknown').padEnd(12);
        const contract = record.contract_number || record.entity_id || 'N/A';
        const statusClass = record.status === 'confirmed' ? 'success' : 'warning';

        terminal.innerHTML += `
            <div class="terminal-line">
                <span class="json-string">${txHash.padEnd(22)}</span>
                <span class="json-value">${block}</span>
                <span class="${statusClass}">${status}</span>
                ${contract}
            </div>
        `;
    });

    terminal.innerHTML += `
        <div class="terminal-line dim">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
    `;
}

// =====================================================
// TAB 2: QUERY CONTRACT (Real Data)
// =====================================================

async function runQueryCommand() {
    const contractId = document.getElementById('queryContractId').value.trim();

    if (!contractId) {
        showNotification('Please enter a Contract ID', 'warning');
        return;
    }

    // document.getElementById('queryIdPreview').textContent = contractId;

    const terminalId = 'terminal-query-output';
    const terminal = document.getElementById(terminalId);

    terminal.innerHTML = `
        <div class="terminal-line command">$ Querying blockchain for this Contract...</div>
        <div class="terminal-line dim">Searching blockchain_records and document_integrity records...</div>
    `;

    try {
        const response = await fetch(`/api/blockchain/terminal/query-contract/${contractId}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();
        displayContractData(terminalId, data, contractId);

    } catch (error) {
        console.error('Query error:', error);
        terminal.innerHTML += `
            <div class="terminal-line error">Error: ${error.message}</div>
        `;
    }
}

function displayContractData(terminalId, data, contractId) {
    const terminal = document.getElementById(terminalId);
    terminal.innerHTML = '';

    if (!data.success) {
        terminal.innerHTML = `
            <div class="terminal-line error">═══════════════════════════════════════════════════</div>
            <div class="terminal-line error">  ✗ NO BLOCKCHAIN RECORD FOUND</div>
            <div class="terminal-line error">═══════════════════════════════════════════════════</div>
            <div class="terminal-line"></div>
            <div class="terminal-line warning">Contract ID: ${contractId}</div>
            <div class="terminal-line dim">${data.message || 'This contract has not been recorded on the blockchain yet.'}</div>
            ${data.contract_exists ? `<div class="terminal-line info">Contract exists in database: ${data.contract_number}</div>` : ''}
        `;
        return;
    }

    terminal.innerHTML = `
        <div class="terminal-line success">═══════════════════════════════════════════════════</div>
        <div class="terminal-line success">  ✓ BLOCKCHAIN RECORD FOUND</div>
        <div class="terminal-line success">═══════════════════════════════════════════════════</div>
        <div class="terminal-line"></div>
    `;

    // Contract info
    if (data.contract) {
        terminal.innerHTML += `
            <div class="terminal-line"><span class="json-key">Contract Number:</span> <span class="json-string">${data.contract.number || 'N/A'}</span></div>
            <div class="terminal-line"><span class="json-key">Contract Title:</span> <span class="json-string">${data.contract.title || 'N/A'}</span></div>
            <div class="terminal-line"><span class="json-key">Contract Type:</span> <span class="json-string">${data.contract.type || 'N/A'}</span></div>
            <div class="terminal-line"><span class="json-key">Status:</span> <span class="json-value">${data.contract.status || 'N/A'}</span></div>
            <div class="terminal-line"></div>
        `;
    }

    // Blockchain record
    if (data.blockchain_record) {
        terminal.innerHTML += `
            <div class="terminal-line" style="color: #00d9ff;">── Blockchain Record ──</div>
            <div class="terminal-line"><span class="json-key">Transaction Hash:</span> <span class="json-string">${data.blockchain_record.transaction_hash || 'N/A'}</span></div>
            <div class="terminal-line"><span class="json-key">Block Number:</span> <span class="json-value">${data.blockchain_record.block_number || 'Pending'}</span></div>
            <div class="terminal-line"><span class="json-key">Network:</span> <span class="json-string">${data.blockchain_record.network || 'hyperledger-fabric'}</span></div>
            <div class="terminal-line"><span class="json-key">Status:</span> <span class="success">${data.blockchain_record.status || 'confirmed'}</span></div>
            <div class="terminal-line"><span class="json-key">Created At:</span> <span class="json-string">${data.blockchain_record.created_at || 'N/A'}</span></div>
            <div class="terminal-line"></div>
        `;
    }

    // Document integrity
    if (data.integrity_record) {
        terminal.innerHTML += `
            <div class="terminal-line" style="color: #00d9ff;">── Document Integrity ──</div>
            <div class="terminal-line"><span class="json-key">Document Hash:</span> <span class="json-string">${data.integrity_record.document_hash || 'N/A'}</span></div>
            <div class="terminal-line"><span class="json-key">Algorithm:</span> <span class="json-value">${data.integrity_record.hash_algorithm || 'SHA-256'}</span></div>
            <div class="terminal-line"><span class="json-key">Verification:</span> <span class="success">${data.integrity_record.verification_status || 'verified'}</span></div>
            <div class="terminal-line"><span class="json-key">Last Verified:</span> <span class="json-string">${data.integrity_record.last_verified_at || 'N/A'}</span></div>
        `;
    }

    terminal.innerHTML += `
        <div class="terminal-line"></div>
    `;
}

// =====================================================
// TAB 3: VERIFY TRANSACTION (Real Data)
// =====================================================

async function runVerifyCommand() {
    const txHash = document.getElementById('verifyTxHash').value.trim();

    if (!txHash) {
        showNotification('Please enter a Transaction Hash', 'warning');
        return;
    }

    document.getElementById('txHashPreview').textContent = txHash;

    const terminalId = 'terminal-verify-output';
    const terminal = document.getElementById(terminalId);

    terminal.innerHTML = `
        <div class="terminal-line command">$ Verifying transaction hash: ${txHash}</div>
        <div class="terminal-line dim">Searching blockchain_records and audit_logs...</div>
    `;

    try {
        const response = await fetch('/api/blockchain/terminal/verify-transaction', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ transaction_hash: txHash })
        });

        const data = await response.json();
        displayVerificationResult(terminalId, data, txHash);

    } catch (error) {
        console.error('Verification error:', error);
        terminal.innerHTML += `
            <div class="terminal-line error">Error: ${error.message}</div>
        `;
    }
}

function displayVerificationResult(terminalId, data, txHash) {
    const terminal = document.getElementById(terminalId);
    terminal.innerHTML = '';

    if (data.verified) {
        terminal.innerHTML = `
            <div class="terminal-line success">═══════════════════════════════════════════════════</div>
            <div class="terminal-line success">  ✓ TRANSACTION VERIFIED</div>
            <div class="terminal-line success">═══════════════════════════════════════════════════</div>
            <div class="terminal-line"></div>
            <div class="terminal-line"><span class="json-key">Hash:</span> <span class="json-string">${txHash}</span></div>
            <div class="terminal-line"><span class="json-key">Source:</span> <span class="json-value">${data.source}</span></div>
        `;

        const tx = data.transaction || {};

        if (tx.block_number) {
            terminal.innerHTML += `<div class="terminal-line"><span class="json-key">Block Number:</span> <span class="json-value">${tx.block_number}</span></div>`;
        }
        if (tx.network) {
            terminal.innerHTML += `<div class="terminal-line"><span class="json-key">Network:</span> <span class="json-string">${tx.network}</span></div>`;
        }
        if (tx.status) {
            terminal.innerHTML += `<div class="terminal-line"><span class="json-key">Status:</span> <span class="success">${tx.status}</span></div>`;
        }
        if (tx.contract_number) {
            terminal.innerHTML += `<div class="terminal-line"><span class="json-key">Contract:</span> <span class="json-string">${tx.contract_number}</span></div>`;
        }
        if (tx.created_at) {
            terminal.innerHTML += `<div class="terminal-line"><span class="json-key">Created:</span> <span class="json-string">${tx.created_at}</span></div>`;
        }

        terminal.innerHTML += `
            <div class="terminal-line"></div>
            <div class="terminal-line info">ℹ Transaction exists in the ${data.source}</div>
        `;
    } else {
        terminal.innerHTML = `
            <div class="terminal-line error">═══════════════════════════════════════════════════</div>
            <div class="terminal-line error">  ✗ TRANSACTION NOT FOUND</div>
            <div class="terminal-line error">═══════════════════════════════════════════════════</div>
            <div class="terminal-line"></div>
            <div class="terminal-line warning">Hash: ${txHash}</div>
            <div class="terminal-line dim">${data.message || 'This transaction hash was not found in the database.'}</div>
            <div class="terminal-line"></div>
            <div class="terminal-line dim">Possible reasons:</div>
            <div class="terminal-line dim">  • The hash may be incorrect or incomplete</div>
            <div class="terminal-line dim">  • The transaction may not have been recorded yet</div>
            <div class="terminal-line dim">  • The hash may be from a different system</div>
        `;
    }
}

// =====================================================
// TAB 4: ACTIVITY LOGS (Real Data)
// =====================================================

async function runLogsCommand() {
    const terminalId = 'terminal-logs-output';
    const terminal = document.getElementById(terminalId);

    // Update UI
    isRefreshing = true;
    document.getElementById('stopLogsBtn').style.display = 'flex';
    document.getElementById('logStreamStatus').innerHTML = '<i class="ti ti-loader"></i> Loading...';
    document.getElementById('logStreamStatus').className = 'log-status streaming';

    terminal.innerHTML = `
        <div class="terminal-line command">$ Fetching blockchain activity logs...</div>
        <div class="terminal-line dim">Querying audit_logs for blockchain operations...</div>
        <div class="terminal-line"></div>
    `;

    await loadActivityLogs(terminalId);

    // Start auto-refresh
    logRefreshInterval = setInterval(() => {
        if (isRefreshing) {
            loadActivityLogs(terminalId, true);
        }
    }, 10000); // Refresh every 10 seconds
}

async function loadActivityLogs(terminalId, append = false) {
    try {
        const response = await fetch('/api/blockchain/terminal/activity-logs?limit=50', {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${getAuthToken()}`,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            displayActivityLogs(terminalId, data, append);
            document.getElementById('logStreamStatus').innerHTML = '<i class="ti ti-circle-check"></i> Live';
        } else {
            const terminal = document.getElementById(terminalId);
            terminal.innerHTML += `<div class="terminal-line error">Error loading logs: ${data.message}</div>`;
        }

    } catch (error) {
        console.error('Error loading activity logs:', error);
        const terminal = document.getElementById(terminalId);
        terminal.innerHTML += `<div class="terminal-line error">Error: ${error.message}</div>`;
    }
}

function displayActivityLogs(terminalId, data, append = false) {
    const terminal = document.getElementById(terminalId);

    if (!append) {
        terminal.innerHTML = `
            <div class="terminal-line success">✓ Retrieved ${data.count} blockchain activity logs</div>
            <div class="terminal-line dim">Source: ${data.source} | Auto-refresh: 10s</div>
            <div class="terminal-line dim">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</div>
        `;
    }

    if (data.logs.length === 0) {
        terminal.innerHTML += `
            <div class="terminal-line warning">No blockchain activity logs found.</div>
            <div class="terminal-line dim">Blockchain operations will appear here when contracts are created or signed.</div>
        `;
        return;
    }

    data.logs.forEach(log => {
        const badgeClass = log.type.toLowerCase();
        const txHash = log.transaction_hash ? ` [${log.transaction_hash.substring(0, 12)}...]` : '';

        terminal.innerHTML += `
            <div class="log-entry">
                <span class="log-timestamp">${log.timestamp || '--:--:--'}</span>
                <span class="log-badge ${badgeClass}">${log.type}</span>
                <span class="log-message">
                    ${log.message}${txHash}
                    ${log.contract_number ? `<span class="dim"> [${log.contract_number}]</span>` : ''}
                </span>
            </div>
        `;
    });

    // Auto-scroll to bottom
    terminal.scrollTop = terminal.scrollHeight;
}

function stopLogRefresh() {
    isRefreshing = false;

    if (logRefreshInterval) {
        clearInterval(logRefreshInterval);
        logRefreshInterval = null;
    }

    const stopBtn = document.getElementById('stopLogsBtn');
    const statusEl = document.getElementById('logStreamStatus');

    if (stopBtn) stopBtn.style.display = 'none';
    if (statusEl) {
        statusEl.innerHTML = '<i class="ti ti-circle"></i> Stopped';
        statusEl.className = 'log-status';
    }
}

// =====================================================
// UTILITY FUNCTIONS
// =====================================================

async function loadNetworkStats() {
    try {
        const response = await fetch('/api/blockchain/terminal/network-stats', {
            headers: { 'Authorization': `Bearer ${getAuthToken()}` }
        });
        const data = await response.json();

        if (data.success && data.display) {
            document.getElementById('totalBlocksCount').textContent = data.display.total_blocks?.toLocaleString() || '0';
            document.getElementById('totalTxCount').textContent = data.display.total_txs?.toLocaleString() || '0';
            document.getElementById('networkUptime').textContent = data.display.uptime || '99.99%';
            document.getElementById('connectedPeersCount').textContent = data.display.connected_peers || '4';
        }
    } catch (error) {
        console.log('Error loading network stats:', error);
    }
}

async function loadRecentHashes() {
    const container = document.getElementById('recentHashesList');
    if (!container) return;

    try {
        const response = await fetch('/api/blockchain/terminal/recent-hashes?limit=5', {
            headers: { 'Authorization': `Bearer ${getAuthToken()}` }
        });
        const data = await response.json();

        if (data.success && data.hashes.length > 0) {
            container.innerHTML = data.hashes.map(h => `
                <div class="hash-item" onclick="document.getElementById('verifyTxHash').value='${h.hash}'; document.getElementById('txHashPreview').textContent='${h.hash}';">
                    <code>${h.hash.substring(0, 24)}...</code>
                    <span class="hash-time">${h.time_ago}</span>
                </div>
            `).join('');
        } else {
            container.innerHTML = `<div class="terminal-line dim">No recent transactions found</div>`;
        }
    } catch (error) {
        console.log('Error loading recent hashes:', error);
        container.innerHTML = `<div class="terminal-line dim">Unable to load recent hashes</div>`;
    }
}

function refreshAllTerminals() {
    const activeTab = document.querySelector('.blockchain-ops-tab.active');
    if (activeTab) {
        const tabId = activeTab.dataset.tab;
        switch (tabId) {
            case 'docker-containers': runDockerCommand(); break;
            case 'query-blockchain': runQueryCommand(); break;
            case 'verify-hash': runVerifyCommand(); break;
            case 'blockchain-logs': runLogsCommand(); break;
        }
    }
}

function clearAllTerminals() {
    ['terminal-docker-output', 'terminal-query-output', 'terminal-verify-output', 'terminal-logs-output'].forEach(id => {
        const terminal = document.getElementById(id);
        if (terminal) {
            terminal.innerHTML = '<div class="terminal-welcome"><span class="terminal-line dim">Terminal cleared</span></div>';
        }
    });
}

function exportTerminalLogs() {
    const terminals = ['terminal-docker-output', 'terminal-query-output', 'terminal-verify-output', 'terminal-logs-output'];
    const tabNames = ['Blockchain Records', 'Query Contract', 'Verify Transaction', 'Activity Logs'];

    let exportContent = `CALIM 360 Blockchain Operations Log\n`;
    exportContent += `Exported: ${new Date().toISOString()}\n`;
    exportContent += `User: Real Database Data\n`;
    exportContent += `${'='.repeat(60)}\n\n`;

    terminals.forEach((id, index) => {
        const terminal = document.getElementById(id);
        if (terminal) {
            exportContent += `--- ${tabNames[index]} ---\n${terminal.textContent}\n\n`;
        }
    });

    const blob = new Blob([exportContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `blockchain-operations-${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);

    showNotification('Logs exported successfully', 'success');
}

function getContractIdFromPage() {
    const urlParams = new URLSearchParams(window.location.search);
    let contractId = urlParams.get('contract_id') || urlParams.get('id');

    if (!contractId) {
        const pathMatch = window.location.pathname.match(/\/contract\/(?:edit|view)\/(\d+)/);
        if (pathMatch) {
            contractId = pathMatch[1];
        }
    }

    if (!contractId) {
        const indicator = document.querySelector('[data-contract-id]');
        if (indicator) {
            contractId = indicator.dataset.contractId;
        }
    }

    return contractId;
}

function getAuthToken() {
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'session_token') return value;
    }
    return null;
}

function showNotification(message, type = 'info') {
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
    } else {
        console.log(`[${type.toUpperCase()}] ${message}`);
        alert(message);
    }
}

// =====================================================
// EVENT LISTENERS
// =====================================================

document.addEventListener('DOMContentLoaded', function () {
    // Update query preview on input
    const queryInput = document.getElementById('queryContractId');
    if (queryInput) {
        queryInput.addEventListener('input', function () {
            // document.getElementById('queryIdPreview').textContent = this.value || 'CONTRACT_ID';
        });
    }

    // Update hash preview on input
    const hashInput = document.getElementById('verifyTxHash');
    if (hashInput) {
        hashInput.addEventListener('input', function () {
            document.getElementById('txHashPreview').textContent = this.value || 'TX_HASH';
        });
    }

    // Update peer preview on change
    const peerSelect = document.getElementById('peerSelect');
    if (peerSelect) {
        peerSelect.addEventListener('change', function () {
            document.getElementById('peerNamePreview').textContent = this.value;
        });
    }

    // Close modal on Escape key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeBlockchainOperations();
        }
    });
});


// QUICK FIX: Event listeners
document.addEventListener('DOMContentLoaded', function () {
    console.log('Setting up event listeners...');

    // Close button
    const closeBtn = document.getElementById('closeBlockchainBtn');
    if (closeBtn) {
        closeBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            closeBlockchainOperations();
        });
    }

    // Tab buttons
    document.getElementById('tab-btn-docker')?.addEventListener('click', () => switchTab('docker-containers'));
    document.getElementById('tab-btn-query')?.addEventListener('click', () => switchTab('query-blockchain'));
    document.getElementById('tab-btn-logs')?.addEventListener('click', () => switchTab('blockchain-logs'));

    // Refresh and clear
    document.getElementById('refreshAllBtn')?.addEventListener('click', refreshAllTerminals);
    document.getElementById('clearAllBtn')?.addEventListener('click', clearAllTerminals);

    console.log('Event listeners ready!');
});


// Export functions for global access
window.openBlockchainOperations = openBlockchainOperations;
window.closeBlockchainOperations = closeBlockchainOperations;
window.switchTab = switchTab;
window.runDockerCommand = runDockerCommand;
window.runQueryCommand = runQueryCommand;
window.runVerifyCommand = runVerifyCommand;
window.runLogsCommand = runLogsCommand;
window.stopLogRefresh = stopLogRefresh;
window.refreshAllTerminals = refreshAllTerminals;
window.clearAllTerminals = clearAllTerminals;
window.exportTerminalLogs = exportTerminalLogs;