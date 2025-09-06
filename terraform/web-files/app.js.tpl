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
    { position: "FLEX", slot: "FLEX", maxCount: 1 }, // RB/WR/TE eligible
    { position: "OP", slot: "OP", maxCount: 1 }, // Offensive Player (QB/RB/WR/TE)
    { position: "K", slot: "K", maxCount: 1 },
    { position: "DST", slot: "DST", maxCount: 1 }
];

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
    playerSlot: document.getElementById("playerSlot"),
    savePlayer: document.getElementById("savePlayer"),
    cancelEdit: document.getElementById("cancelEdit"),
    removePlayer: document.getElementById("removePlayer"),
    addPlayer: document.getElementById("addPlayer"),
    saveRoster: document.getElementById("saveRoster")
};

// Event Listeners
document.addEventListener("DOMContentLoaded", function () {
    initializeEventListeners();
    console.log("API Configuration loaded:", API_CONFIG);
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
    elements.teamId.addEventListener("keypress", function (e) {
        if (e.key === "Enter") {
            loadTeamData();
        }
    });
    elements.weekNumber.addEventListener("keypress", function (e) {
        if (e.key === "Enter") {
            generateWeeklyAnalysis();
        }
    });
    
    // Auto-reload roster when week number changes (if team is loaded)
    elements.weekNumber.addEventListener("change", function () {
        if (currentTeam && elements.teamId.value.trim()) {
            loadTeamData();
        }
    });
}

// API Functions
async function loadTeamData() {
    const teamId = elements.teamId.value.trim();
    const week = elements.weekNumber.value.trim();
    
    if (!teamId) {
        showToast("Please enter a team ID", "error");
        return;
    }
    
    // Validate week number if provided
    if (week && (isNaN(week) || week < 1 || week > 18)) {
        showToast("Please enter a valid week number (1-18)", "error");
        return;
    }
    
    showLoading(true);
    
    try {
        // Build query parameters
        let queryParams = `team_id=${encodeURIComponent(teamId)}`;
        if (week) {
            queryParams += `&week=${encodeURIComponent(week)}`;
        }
        
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.TEAMS_ENDPOINT}?${queryParams}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Team not found');
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const teamData = await response.json();
        currentTeam = teamData;
        
        displayTeamDetails(teamData);
        displayRoster(teamData.players || []);
        
        const message = week ? 
            `Team loaded successfully with Week ${week} stats` : 
            "Team loaded successfully";
        showToast(message, "success");
        
    } catch (error) {
        console.error('Error loading team data:', error);
        showToast(`Error loading team: ${error.message}`, "error");
        
        // Clear displays on error
        elements.teamDetails.innerHTML = "<p>Failed to load team details</p>";
        elements.rosterList.innerHTML = "<p>Failed to load roster</p>";
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
        displayAnalysis(analysisData);
        
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
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.TEAMS_ENDPOINT}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                team_id: teamId,
                players: currentTeam.players || [],
                league_id: currentTeam.league_id,
                owner: currentTeam.owner
            })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        showToast("Roster saved successfully", "success");
        
    } catch (error) {
        console.error('Error saving roster:', error);
        showToast(`Error saving roster: ${error.message}`, "error");
    } finally {
        showLoading(false);
    }
}

// Display Functions
function displayTeamDetails(teamData) {
    if (!teamData) {
        elements.teamDetails.innerHTML = "<p>No team data available</p>";
        return;
    }
    
    const playerCount = teamData.players ? teamData.players.length : 0;
    const starterCount = teamData.players ? teamData.players.filter(p => p.status === 'starter').length : 0;
    const benchCount = playerCount - starterCount;
    
    // Calculate total team points if final scores are available
    let totalPoints = 0;
    let hasScores = false;
    if (teamData.players) {
        teamData.players.forEach(player => {
            if (player.final_score !== undefined && player.status === 'starter') {
                totalPoints += player.final_score;
                hasScores = true;
            }
        });
    }
    
    elements.teamDetails.innerHTML = `
        <div class="team-summary">
            <h3>Team ${teamData.team_id}</h3>
            ${teamData.owner ? `<p><strong>Owner:</strong> ${teamData.owner}</p>` : ''}
            ${teamData.league_id ? `<p><strong>League:</strong> ${teamData.league_id}</p>` : ''}
            <div class="team-stats">
                <div class="stat">
                    <span class="stat-label">Total Players:</span>
                    <span class="stat-value">${playerCount}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Starters:</span>
                    <span class="stat-value">${starterCount}</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Bench:</span>
                    <span class="stat-value">${benchCount}</span>
                </div>
                ${hasScores ? `
                <div class="stat">
                    <span class="stat-label">Week Total:</span>
                    <span class="stat-value">${totalPoints.toFixed(1)} pts</span>
                </div>
                ` : ''}
            </div>
            ${teamData.last_updated ? `<p class="last-updated">Last updated: ${new Date(teamData.last_updated).toLocaleString()}</p>` : ''}
        </div>
    `;
}

