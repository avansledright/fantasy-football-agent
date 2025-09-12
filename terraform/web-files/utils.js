// ================================
// UTILS.JS - Utility Functions
// ================================

// ================================
// NFL WEEK CALCULATOR
// ================================

const NFLWeekCalculator = {
    // NFL 2025 season dates (update these each year)
    SEASON_CONFIG: {
        // Week 1 starts on September 5, 2025 (first Thursday)
        week1Start: new Date('2025-09-05'),
        // Regular season is 18 weeks
        regularSeasonWeeks: 18,
        // Playoff weeks (wild card, divisional, conference, super bowl)
        playoffWeeks: 4
    },

    getCurrentNFLWeek() {
        const now = new Date();
        const { week1Start, regularSeasonWeeks } = this.SEASON_CONFIG;
        
        // If before season starts
        if (now < week1Start) {
            return 1;
        }
        
        // For fantasy purposes, shift the week calculation by moving the 
        // effective start date back by 2 days (Tuesday instead of Thursday)
        // This makes Week 2 start on Tuesday Sep 10 instead of Thursday Sep 12
        const adjustedWeekStart = new Date(week1Start);
        adjustedWeekStart.setDate(adjustedWeekStart.getDate() - 2);
        
        const daysSinceAdjustedStart = Math.floor((now - adjustedWeekStart) / (1000 * 60 * 60 * 24));
        const currentWeek = Math.floor(daysSinceAdjustedStart / 7) + 1;
        
        // Cap at regular season weeks
        if (currentWeek > regularSeasonWeeks) {
            return regularSeasonWeeks;
        }
        
        return Math.max(1, currentWeek);
    },

    // Helper method to check if we're in season
    isInSeason() {
        const now = new Date();
        const { week1Start, regularSeasonWeeks } = this.SEASON_CONFIG;
        const seasonEnd = new Date(week1Start);
        seasonEnd.setDate(seasonEnd.getDate() + (regularSeasonWeeks * 7));
        
        return now >= week1Start && now <= seasonEnd;
    },

    // Method to get season status
    getSeasonStatus() {
        const now = new Date();
        const { week1Start, regularSeasonWeeks } = this.SEASON_CONFIG;
        const seasonEnd = new Date(week1Start);
        seasonEnd.setDate(seasonEnd.getDate() + (regularSeasonWeeks * 7));
        
        if (now < week1Start) {
            return 'preseason';
        } else if (now <= seasonEnd) {
            return 'regular';
        } else {
            return 'postseason';
        }
    }
};

// ================================
// UTILS OBJECT
// ================================

const Utils = {
    formatPoints(points) {
        if (points === undefined || points === null) return "0.0";
        return parseFloat(points).toFixed(1);
    },

    sanitizeHTML(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    getSlotDescription(position) {
        switch (position) {
            case "FLEX": return "RB/WR/TE";
            case "OP": return "QB/RB/WR/TE";
            default: return position;
        }
    },

    generatePlayerId(name, position) {
        return name.toLowerCase().replace(/\s+/g, "_") + "_" + position.toLowerCase();
    },

    formatTextAsHTML(text) {
        if (!text) return "";
        
        return text
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');
    },

    getCurrentNFLWeek() {
        return NFLWeekCalculator.getCurrentNFLWeek();
    },

    isNFLInSeason() {
        return NFLWeekCalculator.isInSeason();
    },

    getNFLSeasonStatus() {
        return NFLWeekCalculator.getSeasonStatus();
    }
};