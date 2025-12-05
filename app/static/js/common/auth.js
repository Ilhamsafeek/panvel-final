// =====================================================
// File: app/static/js/common/auth.js
// FIXED - Removed automatic redirect that causes loop
// =====================================================

// =====================================================
// Token Management Functions (for API calls)
// =====================================================

// Get auth token from localStorage (for API calls only)
function getAuthToken() {
    return localStorage.getItem('access_token');
}

// Set auth token in localStorage (for API calls)
function setAuthToken(token) {
    localStorage.setItem('access_token', token);
}

// Remove auth token from localStorage
function removeAuthToken() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('user_email');
    localStorage.removeItem('user_name');
    localStorage.removeItem('user_company');
}

// Store user info in localStorage
function setUserInfo(user) {
    if (user.id) localStorage.setItem('user_id', user.id);
    if (user.email) localStorage.setItem('user_email', user.email);
    if (user.first_name || user.last_name) {
        localStorage.setItem('user_name', `${user.first_name || ''} ${user.last_name || ''}`.trim());
    }
    if (user.company) localStorage.setItem('user_company', user.company);
}

// Get user info from localStorage
function getUserInfo() {
    return {
        id: localStorage.getItem('user_id'),
        email: localStorage.getItem('user_email'),
        name: localStorage.getItem('user_name'),
        company: localStorage.getItem('user_company')
    };
}

// =====================================================
// API Request Functions
// =====================================================

// Make authenticated API calls
async function authenticatedFetch(url, options = {}) {
    const token = getAuthToken();

    const defaultOptions = {
        credentials: 'include', // Always include cookies
        headers: {
            'Content-Type': 'application/json',
            ...(token && { 'Authorization': `Bearer ${token}` })
        }
    };

    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };

    return fetch(url, mergedOptions);
}

// =====================================================
// Login Function (for forms)
// =====================================================

async function login(email, password, rememberMe = false) {
    showLoading('Signing in...');

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            credentials: 'include', // Include cookies
            body: JSON.stringify({
                email: email,
                password: password,
                remember_me: rememberMe
            })
        });

        const data = await response.json();

        if (response.ok && data.success) {
            // Store token and user info (optional, cookies are primary)
            if (data.access_token) setAuthToken(data.access_token);
            if (data.user) setUserInfo(data.user);

            console.log('✅ Login successful');

            // Redirect to dashboard or intended page
            const urlParams = new URLSearchParams(window.location.search);
            const redirect = urlParams.get('redirect') || '/dashboard';  // Changed from '/dashboard' to '/hub'
            window.location.href = redirect;

            return data;
        } else {
            // Handle 2FA or other special cases
            if (data.requires_2fa) {
                return data; // Let the calling function handle 2FA
            }

            throw new Error(data.detail || data.message || 'Login failed');
        }

    } catch (error) {
        console.error('❌ Login error:', error);
        throw error;
    } finally {
        hideLoading();
    }
}

// =====================================================
// Logout Function
// =====================================================

async function logout() {
    try {
        const response = await fetch('/api/auth/logout', {
            method: 'POST',
            credentials: 'include'
        });

        console.log('✅ Logout successful');

    } catch (error) {
        console.error('Logout API error:', error);
        // Continue with logout even if API fails
    } finally {
        // Always clear local storage and redirect
        removeAuthToken();
        window.location.href = '/login';
    }
}

// =====================================================
// Loading and Error Handling
// =====================================================

function showLoading(message = 'Loading...') {
    console.log(`⏳ ${message}`);
    // Can be extended to show UI loading indicator
}

function hideLoading() {
    console.log('✅ Loading complete');
    // Can be extended to hide UI loading indicator
}

// =====================================================
// Export functions for use in other scripts
// =====================================================

if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        getAuthToken,
        setAuthToken,
        removeAuthToken,
        setUserInfo,
        getUserInfo,
        authenticatedFetch,
        login,
        logout
    };
}