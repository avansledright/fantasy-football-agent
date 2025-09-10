// ================================
// MAIN APP.JS - Core functionality only
// ================================

// Configuration - Dynamically templated by Terraform
const API_CONFIG = {
    BASE_URL: "${api_endpoint}",
    TEAMS_ENDPOINT: "/teams",
    COACH_ENDPOINT: "/coach"
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
const elements = {
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

// ================================
// INITIALIZATION
// ================================

document.addEventListener("DOMContentLoaded", function () {
    initializeEventListeners();
    console.log("API Configuration loaded:", API_CONFIG);
    if (elements.teamId.value) {
        loadTeamData();
    }
});

function initializeEventListeners() {
    elements.loadTeam.addEventListener("click", loadTeamData);
    elements.editRoster.addEventListener("click", RosterManager.toggleEditMode);
    elements.generateAnalysis.addEventListener("click", generateWeeklyAnalysis);
    elements.savePlayer.addEventListener("click", RosterManager.savePlayer);
    elements.cancelEdit.addEventListener("click", RosterManager.cancelEdit);
    elements.removePlayer.addEventListener("click", RosterManager.removePlayer);
    elements.addPlayer.addEventListener("click", RosterManager.addNewPlayer);
    elements.saveRoster.addEventListener("click", saveRosterChanges);
    
    // Keyboard shortcuts
    elements.teamId.addEventListener("keypress", e => e.key === "Enter" && loadTeamData());
    elements.weekNumber.addEventListener("keypress", e => e.key === "Enter" && generateWeeklyAnalysis());
    elements.weekNumber.addEventListener("change", () => {
        if (currentTeam && elements.teamId.value.trim()) {
            loadTeamData();
        }
    });
}

// ================================
// API FUNCTIONS
// ================================

async function loadTeamData() {
    const teamId = elements.teamId.value.trim();
    const week = elements.weekNumber.value.trim();
    
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
        elements.analysisResult.innerHTML = "<p>Failed to generate analysis</p>";
    } finally {
        showLoading(false);
    }
}

async function saveRosterChanges() {
    if (!currentTeam) {
        showToast("No team data to save", "warning");
        return;
    }
    
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
    elements.loadingOverlay.style.display = show ? "flex" : "none";
}

function showToast(message, type = "info") {
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