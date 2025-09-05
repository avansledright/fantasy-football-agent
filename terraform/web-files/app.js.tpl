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
    
    // Organize players by their assigned slots
    const organizedRoster = organizePlayersIntoLineup(players);
    
    const rosterHTML = `
        <div class="lineup-container">
            <div class="starting-lineup">
                <h3><i class="fas fa-star"></i> Starting Lineup</h3>
                <div class="lineup-slots">
                    ${LINEUP_SLOTS.map(slot => generateSlotHTML(slot, organizedRoster.starters[slot.slot])).join("")}
                </div>
            </div>
            
            <div class="bench-players">
                <h3><i class="fas fa-users"></i> Bench Players</h3>
                <div class="bench-list">
                    ${organizedRoster.bench.map((player, index) => `
                        <div class="player-card bench" onclick="editPlayer(${players.indexOf(player)})" data-index="${players.indexOf(player)}">
                            <div class="player-info">
                                <div class="player-name">${player.name}</div>
                                <div class="player-details">
                                    ${player.team} • ${player.position}
                                </div>
                            </div>
                            <div class="position-badge">${player.position}</div>
                        </div>
                    `).join("")}
                </div>
            </div>
        </div>
    `;
    
    elements.rosterList.innerHTML = rosterHTML;
}

function organizePlayersIntoLineup(players) {
    const starters = {};
    const bench = [];
    
    // Initialize empty slots
    LINEUP_SLOTS.forEach(slot => {
        starters[slot.slot] = null;
    });
    
    // Sort players by status and position priority
    const sortedPlayers = [...players].sort((a, b) => {
        if (a.status !== b.status) {
            return a.status === "starter" ? -1 : 1;
        }
        return 0;
    });
    
    // Place players in lineup slots
    for (const player of sortedPlayers) {
        if (player.status === "starter") {
            // If player has a specific slot assigned, use it
            if (player.slot && starters[player.slot] === null) {
                starters[player.slot] = player;
                continue;
            }
            
            // Auto-assign to appropriate slot
            const assignedSlot = findAvailableSlot(player, starters);
            if (assignedSlot) {
                starters[assignedSlot] = player;
                // Update player's slot assignment
                player.slot = assignedSlot;
            } else {
                // No available starter slot, move to bench
                player.status = "bench";
                bench.push(player);
            }
        } else {
            bench.push(player);
        }
    }
    
    return { starters, bench };
}

function findAvailableSlot(player, starters) {
    // First, try to find exact position match
    for (const slot of LINEUP_SLOTS) {
        if (starters[slot.slot] === null && isPlayerEligibleForSlot(player, slot)) {
            return slot.slot;
        }
    }
    return null;
}

function isPlayerEligibleForSlot(player, slot) {
    const position = player.position;
    
    switch (slot.position) {
        case "QB":
            return position === "QB";
        case "RB":
            return position === "RB";
        case "WR":
            return position === "WR";
        case "TE":
            return position === "TE";
        case "K":
            return position === "K";
        case "DST":
            return position === "DST";
        case "FLEX":
            return ["RB", "WR", "TE"].includes(position);
        case "OP":
            return ["QB", "RB", "WR", "TE"].includes(position);
        default:
            return false;
    }
}

function generateSlotHTML(slot, player) {
    const playerId = player ? currentTeam.players.indexOf(player) : -1;
    
    return `
        <div class="lineup-slot ${player ? 'filled' : 'empty'}" 
             data-slot="${slot.slot}" 
             ${player ? `onclick="editPlayer(${playerId})" data-index="${playerId}"` : `onclick="addPlayerToSlot('${slot.slot}')"`}>
            <div class="slot-header">
                <span class="slot-name">${slot.slot}</span>
                <span class="slot-position">${getSlotDescription(slot.position)}</span>
            </div>
            <div class="slot-content">
                ${player ? `
                    <div class="player-info">
                        <div class="player-name">${player.name}</div>
                        <div class="player-details">
                            ${player.team} • ${player.position}
                        </div>
                    </div>
                    <div class="position-badge">${player.position}</div>
                ` : `
                    <div class="empty-slot">
                        <i class="fas fa-plus"></i>
                        <span>Add Player</span>
                    </div>
                `}
            </div>
        </div>
    `;
}

function getSlotDescription(position) {
    switch (position) {
        case "FLEX": return "RB/WR/TE";
        case "OP": return "QB/RB/WR/TE";
        default: return position;
    }
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
    
    const playerCards = document.querySelectorAll(".player-card, .lineup-slot");
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