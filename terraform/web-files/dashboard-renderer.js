// ================================
// DASHBOARD-RENDERER.JS - Dashboard Analysis Display
// ================================

const DashboardRenderer = {
    render(analysisData) {
        if (!analysisData) {
            elements.analysisResult.innerHTML = "<p>No analysis data available</p>";
            return;
        }

        const explanationText = analysisData.explanations || "";
        const parsedData = AnalysisParser.parse(explanationText);
        const stats = this.calculateSummaryStats(analysisData, parsedData);

        elements.analysisResult.innerHTML = `
            <div class="analysis-dashboard">
                ${this.renderHeader()}
                ${this.renderSummaryStats(stats)}
                ${this.renderSections(analysisData, parsedData, explanationText)}
            </div>
        `;

        this.addEventListeners();
    },

    renderHeader() {
        return `
            <div class="dashboard-header">
                <h1>Week ${elements.weekNumber.value} Lineup Optimization Dashboard</h1>
            </div>
        `;
    },

    renderSummaryStats(stats) {
        return `
            <div class="summary-stats">
                ${Object.entries(stats).map(([label, value]) => 
                    `<div class="stat-card">
                        <span class="stat-number">${value}</span>
                        <span class="stat-label">${label}</span>
                    </div>`
                ).join('')}
            </div>
        `;
    },

    renderSections(analysisData, parsedData, explanationText) {
        const sections = [
            SectionRenderers.startingLineup(analysisData.lineup, parsedData.startingLineup),
            SectionRenderers.bench(analysisData.bench),
            SectionRenderers.waiverWire(parsedData.waiverTargets, parsedData.priorityMessage, explanationText),
            SectionRenderers.matchups(parsedData.matchups, explanationText),
            SectionRenderers.explanation(explanationText),
            SectionRenderers.actionItems(parsedData.priorityActions, explanationText)
        ].filter(section => section); // Remove empty sections

        return sections.join('');
    },

    calculateSummaryStats(analysisData, parsedData) {
        return {
            "Lineup Players": analysisData.lineup ? analysisData.lineup.length : 0,
            "Bench Players": analysisData.bench ? analysisData.bench.length : 0,
            "Waiver Targets": parsedData.waiverTargets.length,
            "Action Items": parsedData.priorityActions.length
        };
    },

    addEventListeners() {
        // Event listeners for interactive elements
    }
};

// ================================
// ANALYSIS PARSER
// ================================

const AnalysisParser = {
    parse(explanationText) {
        const data = {
            startingLineup: [],
            waiverTargets: [],
            matchups: [],
            priorityActions: [],
            priorityMessage: ""
        };

        if (!explanationText) return data;

        this.parseStartingLineup(explanationText, data);
        this.parseWaiverTargets(explanationText, data);
        this.parseMatchups(explanationText, data);
        this.parsePriorityActions(explanationText, data);

        return data;
    },

    parseStartingLineup(text, data) {
        const section = text.match(/\*\*Starting Lineup Strategy:\*\*([\s\S]*?)(?=\*\*CRITICAL WAIVER|$)/);
        if (!section) return;

        const playerMatches = section[1].match(/- \*\*([^*]+):\*\*([^-]+)/g);
        if (playerMatches) {
            playerMatches.forEach(match => {
                const playerMatch = match.match(/- \*\*([^*]+):\*\*([^-]+)/);
                if (playerMatch) {
                    const playerInfo = playerMatch[1].trim();
                    const description = playerMatch[2].trim();
                    const posMatch = playerInfo.match(/\(([^)]+)\)/);
                    
                    data.startingLineup.push({
                        player: playerInfo.replace(/\([^)]+\)/, '').trim(),
                        position: posMatch ? posMatch[1] : "",
                        description: description
                    });
                }
            });
        }
    },

    parseWaiverTargets(text, data) {
        const section = text.match(/\*\*CRITICAL WAIVER WIRE TARGETS:\*\*([\s\S]*?)(?=\*\*INJURY CONCERNS|$)/);
        if (!section) return;

        const waiverText = section[1];
        
        if (waiverText.includes("George Kittle")) {
            data.priorityMessage = "IMMEDIATE TE NEED - George Kittle on IR";
        }

        const playerMatches = waiverText.match(/\d+\.\s\*\*([^*]+)\*\*([^:]*?):\s*([^1-9]+)/g);
        if (playerMatches) {
            playerMatches.forEach(match => {
                const detailMatch = match.match(/\d+\.\s\*\*([^*]+)\*\*([^:]*?):\s*([^1-9]+)/);
                if (detailMatch) {
                    const fullName = (detailMatch[1] + detailMatch[2]).trim();
                    const description = detailMatch[3].trim();
                    const projMatch = description.match(/(\d+\.?\d*)\s*projected/);
                    const ownedMatch = description.match(/(\d+\.?\d*)%?\s*owned/);
                    
                    data.waiverTargets.push({
                        name: fullName,
                        projected: projMatch ? projMatch[1] : "N/A",
                        owned: ownedMatch ? ownedMatch[1] : "N/A",
                        description: description.replace(/\d+\.?\d*\s*projected[^.]*\d+\.?\d*%?\s*owned[^.]*\.?/, '').trim()
                    });
                }
            });
        }
    },

    parseMatchups(text, data) {
        const section = text.match(/\*\*MATCHUP ANALYSIS:\*\*([\s\S]*?)(?=\*\*WAIVER PRIORITY|$)/);
        if (!section) return;

        const matchupText = section[1];
        
        const favorableMatch = matchupText.match(/\*\*Favorable:\*\*([^*]+)/);
        if (favorableMatch) {
            data.matchups.push({
                title: "Favorable Matchups",
                content: favorableMatch[1].trim()
            });
        }

        const concerningMatch = matchupText.match(/\*\*Concerning:\*\*([^*]+)/);
        if (concerningMatch) {
            data.matchups.push({
                title: "Concerning Matchups",
                content: concerningMatch[1].trim()
            });
        }
    },

    parsePriorityActions(text, data) {
        const section = text.match(/\*\*WAIVER PRIORITY:\*\*([\s\S]*?)$/);
        if (!section) return;

        const priorityMatches = section[1].match(/\d+\.\s([^0-9\n]+)/g);
        if (priorityMatches) {
            priorityMatches.forEach(action => {
                const cleanAction = action.replace(/^\d+\.\s/, '').trim();
                if (cleanAction.length > 5) {
                    data.priorityActions.push(cleanAction);
                }
            });
        }
    }
};

