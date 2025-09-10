// ================================
// DISPLAY-MANAGER.JS - Display Management
// ================================

const DisplayManager = {
    showTeamDetails(teamData) {
        if (!teamData) {
            elements.teamDetails.innerHTML = "<p>No team data available</p>";
            return;
        }
        
        const stats = this.calculateTeamStats(teamData);
        
        elements.teamDetails.innerHTML = `
            <div class="team-summary">
                <h3>Team ${teamData.team_id}</h3>
                ${teamData.owner ? `<p><strong>Owner:</strong> ${teamData.owner}</p>` : ''}
                ${teamData.league_id ? `<p><strong>League:</strong> ${teamData.league_id}</p>` : ''}
                <div class="team-stats">
                    ${this.renderStatCard("Total Players", stats.playerCount)}
                    ${this.renderStatCard("Starters", stats.starterCount)}
                    ${this.renderStatCard("Bench", stats.benchCount)}
                    ${stats.hasScores ? this.renderStatCard("Week Total", `${stats.totalPoints.toFixed(1)} pts`) : ''}
                </div>
                ${teamData.last_updated ? `<p class="last-updated">Last updated: ${new Date(teamData.last_updated).toLocaleString()}</p>` : ''}
            </div>
        `;
    },

    showRoster(players) {
        if (!players || players.length === 0) {
            elements.rosterList.innerHTML = "<p>No players in roster</p>";
            return;
        }
        
        const { starters, bench } = this.separatePlayers(players);
        const lineupHTML = this.renderLineupSlots(starters, players);
        const benchHTML = this.renderBenchPlayers(bench, players);
        
        elements.rosterList.innerHTML = `
            <div class="roster-display">
                <div class="lineup-section">
                    <h3><i class="fas fa-star"></i> Starting Lineup</h3>
                    <div class="lineup-grid">${lineupHTML}</div>
                </div>
                ${bench.length > 0 ? `
                    <div class="bench-section">
                        <h3><i class="fas fa-users"></i> Bench Players</h3>
                        <div class="bench-grid">${benchHTML}</div>
                    </div>
                ` : ''}
            </div>
        `;
    },

    clearDisplays() {
        elements.teamDetails.innerHTML = "<p>Failed to load team details</p>";
        elements.rosterList.innerHTML = "<p>Failed to load roster</p>";
    },

    // Helper methods
    calculateTeamStats(teamData) {
        const playerCount = teamData.players ? teamData.players.length : 0;
        const starterCount = teamData.players ? teamData.players.filter(p => p.status === 'starter').length : 0;
        const benchCount = playerCount - starterCount;
        
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
        
        return { playerCount, starterCount, benchCount, totalPoints, hasScores };
    },

    renderStatCard(label, value) {
        return `
            <div class="stat">
                <span class="stat-label">${label}:</span>
                <span class="stat-value">${value}</span>
            </div>
        `;
    },

    separatePlayers(players) {
        return {
            starters: players.filter(p => p.status === 'starter'),
            bench: players.filter(p => p.status === 'bench')
        };
    },

    renderLineupSlots(starters, allPlayers) {
        return LINEUP_SLOTS.map(slot => {
            const player = starters.find(p => p.slot === slot.slot);
            const playerInfo = player ? this.renderPlayerInfo(player) : this.renderEmptySlot(slot);
            
            return `
                <div class="lineup-slot ${player ? 'filled' : 'empty'}" onclick="${player ? `editPlayer(${allPlayers.indexOf(player)})` : ''}">
                    <div class="slot-header">
                        <span class="slot-name">${slot.slot}</span>
                        <span class="slot-position">${Utils.getSlotDescription(slot.position)}</span>
                    </div>
                    ${playerInfo}
                </div>
            `;
        }).join('');
    },

    renderBenchPlayers(bench, allPlayers) {
        return bench.map(player => {
            const playerIndex = allPlayers.indexOf(player);
            return `
                <div class="player-card bench-player" onclick="editPlayer(${playerIndex})">
                    ${this.renderPlayerInfo(player)}
                </div>
            `;
        }).join('');
    },

    renderPlayerInfo(player) {
        return `
            <div class="player-info">
                <div class="player-name">${Utils.sanitizeHTML(player.name)}</div>
                <div class="player-details">${Utils.sanitizeHTML(player.team)} • ${Utils.sanitizeHTML(player.position)}</div>
                ${player.final_score !== undefined ? 
                    `<div class="final-score">${Utils.formatPoints(player.final_score)} pts</div>` : ''
                }
                ${player.opponent ? 
                    `<div class="opponent">vs ${Utils.sanitizeHTML(player.opponent)}</div>` : ''
                }
            </div>
        `;
    },

    renderEmptySlot(slot) {
        return `
            <div class="empty-slot" onclick="addPlayerToSlot('${slot.slot}')">
                <i class="fas fa-plus"></i> Add ${slot.position}
            </div>
        `;
    }
};