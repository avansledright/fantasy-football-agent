// ================================
// API-HELPER.JS - API Management
// ================================

const APIHelper = {
    validateInputs(teamId, week) {
        if (!teamId) {
            showToast("Please enter a team ID", "error");
            return false;
        }
        
        if (week && (isNaN(week) || week < 1 || week > 18)) {
            showToast("Please enter a valid week number (1-18)", "error");
            return false;
        }
        
        return true;
    },

    validateAnalysisInputs(teamId, week, currentTeam) {
        if (!teamId) {
            showToast("Please enter a team ID", "error");
            return false;
        }
        
        if (!week || week < 1 || week > 18) {
            showToast("Please enter a valid week number (1-18)", "error");
            return false;
        }
        
        if (!currentTeam || !currentTeam.players || currentTeam.players.length === 0) {
            showToast("Please load a team first", "warning");
            return false;
        }
        
        return true;
    },

    buildQueryParams(teamId, week) {
        let queryParams = `team_id=${encodeURIComponent(teamId)}`;
        if (week) {
            queryParams += `&week=${encodeURIComponent(week)}`;
        }
        return queryParams;
    },

    async fetchTeamData(queryParams) {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.TEAMS_ENDPOINT}?${queryParams}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Team not found');
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.json();
    },

    async fetchAnalysisData(teamId, week) {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.COACH_ENDPOINT}?team_id=${encodeURIComponent(teamId)}&week=${week}`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.json();
    },

    async saveRoster(teamId, currentTeam) {
        const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.TEAMS_ENDPOINT}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
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
        
        return response.json();
    }
};