// ================================
// SECTION RENDERERS
// ================================

const SectionRenderers = {
    createSection(title, icon, content, expanded = false) {
        return `
            <div class="dashboard-section ${expanded ? 'expanded' : ''}">
                <div class="section-header" onclick="toggleDashboardSection(this)">
                    <div class="section-title">
                        <div class="section-icon">${icon}</div>
                        ${title}
                    </div>
                    <div class="expand-icon">▼</div>
                </div>
                <div class="section-content">
                    ${content}
                </div>
            </div>
        `;
    },

    startingLineup(lineup, startingLineupData) {
        if ((!lineup || lineup.length === 0) && (!startingLineupData || startingLineupData.length === 0)) {
            return "";
        }

        let playersHTML = "";
        
        if (lineup && lineup.length > 0) {
            playersHTML = lineup.map(player => `
                <div class="player-row">
                    <div class="position-chip">${Utils.sanitizeHTML(player.slot || player.position)}</div>
                    <div class="player-info">
                        <h4>${Utils.sanitizeHTML(player.player)}</h4>
                        <p class="player-details">${Utils.sanitizeHTML(player.team)} • ${Utils.sanitizeHTML(player.position)} • Proj: ${Utils.formatPoints(player.projected)} pts</p>
                    </div>
                    <div class="projection">${Utils.formatPoints(player.adjusted)} pts</div>
                </div>
            `).join("");
        } else if (startingLineupData && startingLineupData.length > 0) {
            playersHTML = startingLineupData.map(player => `
                <div class="player-row">
                    <div class="position-chip">${player.position}</div>
                    <div class="player-info">
                        <h4>${Utils.sanitizeHTML(player.player)}</h4>
                        <p class="player-details">${Utils.sanitizeHTML(player.description)}</p>
                    </div>
                    <div class="projection">Recommended</div>
                </div>
            `).join("");
        }

        return this.createSection(
            "Optimal Starting Lineup",
            "★",
            `<div class="player-roster">${playersHTML}</div>`,
            true
        );
    },

    bench(bench) {
        if (!bench || bench.length === 0) return "";

        const benchHTML = bench.map(player => `
            <div class="player-row">
                <div class="position-chip bench-chip">${Utils.sanitizeHTML(player.position)}</div>
                <div class="player-info">
                    <h4>${Utils.sanitizeHTML(player.player)}</h4>
                    <p class="player-details">${Utils.sanitizeHTML(player.team)} • Proj: ${Utils.formatPoints(player.projected)} pts</p>
                </div>
                <div class="projection">${Utils.formatPoints(player.adjusted)} pts</div>
            </div>
        `).join("");

        return this.createSection(
            "Bench Players",
            "👥",
            `<div class="player-roster">${benchHTML}</div>`
        );
    },

    waiverWire(waiverTargets, priorityMessage, explanationText) {
        if (waiverTargets.length === 0 && explanationText) {
            const waiverMatch = explanationText.match(/\*\*CRITICAL WAIVER WIRE TARGETS:\*\*([\s\S]*?)(?=\*\*INJURY CONCERNS|$)/);
            if (waiverMatch) {
                return this.createSection(
                    "Critical Waiver Wire Targets",
                    "!",
                    `<div class="raw-explanation">${Utils.formatTextAsHTML(waiverMatch[1])}</div>`,
                    true
                );
            }
            return "";
        }

        if (waiverTargets.length === 0) return "";

        // Group by position and render
        const groupedTargets = this.groupWaiverTargets(waiverTargets);
        const content = `
            ${priorityMessage ? `<div class="priority-banner">${priorityMessage}</div>` : ''}
            ${Object.entries(groupedTargets).map(([position, targets]) => `
                <div class="waiver-category">
                    <h4>Top ${position} Waiver Pickups</h4>
                    <div class="waiver-grid">
                        ${targets.map((player, index) => `
                            <div class="waiver-card ${index === 0 ? 'waiver-priority' : ''}">
                                <div class="waiver-player-name">${Utils.sanitizeHTML(player.name)}</div>
                                <div class="waiver-stats">${player.projected} proj • ${player.owned}% owned</div>
                                <div class="waiver-description">${Utils.sanitizeHTML(player.description)}</div>
                            </div>
                        `).join("")}
                    </div>
                </div>
            `).join("")}
        `;

        return this.createSection(
            "Critical Waiver Wire Targets",
            "!",
            content,
            true
        );
    },

    matchups(matchups, explanationText) {
        if (matchups.length === 0 && explanationText) {
            const matchupMatch = explanationText.match(/\*\*MATCHUP ANALYSIS:\*\*([\s\S]*?)(?=\*\*WAIVER PRIORITY|$)/);
            if (matchupMatch) {
                return this.createSection(
                    "Matchup Analysis",
                    "📊",
                    `<div class="raw-explanation">${Utils.formatTextAsHTML(matchupMatch[1])}</div>`
                );
            }
            return "";
        }

        if (matchups.length === 0) return "";

        const matchupHTML = matchups.map(matchup => `
            <div class="insight-card">
                <div class="insight-title">${Utils.sanitizeHTML(matchup.title)}</div>
                <div class="insight-content">${Utils.sanitizeHTML(matchup.content)}</div>
            </div>
        `).join("");

        return this.createSection(
            "Key Matchup Insights",
            "📊",
            `<div class="matchup-insights">${matchupHTML}</div>`
        );
    },

    explanation(explanationText) {
        if (!explanationText) return "";

        return this.createSection(
            "Full Analysis Explanation",
            "💡",
            `<div class="raw-explanation">${Utils.formatTextAsHTML(explanationText)}</div>`
        );
    },

    actionItems(actions, explanationText) {
        if (actions.length === 0 && explanationText) {
            const finalMatch = explanationText.match(/\*\*WAIVER PRIORITY:\*\*([\s\S]*?)$/);
            if (finalMatch) {
                return this.createSection(
                    "Waiver Priority Actions",
                    "✓",
                    `<div class="raw-explanation">${Utils.formatTextAsHTML(finalMatch[1])}</div>`,
                    true
                );
            }
            return "";
        }

        if (actions.length === 0) return "";

        const actionsHTML = actions.map(action => `
            <div class="checklist-item">
                <div class="checkbox" onclick="toggleDashboardCheck(this)"></div>
                <div>${Utils.sanitizeHTML(action)}</div>
            </div>
        `).join("");

        return this.createSection(
            `Week ${elements.weekNumber.value} Action Checklist`,
            "✓",
            `<div class="action-checklist">${actionsHTML}</div>`,
            true
        );
    },

    groupWaiverTargets(targets) {
        const groups = {};
        targets.forEach(target => {
            let position = "Other";
            if (target.name.includes("RB") || target.description.toLowerCase().includes("rb")) {
                position = "RB";
            } else if (target.name.includes("WR") || target.description.toLowerCase().includes("wr")) {
                position = "WR";
            } else if (target.name.includes("TE") || target.description.toLowerCase().includes("te")) {
                position = "TE";
            }
            
            if (!groups[position]) groups[position] = [];
            groups[position].push(target);
        });
        return groups;
    }
};

// Dashboard interaction functions - these need to be global for onclick handlers
function toggleDashboardSection(header) {
    const section = header.parentElement;
    section.classList.toggle('expanded');
}

function toggleDashboardCheck(checkbox) {
    checkbox.classList.toggle('checked');
}