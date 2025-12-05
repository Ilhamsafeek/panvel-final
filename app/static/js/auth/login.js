// =====================================================
// File: app/static/js/auth/login.js
// Login Page JavaScript - UPDATED
// =====================================================

document.addEventListener('DOMContentLoaded', function () {
    const loginForm = document.getElementById('loginForm');
    const loginBtn = document.getElementById('submitBtn');
    const emailInput = document.querySelector('input[name="email"]');
    const passwordInput = document.querySelector('input[name="password"]');
    const rememberMeCheckbox = document.querySelector('input[name="rememberMe"]');
    const errorDiv = document.querySelector('.alert.error');
    const successDiv = document.querySelector('.alert.success');

    // Login form submission
    loginForm.addEventListener('submit', async function (e) {
        e.preventDefault();

        clearMessages();

        const email = emailInput.value.trim();
        const password = passwordInput.value;
        const rememberMe = rememberMeCheckbox ? rememberMeCheckbox.checked : false;

        // Validate inputs
        if (!email || !password) {
            showError('Please enter both email and password');
            return;
        }

        if (!isValidEmail(email)) {
            showError('Please enter a valid email address');
            return;
        }

        setLoading(true);

        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                credentials: 'include', // Important for cookies
                body: JSON.stringify({
                    email: email,
                    password: password,
                    remember_me: rememberMe
                })
            });

            const data = await response.json();

            if (response.ok && data.success) {
                // Check for 2FA requirement
                if (data.requires_2fa) {
                    show2FAForm(email);
                    return;
                }

                // Check for security question requirement
                if (data.requires_security_question) {
                    showSecurityQuestionForm(email);
                    return;
                }

                // Login successful
                showSuccess('Login successful! Redirecting to dashboard...');

                // Store user info in localStorage (optional, since we're using cookies)
                if (data.user) {
                    localStorage.setItem('user_id', data.user.id);
                    localStorage.setItem('user_email', data.user.email);
                    localStorage.setItem('user_name', `${data.user.first_name} ${data.user.last_name}`);
                }

                // Store access token in localStorage (for API calls)
                if (data.access_token) {
                    localStorage.setItem('access_token', data.access_token);
                }

                // Redirect after short delay
                setTimeout(() => {
                    const redirectUrl = data.redirect_url || '/dashboard';  // Changed from '/dashboard' to '/hub'
                    console.log(`🔄 Redirecting to: ${redirectUrl}`);
                    window.location.href = redirectUrl;
                }, 1000);
            } else {
                // Login failed
                const errorMessage = data.detail || data.message || 'Login failed';
                showError(errorMessage);
            }

        } catch (error) {
            console.error('❌ Login error:', error);
            showError('Network error. Please check your connection and try again.');
        } finally {
            setLoading(false);
        }
    });

    // Helper functions
    function clearMessages() {
        if (errorDiv) {
            errorDiv.style.display = 'none';
            const errorMessage = errorDiv.querySelector('#errorMessage');
            if (errorMessage) errorMessage.textContent = '';
        }
        if (successDiv) {
            successDiv.style.display = 'none';
            const successMessage = successDiv.querySelector('span');
            if (successMessage) successMessage.textContent = '';
        }
    }

    function showError(message) {
        if (errorDiv) {
            const errorMessage = errorDiv.querySelector('#errorMessage');
            if (errorMessage) {
                errorMessage.textContent = message;
            }
            errorDiv.style.display = 'flex';
        }
        console.error('🚨 Login error:', message);
    }

    function showSuccess(message) {
        if (successDiv) {
            const successMessage = successDiv.querySelector('span');
            if (successMessage) {
                successMessage.textContent = message;
            }
            successDiv.style.display = 'flex';
        }
        console.log('✅ Login success:', message);
    }

    function setLoading(loading) {
        if (loginBtn) {
            loginBtn.disabled = loading;
            const btnText = loginBtn.querySelector('.btn-text #submitBtnText');
            if (btnText) {
                btnText.innerHTML = loading ?
                    '<i class="ti ti-loader"></i> Signing in...' :
                    'Sign In <i class="ti ti-login"></i>';
            }
        }

        // Disable form inputs
        if (emailInput) emailInput.disabled = loading;
        if (passwordInput) passwordInput.disabled = loading;
    }

    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    function show2FAForm(email) {
        // TODO: Implement 2FA form display
        console.log('📱 Showing 2FA form for:', email);
        showError('2FA verification required. This feature is coming soon.');
    }

    function showSecurityQuestionForm(email) {
        // TODO: Implement security question form display
        console.log('🔒 Showing security question form for:', email);
        showError('Security question verification required. This feature is coming soon.');
    }
});

// =====================================================
// Utility Functions
// =====================================================

// Logout function (can be called from other pages)
async function logout() {
    try {
        const response = await fetch('/api/auth/logout', {
            method: 'POST',
            credentials: 'include'
        });

        // Clear localStorage
        localStorage.removeItem('access_token');
        localStorage.removeItem('user_id');
        localStorage.removeItem('user_email');
        localStorage.removeItem('user_name');

        // Redirect to login
        window.location.href = '/login';

    } catch (error) {
        console.error('Logout error:', error);
        // Force redirect even if logout request failed
        window.location.href = '/login';
    }
}