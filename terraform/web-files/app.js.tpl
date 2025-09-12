// ================================
// MAIN APP.JS - Core functionality with Chat Integration
// ================================

// Configuration - Dynamically templated by Terraform
const API_CONFIG = {
    BASE_URL: "${api_endpoint}",
    TEAMS_ENDPOINT: "/teams",
    COACH_ENDPOINT: "/coach",
    CHAT_ENDPOINT: "/chat"  // New chat endpoint
};

// Starting lineup configuration
const LINEUP_SLOTS = [
    { position: "QB", slot: "QB", maxCount: 1 },
    { position: "RB", slot: "RB1", maxCount: 1 },
    { position: "RB", slot: "RB2", maxCount: 1 },
    { position: "WR", slot: "WR1", maxCount: 1 },
    { position: "WR", slot: "WR2", maxCount: 1 },
    { position: "TE", slot: "TE", maxCount: 1 },
    { position: "FLEX", slot: "FLEX", maxCount: 1 },
    { position: "OP", slot: "OP", maxCount: 1 },
    { position: "K", slot: "K", maxCount: 1 },
    { position: "DST", slot: "DST", maxCount: 1 }
];

// Global state
let currentTeam = null;
let isEditing = false;

// DOM Elements cache
let elements = {};

// ================================
// INITIALIZATION - Make initializeApp global for auth system
// ================================

// REMOVED the DOMContentLoaded listener - auth system will handle initialization

// Make initializeApp globally accessible for the auth system
window.initializeApp = function initializeApp() {
    console.log('Initializing main app...');
    
    // Wait a bit for DOM elements to be ready
    setTimeout(() => {
        // Cache DOM elements
        cacheElements();
        setCurrentWeek();
        // Initialize event listeners
        initializeEventListeners();
        
        console.log("API Configuration loaded:", API_CONFIG);
        
        // Initialize Chat Feature
        initializeChatFeature();
        
        // Load team if teamId is pre-filled
        if (elements.teamId && elements.teamId.value) {
            loadTeamData();
        }
    }, 100);
}

function cacheElements() {
    console.log('Caching DOM elements...');
    
    elements = {
        teamId: document.getElementById("teamId"),
        loadTeam: document.getElementById("loadTeam"),
        teamDetails: document.getElementById("teamDetails"),
        rosterList: document.getElementById("rosterList"),
        editRoster: document.getElementById("editRoster"),
        editRosterForm: document.getElementById("editRosterForm"),
        weekNumber: document.getElementById("weekNumber"),
        generateAnalysis: document.getElementById("generateAnalysis"),
        analysisResult: document.getElementById("analysisResult"),
        loadingOverlay: document.getElementById("loadingOverlay"),
        toastContainer: document.getElementById("toastContainer"),
        editPlayerIndex: document.getElementById("editPlayerIndex"),
        playerName: document.getElementById("playerName"),
        playerPosition: document.getElementById("playerPosition"),
        playerTeam: document.getElementById("playerTeam"),
        playerStatus: document.getElementById("playerStatus"),
        playerSlot: document.getElementById("playerSlot"),
        savePlayer: document.getElementById("savePlayer"),
        cancelEdit: document.getElementById("cancelEdit"),
        removePlayer: document.getElementById("removePlayer"),
        addPlayer: document.getElementById("addPlayer"),
        saveRoster: document.getElementById("saveRoster")
    };
    
    console.log('Elements cached:', Object.keys(elements).length);
}

function initializeEventListeners() {
    console.log('Setting up event listeners...');
    
    // Check if elements exist before adding listeners
    if (elements.loadTeam) elements.loadTeam.addEventListener("click", loadTeamData);
    if (elements.editRoster) elements.editRoster.addEventListener("click", RosterManager.toggleEditMode);
    if (elements.generateAnalysis) elements.generateAnalysis.addEventListener("click", generateWeeklyAnalysis);
    if (elements.savePlayer) elements.savePlayer.addEventListener("click", RosterManager.savePlayer);
    if (elements.cancelEdit) elements.cancelEdit.addEventListener("click", RosterManager.cancelEdit);
    if (elements.removePlayer) elements.removePlayer.addEventListener("click", RosterManager.removePlayer);
    if (elements.addPlayer) elements.addPlayer.addEventListener("click", RosterManager.addNewPlayer);
    if (elements.saveRoster) elements.saveRoster.addEventListener("click", saveRosterChanges);
    
    // Keyboard shortcuts
    if (elements.teamId) {
        elements.teamId.addEventListener("keypress", e => e.key === "Enter" && loadTeamData());
    }
    if (elements.weekNumber) {
        elements.weekNumber.addEventListener("keypress", e => e.key === "Enter" && generateWeeklyAnalysis());
        elements.weekNumber.addEventListener("change", () => {
            if (currentTeam && elements.teamId && elements.teamId.value.trim()) {
                loadTeamData();
            }
        });
    }
    
    console.log('Event listeners set up');
}

function initializeChatFeature() {
    console.log('Initializing chat feature...');
    
    // Check if ChatManager exists before initializing
    if (typeof ChatManager !== 'undefined') {
        ChatManager.initialize();
        
        // Add chat context helpers
        window.sendTeamContextToChat = function() {
            if (currentTeam && elements.teamId && elements.weekNumber) {
                const context = `My team ID is ${elements.teamId.value} for week ${elements.weekNumber.value}. Current roster has ${currentTeam.players ? currentTeam.players.length : 0} players.`;
                ChatManager.sendProgrammaticMessage(context);
            }
        };
        
        console.log('Chat feature initialized successfully');
    } else {
        console.warn('ChatManager not found - chat feature not available');
    }
}

