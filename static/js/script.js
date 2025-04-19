// ===== SCROLL ANIMATION =====
document.addEventListener('DOMContentLoaded', () => {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('visible');
            }
        });
    }, { threshold: 0.3 });

    document.querySelectorAll('.career-hub-part, .quiz-step').forEach(el => {
        observer.observe(el);
    });
});

// ===== AUTH SYSTEM =====
let currentUser = null;
const authModal = document.getElementById('authModal');
const loginForm = document.querySelector('.manual-login');
const signupForm = document.querySelector('.manual-signup');

// Modal Controls
function showView(view) {
    document.getElementById('loginView').style.display = view === 'login' ? 'block' : 'none';
    document.getElementById('signupView').style.display = view === 'signup' ? 'block' : 'none';
    
    const errorMsg = document.querySelector('.error-message');
    if (errorMsg) errorMsg.remove();
}

function openModal(view = 'login') {
    authModal.style.display = 'flex';
    showView(view);
}

function closeModal() {
    authModal.style.display = 'none';
    loginForm.reset();
    signupForm.reset();
}

// Close modal when clicking outside
window.addEventListener('click', (e) => {
    if (e.target === authModal) {
        closeModal();
    }
});

// Form Handlers
loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = e.target.querySelector('input[type="email"]').value;
    const password = e.target.querySelector('input[type="password"]').value;
    await handleAuth('login', { email, password });
});

signupForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());
    
    if (data.password !== data.confirmPassword) {
        showError('Passwords do not match');
        return;
    }
    
    await handleAuth('register', data);
});

// Unified Auth Handler
async function handleAuth(action, data) {
    const endpoint = action === 'login' ? 'login' : 'register';
    const button = action === 'login' 
        ? loginForm.querySelector('button[type="submit"]') 
        : signupForm.querySelector('button[type="submit"]');

    try {
        button.disabled = true;
        button.innerHTML = `<i class="fas fa-spinner fa-spin"></i> ${action === 'login' ? 'Logging in...' : 'Signing up...'}`;

        // This would be your Flask API endpoint
        const response = await fetch(`/api/auth/${endpoint}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await response.json();

        if (!response.ok) throw new Error(result.message || 'Authentication failed');

        if (action === 'login') {
            localStorage.setItem('token', result.token);
            currentUser = result.user;
            showAlert('Login successful!', 'success');
            closeModal();
            updateUIForAuthState();
        } else {
            showAlert('Account created! Please login.', 'success');
            showView('login');
        }
    } catch (error) {
        showError(error.message);
    } finally {
        button.disabled = false;
        button.innerHTML = action === 'login' ? 'Login' : 'Sign Up';
    }
}

// Social Login Placeholders
function googleLogin() {
    showAlert('Google login would be implemented here', 'info');
}

// UI Utilities
function showAlert(message, type) {
    const alertBox = document.createElement('div');
    alertBox.className = `alert ${type}`;
    alertBox.innerHTML = `
        <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
        ${message}
    `;
    document.body.appendChild(alertBox);

    setTimeout(() => {
        alertBox.classList.add('fade-out');
        setTimeout(() => alertBox.remove(), 300);
    }, 3000);
}

function showError(message) {
    const existingError = document.querySelector('.error-message');
    if (existingError) existingError.remove();

    const errorElement = document.createElement('div');
    errorElement.className = 'error-message';
    errorElement.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;
    
    const currentView = document.activeElement.closest('form');
    currentView.insertBefore(errorElement, currentView.lastElementChild);
}

function updateUIForAuthState() {
    const authButton = document.querySelector('header .cta-btn');
    if (currentUser) {
        authButton.textContent = 'Dashboard';
        authButton.onclick = () => { window.location.href = '/dashboard'; };
    } else {
        authButton.textContent = 'Get Started';
        authButton.onclick = openModal;
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    const token = localStorage.getItem('token');
    if (token) {
        // Verify token with your Flask backend
        currentUser = { email: 'user@example.com' }; // Replace with actual verification
        updateUIForAuthState();
    }
});