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

    console.log('🎯 Login page initialized');

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
            console.log(' Attempting login for:', email);
            
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

            console.log('📡 Response status:', response.status);

            //  CRITICAL FIX: Always parse JSON response, even for errors
            const data = await response.json();
            console.log('📦 Response data:', data);

            //  FIXED: Check response.ok (status 200-299) not data.success
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
                console.log(' Login successful');
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
                    const redirectUrl = data.redirect_url || '/hub';
                    console.log(`🔄 Redirecting to: ${redirectUrl}`);
                    window.location.href = redirectUrl;
                }, 1000);
            } else {
                //  CRITICAL FIX: Show the ACTUAL error message from backend
                let errorMessage = 'Login failed';
                
                // Try different error message formats
                if (data.detail) {
                    errorMessage = data.detail;
                } else if (data.message) {
                    errorMessage = data.message;
                } else if (data.error) {
                    errorMessage = data.error;
                }
                
                console.error('❌ Login failed:', errorMessage);
                console.error('❌ Full error data:', data);
                showError(errorMessage);
            }

        } catch (error) {
            console.error('💥 Network/Parse error:', error);
            showError('Network error. Please check your connection and try again.');
        } finally {
            setLoading(false);
        }
    });

    // =====================================================
    // HELPER FUNCTIONS
    // =====================================================

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
        console.error('🚨 Showing error:', message);
        if (errorDiv) {
            const errorMessage = errorDiv.querySelector('#errorMessage');
            if (errorMessage) {
                errorMessage.textContent = message;
            } else {
                // Fallback if no errorMessage element
                errorDiv.innerHTML = `<span>${message}</span>`;
            }
            errorDiv.style.display = 'flex';
            
            // Scroll to error message
            errorDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            // Fallback: show alert if no error div
            alert(message);
        }
    }

    function showSuccess(message) {
        console.log(' Showing success:', message);
        if (successDiv) {
            const successMessage = successDiv.querySelector('span');
            if (successMessage) {
                successMessage.textContent = message;
            } else {
                // Fallback if no success message element
                successDiv.innerHTML = `<span>${message}</span>`;
            }
            successDiv.style.display = 'flex';
        }
    }

    function setLoading(loading) {
        if (loginBtn) {
            loginBtn.disabled = loading;
            const btnText = loginBtn.querySelector('.btn-text #submitBtnText');
            if (btnText) {
                btnText.innerHTML = loading ?
                    '<i class="ti ti-loader-2 rotating"></i> Signing in...' :
                    'Sign In';
            } else {
                // Fallback: update button text directly
                loginBtn.textContent = loading ? 'Signing in...' : 'Sign In';
            }
        }
        
        // Disable form inputs during loading
        emailInput.disabled = loading;
        passwordInput.disabled = loading;
        if (rememberMeCheckbox) rememberMeCheckbox.disabled = loading;
    }

    function isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    // =====================================================
    // 2FA FORM (if needed)
    // =====================================================
    
    function show2FAForm(email) {
        console.log(' 2FA required for:', email);
        showError('Two-factor authentication is required. Please enter the OTP sent to your device.');
        
        // TODO: Show 2FA input modal or redirect to 2FA page
        // For now, just show a message
    }

    // =====================================================
    // SECURITY QUESTION FORM (if needed)
    // =====================================================
    
    function showSecurityQuestionForm(email) {
        console.log(' Security question required for:', email);
        showError('Please answer your security question to continue.');
        
        // TODO: Show security question modal or redirect to security question page
        // For now, just show a message
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

const style = document.createElement('style');
style.textContent = `
    .rotating {
        animation: rotate 1s linear infinite;
    }
    
    @keyframes rotate {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
`;
document.head.appendChild(style);