// ================================
// API FUNCTIONS
// ================================

async function loadTeamData() {
    if (!elements.teamId) return;
    
    const teamId = elements.teamId.value.trim();
    const week = elements.weekNumber ? elements.weekNumber.value.trim() : '';
    
    if (!APIHelper.validateInputs(teamId, week)) return;
    
    showLoading(true);
    
    try {
        const queryParams = APIHelper.buildQueryParams(teamId, week);
        const response = await APIHelper.fetchTeamData(queryParams);
        
        currentTeam = response;
        DisplayManager.showTeamDetails(response);
        DisplayManager.showRoster(response.players || []);
        
        const message = week ? 
            `Team loaded successfully with Week ${week} stats` : 
            "Team loaded successfully";
        showToast(message, "success");
        
    } catch (error) {
        console.error('Error loading team data:', error);
        showToast(`Error loading team: ${error.message}`, "error");
        DisplayManager.clearDisplays();
        currentTeam = null;
    } finally {
        showLoading(false);
    }
}

async function generateWeeklyAnalysis() {
    if (!elements.teamId || !elements.weekNumber) return;
    
    const teamId = elements.teamId.value.trim();
    const week = elements.weekNumber.value.trim();
    
    if (!teamId) {
        showToast("Please enter a team ID", "error");
        return;
    }
    
    if (!week || week < 1 || week > 18) {
        showToast("Please enter a valid week number (1-18)", "error");
        return;
    }
    
    if (!currentTeam || !currentTeam.players || currentTeam.players.length === 0) {
        showToast("Please load a team first", "warning");
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.COACH_ENDPOINT}?team_id=${encodeURIComponent(teamId)}&week=${week}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const analysisData = await response.json();
        DashboardRenderer.render(analysisData);
        
        showToast("Analysis generated successfully", "success");
        
    } catch (error) {
        console.error('Error generating analysis:', error);
        showToast(`Error generating analysis: ${error.message}`, "error");
        if (elements.analysisResult) {
            elements.analysisResult.innerHTML = "<p>Failed to generate analysis</p>";
        }
    } finally {
        showLoading(false);
    }
}

async function saveRosterChanges() {
    if (!currentTeam) {
        showToast("No team data to save", "warning");
        return;
    }
    
    if (!elements.teamId) return;
    
    const teamId = elements.teamId.value.trim();
    if (!teamId) {
        showToast("Please enter a team ID", "error");
        return;
    }
    
    showLoading(true);
    
    try {
        await APIHelper.saveRoster(teamId, currentTeam);
        showToast("Roster saved successfully", "success");
        
    } catch (error) {
        console.error('Error saving roster:', error);
        showToast(`Error saving roster: ${error.message}`, "error");
    } finally {
        showLoading(false);
    }
}

// ================================
// UTILITY FUNCTIONS
// ================================

function showLoading(show) {
    if (elements.loadingOverlay) {
        elements.loadingOverlay.style.display = show ? "flex" : "none";
    }
}

function showToast(message, type = "info") {
    if (!elements.toastContainer) return;
    
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="fas ${getToastIcon(type)}"></i>
            <span>${message}</span>
        </div>
    `;

    elements.toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
    toast.addEventListener("click", () => toast.remove());
}

function getToastIcon(type) {
    const icons = {
        success: "fa-check-circle",
        error: "fa-exclamation-circle", 
        warning: "fa-exclamation-triangle",
        info: "fa-info-circle"
    };
    return icons[type] || icons.info;
}

function setCurrentWeek() {
    if (elements.weekNumber) {
        const currentWeek = Utils.getCurrentNFLWeek();
        elements.weekNumber.value = currentWeek;
        
        // Optional: Add a visual indicator of the season status
        const seasonStatus = Utils.getNFLSeasonStatus();
        console.log(`Current NFL Week: ${currentWeek} (${seasonStatus} season)`);
        
        // You could also show a toast notification
        if (seasonStatus === 'preseason') {
            showToast(`Season hasn't started yet. Defaulting to Week 1`, "info");
        } else if (seasonStatus === 'postseason') {
            showToast(`Regular season ended. Showing Week 18`, "info");
        } else {
            showToast(`Current NFL Week: ${currentWeek}`, "success");
        }
    }
}

// ================================
// CHAT INTEGRATION HELPERS
// ================================

// Global helper functions for chat integration
window.getChatContext = function() {
    return {
        teamId: elements.teamId ? elements.teamId.value.trim() : '',
        week: elements.weekNumber ? elements.weekNumber.value.trim() : '',
        currentTeam: currentTeam,
        isEditing: isEditing,
        seasonStatus: Utils.getNFLSeasonStatus()
    };
};

window.sendQuickChatMessage = function(message) {
    if (typeof ChatManager !== 'undefined') {
        ChatManager.sendProgrammaticMessage(message);
    }
};

// Error handling
window.addEventListener("error", e => {
    console.error("JavaScript Error:", e.error);
    showToast("An unexpected error occurred", "error");
});

window.addEventListener("unhandledrejection", e => {
    console.error("Unhandled Promise Rejection:", e.reason);
    if (e.reason instanceof TypeError && e.reason.message.includes("fetch")) {
        showToast("Network error: Please check your connection", "error");
    }
});

console.log("Fantasy Football AI Coach loaded successfully");