function displayRoster(players) {
    if (!players || players.length === 0) {
        elements.rosterList.innerHTML = "<p>No players in roster</p>";
        return;
    }
    
    // Separate starters and bench players
    const starters = players.filter(p => p.status === 'starter');
    const bench = players.filter(p => p.status === 'bench');
    
    // Create lineup slots display
    const lineupHTML = LINEUP_SLOTS.map(slot => {
        const player = starters.find(p => p.slot === slot.slot);
        const playerInfo = player ? `
            <div class="player-info">
                <div class="player-name">${sanitizeHTML(player.name)}</div>
                <div class="player-details">${sanitizeHTML(player.team)} • ${sanitizeHTML(player.position)}</div>
                ${player.final_score !== undefined ? 
                    `<div class="final-score">${formatPoints(player.final_score)} pts</div>` : ''
                }
                ${player.opponent ? 
                    `<div class="opponent">vs ${sanitizeHTML(player.opponent)}</div>` : ''
                }
            </div>
        ` : `
            <div class="empty-slot" onclick="addPlayerToSlot('${slot.slot}')">
                <i class="fas fa-plus"></i> Add ${slot.position}
            </div>
        `;
        
        return `
            <div class="lineup-slot ${player ? 'filled' : 'empty'}" onclick="${player ? `editPlayer(${players.indexOf(player)})` : ''}">
                <div class="slot-header">
                    <span class="slot-name">${slot.slot}</span>
                    <span class="slot-position">${getSlotDescription(slot.position)}</span>
                </div>
                ${playerInfo}
            </div>
        `;
    }).join('');
    
    // Create bench players display
    const benchHTML = bench.map((player, index) => {
        const playerIndex = players.indexOf(player);
        return `
            <div class="player-card bench-player" onclick="editPlayer(${playerIndex})">
                <div class="player-info">
                    <div class="player-name">${sanitizeHTML(player.name)}</div>
                    <div class="player-details">${sanitizeHTML(player.team)} • ${sanitizeHTML(player.position)}</div>
                    ${player.final_score !== undefined ? 
                        `<div class="final-score">${formatPoints(player.final_score)} pts</div>` : ''
                    }
                    ${player.opponent ? 
                        `<div class="opponent">vs ${sanitizeHTML(player.opponent)}</div>` : ''
                    }
                </div>
            </div>
        `;
    }).join('');
    
    elements.rosterList.innerHTML = `
        <div class="roster-display">
            <div class="lineup-section">
                <h3><i class="fas fa-star"></i> Starting Lineup</h3>
                <div class="lineup-grid">
                    ${lineupHTML}
                </div>
            </div>
            
            ${bench.length > 0 ? `
                <div class="bench-section">
                    <h3><i class="fas fa-users"></i> Bench Players</h3>
                    <div class="bench-grid">
                        ${benchHTML}
                    </div>
                </div>
            ` : ''}
        </div>
    `;
}

