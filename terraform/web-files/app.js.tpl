// Configuration - Dynamically templated by Terraform
const API_CONFIG = {
    BASE_URL: "${api_endpoint}",
    TEAMS_ENDPOINT: "/teams",
    COACH_ENDPOINT: "/coach"
};

// Global state
let currentTeam = null;
let isEditing = false;

// DOM Elements
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
    
    // Form elements
    editPlayerIndex: document.getElementById("editPlayerIndex"),
    playerName: document.getElementById("playerName"),
    playerPosition: document.getElementById("playerPosition"),
    playerTeam: document.getElementById("playerTeam"),
    playerStatus: document.getElementById("playerStatus"),
    savePlayer: document.getElementById("savePlayer"),
    cancelEdit: document.getElementById("cancelEdit"),
    removePlayer: document.getElementById("removePlayer"),
    addPlayer: document.getElementById("addPlayer"),
    saveRoster: document.getElementById("saveRoster")
};

// Event Listeners
document.addEventListener("DOMContentLoaded", function() {
    initializeEventListeners();
    
    // Debug: Log the API endpoint for verification
    console.log("API Configuration loaded:", API_CONFIG);
    
    // Load team if teamId is already filled
    if (elements.teamId.value) {
        loadTeamData();
    }
});

function initializeEventListeners() {
    elements.loadTeam.addEventListener("click", loadTeamData);
    elements.editRoster.addEventListener("click", toggleEditMode);
    elements.generateAnalysis.addEventListener("click", generateWeeklyAnalysis);
    elements.savePlayer.addEventListener("click", savePlayer);
    elements.cancelEdit.addEventListener("click", cancelEdit);
    elements.removePlayer.addEventListener("click", removePlayer);
    elements.addPlayer.addEventListener("click", addNewPlayer);
    elements.saveRoster.addEventListener("click", saveRosterChanges);
    
    // Allow Enter key to load team
    elements.teamId.addEventListener("keypress", function(e) {
        if (e.key === "Enter") {
            loadTeamData();
        }
    });
    
    // Allow Enter key to generate analysis
    elements.weekNumber.addEventListener("keypress", function(e) {
        if (e.key === "Enter") {
            generateWeeklyAnalysis();
        }
    });
}

// API Functions
async function loadTeamData() {
    const teamId = elements.teamId.value.trim();
    if (!teamId) {
        showToast("Please enter a team ID", "error");
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.TEAMS_ENDPOINT}?team_id=${encodeURIComponent(teamId)}`);
        
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error("Team not found");
            }
            throw new Error(`Failed to load team data: ${response.status}`);
        }
        
        const teamData = await response.json();
        currentTeam = teamData;
        
        displayTeamInfo(teamData);
        displayRoster(teamData.players || []);
        showToast("Team loaded successfully", "success");
        
    } catch (error) {
        console.error("Error loading team:", error);
        showToast(error.message, "error");
        currentTeam = null;
        elements.teamDetails.innerHTML = "<p>Failed to load team data</p>";
        elements.rosterList.innerHTML = "<p>Failed to load roster</p>";
    } finally {
        showLoading(false);
    }
}

async function generateWeeklyAnalysis() {
    const teamId = elements.teamId.value.trim();
    const week = elements.weekNumber.value;
    
    if (!teamId) {
        showToast("Please load a team first", "error");
        return;
    }
    
    if (!week || week < 1 || week > 18) {
        showToast("Please enter a valid week number (1-18)", "error");
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.COACH_ENDPOINT}?team_id=${encodeURIComponent(teamId)}&week=${week}`);
        
        if (!response.ok) {
            throw new Error(`Failed to generate analysis: ${response.status}`);
        }
        
        const analysisData = await response.json();
        displayAnalysis(analysisData);
        showToast("Analysis generated successfully", "success");
        
    } catch (error) {
        console.error("Error generating analysis:", error);
        showToast(error.message, "error");
        elements.analysisResult.innerHTML = "<p>Failed to generate analysis</p>";
    } finally {
        showLoading(false);
    }
}

