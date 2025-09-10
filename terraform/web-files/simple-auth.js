// ================================
// SIMPLE-AUTH.JS - Basic Client-Side Authentication
// ================================

const SimpleAuth = {
    // Predefined users (in production, this should be server-side)
    users: {
        'admin': 'fantasy2025!',
    },

    // Session timeout (24 hours)
    sessionTimeout: 24 * 60 * 60 * 1000,

    // Initialize authentication
    init() {
        console.log('SimpleAuth initializing...');
        if (this.isAuthenticated()) {
            console.log('User is authenticated, showing app');
            this.showApp();
            // Setup logout after a short delay to ensure DOM is ready
            setTimeout(() => this.setupLogout(), 500);
        } else {
            console.log('User not authenticated, showing login');
            this.showLoginForm();
        }
    },

    // Check if user is authenticated
    isAuthenticated() {
        const session = localStorage.getItem('fantasy_auth_session');
        if (!session) {
            console.log('No session found');
            return false;
        }

        try {
            const sessionData = JSON.parse(session);
            const now = new Date().getTime();
            
            // Check if session is expired
            if (now > sessionData.expires) {
                console.log('Session expired');
                localStorage.removeItem('fantasy_auth_session');
                return false;
            }
            
            console.log('Valid session found for user:', sessionData.username);
            return true;
        } catch (error) {
            console.log('Error parsing session:', error);
            localStorage.removeItem('fantasy_auth_session');
            return false;
        }
    },

    // Show login form
    showLoginForm() {
        console.log('Displaying login form');
        
        // Force body to be visible and replace content
        document.body.style.display = 'block';
        document.body.style.margin = '0';
        document.body.style.padding = '0';
        
        document.body.innerHTML = `
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <div style="
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 0;
            ">
                <div style="
                    background: rgba(255, 255, 255, 0.95);
                    backdrop-filter: blur(10px);
                    border-radius: 15px;
                    padding: 40px;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                    width: 100%;
                    max-width: 400px;
                    margin: 20px;
                ">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="
                            color: #1e3c72;
                            font-size: 2rem;
                            margin-bottom: 10px;
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            gap: 10px;
                            margin: 0 0 10px 0;
                        ">
                            <i class="fas fa-football-ball"></i> 
                            Fantasy Football AI Coach
                        </h1>
                        <p style="color: #6c757d; font-size: 1rem; margin: 10px 0 0 0;">Please sign in to continue</p>
                    </div>
                    
                    <div id="errorMessage" style="
                        background: #f8d7da;
                        color: #721c24;
                        padding: 10px 15px;
                        border-radius: 6px;
                        margin-bottom: 15px;
                        border: 1px solid #f5c6cb;
                        display: none;
                    "></div>
                    
                    <form id="loginForm">
                        <div style="margin-bottom: 20px;">
                            <label style="
                                display: block;
                                margin-bottom: 8px;
                                font-weight: 600;
                                color: #333;
                            ">Username</label>
                            <input type="text" id="username" required style="
                                width: 100%;
                                padding: 12px 15px;
                                border: 2px solid #e0e0e0;
                                border-radius: 8px;
                                font-size: 1rem;
                                box-sizing: border-box;
                            " value="admin">
                        </div>
                        
                        <div style="margin-bottom: 20px;">
                            <label style="
                                display: block;
                                margin-bottom: 8px;
                                font-weight: 600;
                                color: #333;
                            ">Password</label>
                            <input type="password" id="password" required style="
                                width: 100%;
                                padding: 12px 15px;
                                border: 2px solid #e0e0e0;
                                border-radius: 8px;
                                font-size: 1rem;
                                box-sizing: border-box;
                            " value="fantasy2024!">
                        </div>
                        
                        <button type="submit" id="loginButton" style="
                            width: 100%;
                            padding: 12px;
                            background: linear-gradient(135deg, #ff6b35 0%, #f7931e 100%);
                            color: white;
                            border: none;
                            border-radius: 8px;
                            font-size: 1.1rem;
                            font-weight: 600;
                            cursor: pointer;
                            transition: all 0.3s ease;
                        ">
                            <i class="fas fa-sign-in-alt"></i> Sign In
                        </button>
                    </form>
                    
                    <div style="
                        margin-top: 20px;
                        padding: 15px;
                        background: #e3f2fd;
                        border-radius: 8px;
                        border-left: 4px solid #1976d2;
                    ">
                        <h4 style="margin: 0 0 10px 0; color: #1976d2;">Demo Credentials (pre-filled):</h4>
                        <p style="margin: 5px 0; font-size: 0.9rem; color: #333;">
                            <strong>Username:</strong> admin <strong>Password:</strong> fantasy2024!<br>
                            <strong>Username:</strong> coach <strong>Password:</strong> football123
                        </p>
                    </div>
                </div>
            </div>
        `;

        console.log('Login form HTML inserted');

        // Add event listener for login form
        setTimeout(() => {
            const loginForm = document.getElementById('loginForm');
            if (loginForm) {
                console.log('Adding login form event listener');
                loginForm.addEventListener('submit', (e) => {
                    e.preventDefault();
                    this.handleLogin();
                });
            } else {
                console.error('Login form not found after insertion');
            }
        }, 100);
    },

    // Handle login
    handleLogin() {
        console.log('Handling login...');
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        const errorDiv = document.getElementById('errorMessage');
        const loginButton = document.getElementById('loginButton');

        console.log('Login attempt for username:', username);

        // Clear previous errors
        errorDiv.style.display = 'none';
        
        // Disable button during login
        loginButton.disabled = true;
        loginButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing in...';

        // Check credentials
        if (this.users[username] && this.users[username] === password) {
            console.log('Login successful for user:', username);
            
            // Create session
            const sessionData = {
                username: username,
                loginTime: new Date().getTime(),
                expires: new Date().getTime() + this.sessionTimeout
            };
            
            localStorage.setItem('fantasy_auth_session', JSON.stringify(sessionData));
            console.log('Session created, reloading page');
            
            // Reload page to show main app
            window.location.reload();
        } else {
            console.log('Login failed for user:', username);
            errorDiv.textContent = 'Invalid username or password';
            errorDiv.style.display = 'block';
            
            // Re-enable button
            loginButton.disabled = false;
            loginButton.innerHTML = '<i class="fas fa-sign-in-alt"></i> Sign In';
        }
    },

    // Show the main application
    showApp() {
        console.log('Showing main app');
        // App is already loaded, just make sure it's visible
        document.body.style.display = 'block';
        
        // Trigger app initialization
        if (typeof initializeApp === 'function') {
            console.log('Calling initializeApp');
            initializeApp();
        }
    },

    // Setup logout functionality
    setupLogout() {
        console.log('Setting up logout functionality');
        
        // Find the team selector in the header
        const teamSelector = document.querySelector('.header .team-selector');
        if (teamSelector && !document.getElementById('logoutBtn')) {
            // Add user info
            const session = JSON.parse(localStorage.getItem('fantasy_auth_session'));
            const userInfo = document.createElement('span');
            userInfo.style.cssText = 'margin-left: 15px; color: #1e3c72; font-weight: 500; margin-right: 15px;';
            userInfo.textContent = `Welcome, ${session.username}`;
            teamSelector.appendChild(userInfo);
            
            // Add logout button
            const logoutBtn = document.createElement('button');
            logoutBtn.id = 'logoutBtn';
            logoutBtn.className = 'btn btn-secondary';
            logoutBtn.innerHTML = '<i class="fas fa-sign-out-alt"></i> Logout';
            logoutBtn.onclick = this.logout.bind(this);
            teamSelector.appendChild(logoutBtn);
            
            console.log('Logout button and user info added');
        }
    },

    // Logout function
    logout() {
        console.log('Logging out...');
        localStorage.removeItem('fantasy_auth_session');
        window.location.reload();
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing SimpleAuth');
    // Hide app initially
    document.body.style.display = 'none';
    
    // Initialize simple auth
    SimpleAuth.init();
});