function displayAnalysis(analysisData) {
    if (!analysisData.lineup) {
        elements.analysisResult.innerHTML = "<p>No analysis data available</p>";
        return;
    }

    const lineupHTML = analysisData.lineup.map(player => `
        <div class="lineup-player starter">
            <div class="lineup-info">
                <div class="slot-name">${sanitizeHTML(player.slot)}</div>
                <div class="lineup-player-name">${sanitizeHTML(player.player)}</div>
                <div class="lineup-team">${sanitizeHTML(player.team)} • ${sanitizeHTML(player.position)}</div>
            </div>
            <div class="projections">
                <div class="projected">Proj: ${formatPoints(player.projected)}</div>
                <div class="adjusted">Adj: ${formatPoints(player.adjusted)}</div>
            </div>
        </div>
    `).join("");

    const benchHTML = analysisData.bench ? analysisData.bench.map(player => `
        <div class="bench-player">
            <div class="lineup-player-name">${sanitizeHTML(player.player)}</div>
            <div class="lineup-team">${sanitizeHTML(player.position)}</div>
            <div class="projections">
                <div class="projected">Proj: ${formatPoints(player.projected)}</div>
                <div class="adjusted">Adj: ${formatPoints(player.adjusted)}</div>
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
                <p>${sanitizeHTML(analysisData.explanations)}</p>
            </div>
        ` : ""}
    `;
}

function getSlotDescription(position) {
    switch (position) {
        case "FLEX": return "RB/WR/TE";
        case "OP": return "QB/RB/WR/TE";
        default: return position;
    }
}

// Utility Functions
function formatPoints(points) {
    if (points === undefined || points === null) return "0.0";
    return parseFloat(points).toFixed(1);
}

function sanitizeHTML(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// Roster Management Functions
function toggleEditMode() {
    isEditing = !isEditing;
    elements.editRoster.innerHTML = isEditing ?
        '<i class="fas fa-times"></i> Cancel Edit' :
        '<i class="fas fa-edit"></i> Edit Roster';

    const playerCards = document.querySelectorAll(".player-card, .lineup-slot");
    playerCards.forEach(card => {
        card.style.cursor = isEditing ? "pointer" : "default";
    });

    if (!isEditing) {
        hideEditForm();
    }
    
    showToast(isEditing ? "Edit mode enabled" : "Edit mode disabled", "info");
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

    // Update slot dropdown with available options
    updateSlotDropdown(player);
    elements.playerSlot.value = player.slot || "";

    showEditForm();
}

function addPlayerToSlot(slotName) {
    if (!isEditing) {
        showToast("Enable edit mode first", "warning");
        return;
    }

    addNewPlayer(slotName);
}

function addNewPlayer(targetSlot = null) {
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
    elements.playerStatus.value = targetSlot ? "starter" : "bench";

    // Update slot dropdown and set target slot if specified
    updateSlotDropdown({ position: "QB" });
    elements.playerSlot.value = targetSlot || "";

    showEditForm();
}

function updateSlotDropdown(player) {
    const slotSelect = elements.playerSlot;
    slotSelect.innerHTML = '<option value="">Select Slot (optional)</option>';

    // Add bench option
    slotSelect.innerHTML += '<option value="bench">Bench</option>';

    // Add available starter slots based on player position
    LINEUP_SLOTS.forEach(slot => {
        if (isPlayerEligibleForSlot(player, slot)) {
            slotSelect.innerHTML += `<option value="${slot.slot}">${slot.slot} (${getSlotDescription(slot.position)})</option>`;
        }
    });
}

function isPlayerEligibleForSlot(player, slot) {
    if (!player || !slot) return false;
    
    const playerPos = player.position;
    const slotPos = slot.position;
    
    // Direct position match
    if (playerPos === slotPos) return true;
    
    // FLEX slot eligibility (RB/WR/TE)
    if (slotPos === "FLEX" && ["RB", "WR", "TE"].includes(playerPos)) return true;
    
    // OP slot eligibility (QB/RB/WR/TE)
    if (slotPos === "OP" && ["QB", "RB", "WR", "TE"].includes(playerPos)) return true;
    
    return false;
}

function savePlayer() {
    const index = parseInt(elements.editPlayerIndex.value);
    const playerData = {
        name: elements.playerName.value.trim(),
        position: elements.playerPosition.value,
        team: elements.playerTeam.value.trim().toUpperCase(),
        status: elements.playerStatus.value,
        slot: elements.playerSlot.value === "bench" ? null : elements.playerSlot.value,
        player_id: generatePlayerId(elements.playerName.value, elements.playerPosition.value)
    };

    // Adjust status based on slot selection
    if (playerData.slot && playerData.slot !== "bench") {
        playerData.status = "starter";
    } else if (playerData.slot === "bench" || !playerData.slot) {
        playerData.status = "bench";
        playerData.slot = null;
    }

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
window.addEventListener("error", function (e) {
    console.error("JavaScript Error:", e.error);
    showToast("An unexpected error occurred", "error");
});

// Handle fetch errors globally
window.addEventListener("unhandledrejection", function (e) {
    console.error("Unhandled Promise Rejection:", e.reason);
    if (e.reason instanceof TypeError && e.reason.message.includes("fetch")) {
        showToast("Network error: Please check your connection", "error");
    }
});

// Initialize app
console.log("Fantasy Football AI Coach loaded successfully");
console.log("API Configuration:", API_CONFIG);