async function saveRosterChanges() {
    if (!currentTeam) {
        showToast("No team loaded", "error");
        return;
    }
    
    showLoading(true);
    
    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.TEAMS_ENDPOINT}`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(currentTeam)
        });
        
        if (!response.ok) {
            throw new Error(`Failed to save roster: ${response.status}`);
        }
        
        showToast("Roster saved successfully", "success");
        toggleEditMode(); // Exit edit mode
        
    } catch (error) {
        console.error("Error saving roster:", error);
        showToast(error.message, "error");
    } finally {
        showLoading(false);
    }
}

// Display Functions
function displayTeamInfo(teamData) {
    const playerCount = teamData.players ? teamData.players.length : 0;
    const starters = teamData.players ? teamData.players.filter(p => p.status === "starter").length : 0;
    const bench = playerCount - starters;
    
    elements.teamDetails.innerHTML = `
        <div class="team-details">
            <div class="detail-item">
                <strong>Team ID</strong>
                ${teamData.team_id}
            </div>
            <div class="detail-item">
                <strong>Owner</strong>
                ${teamData.owner || "N/A"}
            </div>
            <div class="detail-item">
                <strong>League ID</strong>
                ${teamData.league_id || "N/A"}
            </div>
            <div class="detail-item">
                <strong>Total Players</strong>
                ${playerCount}
            </div>
            <div class="detail-item">
                <strong>Starters</strong>
                ${starters}
            </div>
            <div class="detail-item">
                <strong>Bench</strong>
                ${bench}
            </div>
            <div class="detail-item">
                <strong>Last Updated</strong>
                ${new Date(teamData.last_updated).toLocaleDateString()}
            </div>
        </div>
    `;
}

function displayRoster(players) {
    if (!players || players.length === 0) {
        elements.rosterList.innerHTML = "<p>No players in roster</p>";
        return;
    }
    
    // Sort players by position and status
    const sortedPlayers = [...players].sort((a, b) => {
        const positionOrder = { "QB": 1, "RB": 2, "WR": 3, "TE": 4, "K": 5, "DST": 6 };
        const statusOrder = { "starter": 1, "bench": 2 };
        
        if (a.status !== b.status) {
            return statusOrder[a.status] - statusOrder[b.status];
        }
        return positionOrder[a.position] - positionOrder[b.position];
    });
    
    const rosterHTML = `
        <div class="roster-list">
            ${sortedPlayers.map((player, index) => `
                <div class="player-card ${player.status}" onclick="editPlayer(${index})" data-index="${index}">
                    <div class="player-info">
                        <div class="player-name">${player.name}</div>
                        <div class="player-details">
                            ${player.team} • ${player.position} • ${player.status}
                        </div>
                    </div>
                    <div class="position-badge">${player.position}</div>
                </div>
            `).join("")}
        </div>
    `;
    
    elements.rosterList.innerHTML = rosterHTML;
}

function displayAnalysis(analysisData) {
    if (!analysisData.lineup) {
        elements.analysisResult.innerHTML = "<p>No analysis data available</p>";
        return;
    }
    
    const lineupHTML = analysisData.lineup.map(player => `
        <div class="lineup-player starter">
            <div class="lineup-info">
                <div class="slot-name">${player.slot}</div>
                <div class="lineup-player-name">${player.player}</div>
                <div class="lineup-team">${player.team} • ${player.position}</div>
            </div>
            <div class="projections">
                <div class="projected">Proj: ${player.projected}</div>
                <div class="adjusted">Adj: ${player.adjusted}</div>
            </div>
        </div>
    `).join("");
    
    const benchHTML = analysisData.bench ? analysisData.bench.map(player => `
        <div class="bench-player">
            <div class="lineup-player-name">${player.player}</div>
            <div class="lineup-team">${player.position}</div>
            <div class="projections">
                <div class="projected">Proj: ${player.projected}</div>
                <div class="adjusted">Adj: ${player.adjusted}</div>
            </div>
        </div>
    `).join("") : "";
    
    elements.analysisResult.innerHTML = `
        <div class="lineup-section">
            <h3><i class="fas fa-star"></i> Optimal Lineup</h3>
            <div class="lineup-grid">
                ${lineupHTML}
            </div>
        </div>
        
        ${benchHTML ? `
            <div class="bench-section">
                <h3><i class="fas fa-users"></i> Bench Players</h3>
                <div class="bench-grid">
                    ${benchHTML}
                </div>
            </div>
        ` : ""}
        
        ${analysisData.explanations ? `
            <div class="explanations">
                <h4><i class="fas fa-lightbulb"></i> Analysis Explanation</h4>
                <p>${analysisData.explanations}</p>
            </div>
        ` : ""}
    `;
}

// Roster Management Functions
function toggleEditMode() {
    isEditing = !isEditing;
    elements.editRoster.innerHTML = isEditing ? 
        '<i class="fas fa-times"></i> Cancel Edit' : 
        '<i class="fas fa-edit"></i> Edit Roster';
    
    const playerCards = document.querySelectorAll(".player-card");
    playerCards.forEach(card => {
        card.style.cursor = isEditing ? "pointer" : "default";
    });
    
    if (!isEditing) {
        hideEditForm();
    }
}

function editPlayer(index) {
    if (!isEditing || !currentTeam || !currentTeam.players) return;
    
    const player = currentTeam.players[index];
    if (!player) return;
    
    elements.editPlayerIndex.value = index;
    elements.playerName.value = player.name;
    elements.playerPosition.value = player.position;
    elements.playerTeam.value = player.team;
    elements.playerStatus.value = player.status;
    
    showEditForm();
}

function addNewPlayer() {
    if (!isEditing) {
        showToast("Enable edit mode first", "warning");
        return;
    }
    
    if (!currentTeam) {
        currentTeam = {
            team_id: elements.teamId.value,
            players: []
        };
    }
    
    if (!currentTeam.players) {
        currentTeam.players = [];
    }
    
    elements.editPlayerIndex.value = -1; // -1 indicates new player
    elements.playerName.value = "";
    elements.playerPosition.value = "QB";
    elements.playerTeam.value = "";
    elements.playerStatus.value = "bench";
    
    showEditForm();
}

function savePlayer() {
    const index = parseInt(elements.editPlayerIndex.value);
    const playerData = {
        name: elements.playerName.value.trim(),
        position: elements.playerPosition.value,
        team: elements.playerTeam.value.trim().toUpperCase(),
        status: elements.playerStatus.value,
        player_id: generatePlayerId(elements.playerName.value, elements.playerPosition.value)
    };
    
    if (!playerData.name || !playerData.team) {
        showToast("Player name and team are required", "error");
        return;
    }
    
    if (!currentTeam.players) {
        currentTeam.players = [];
    }
    
    if (index === -1) {
        // Add new player
        currentTeam.players.push(playerData);
        showToast("Player added successfully", "success");
    } else {
        // Update existing player
        currentTeam.players[index] = playerData;
        showToast("Player updated successfully", "success");
    }
    
    displayRoster(currentTeam.players);
    hideEditForm();
}

function removePlayer() {
    const index = parseInt(elements.editPlayerIndex.value);
    
    if (index === -1) {
        hideEditForm();
        return;
    }
    
    if (confirm("Are you sure you want to remove this player?")) {
        currentTeam.players.splice(index, 1);
        displayRoster(currentTeam.players);
        hideEditForm();
        showToast("Player removed successfully", "success");
    }
}

function cancelEdit() {
    hideEditForm();
}

function showEditForm() {
    elements.editRosterForm.style.display = "block";
    elements.playerName.focus();
}

function hideEditForm() {
    elements.editRosterForm.style.display = "none";
}

// Utility Functions
function generatePlayerId(name, position) {
    return name.toLowerCase().replace(/\s+/g, "_") + "_" + position.toLowerCase();
}

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
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    }, 5000);
    
    // Remove on click
    toast.addEventListener("click", () => {
        if (toast.parentNode) {
            toast.parentNode.removeChild(toast);
        }
    });
}

function getToastIcon(type) {
    switch (type) {
        case "success": return "fa-check-circle";
        case "error": return "fa-exclamation-circle";
        case "warning": return "fa-exclamation-triangle";
        default: return "fa-info-circle";
    }
}

// Error Handling
window.addEventListener("error", function(e) {
    console.error("JavaScript Error:", e.error);
    showToast("An unexpected error occurred", "error");
});

// Handle fetch errors globally
window.addEventListener("unhandledrejection", function(e) {
    console.error("Unhandled Promise Rejection:", e.reason);
    if (e.reason instanceof TypeError && e.reason.message.includes("fetch")) {
        showToast("Network error: Please check your connection", "error");
    }
});

// Initialize app
console.log("Fantasy Football AI Coach loaded successfully");
console.log("API Configuration:", API_CONFIG);