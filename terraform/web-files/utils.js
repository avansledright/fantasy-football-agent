// ================================
// UTILS.JS - Utility Functions
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
    }
};