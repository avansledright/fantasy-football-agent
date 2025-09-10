// ================================
// ROSTER-MANAGER.JS - Roster Management
// ================================

const RosterManager = {
    toggleEditMode() {
        isEditing = !isEditing;
        elements.editRoster.innerHTML = isEditing ?
            '<i class="fas fa-times"></i> Cancel Edit' :
            '<i class="fas fa-edit"></i> Edit Roster';

        document.querySelectorAll(".player-card, .lineup-slot").forEach(card => {
            card.style.cursor = isEditing ? "pointer" : "default";
        });

        if (!isEditing) this.hideEditForm();
        showToast(isEditing ? "Edit mode enabled" : "Edit mode disabled", "info");
    },

    editPlayer(index) {
        if (!isEditing || !currentTeam?.players) return;

        const player = currentTeam.players[index];
        if (!player) return;

        elements.editPlayerIndex.value = index;
        elements.playerName.value = player.name;
        elements.playerPosition.value = player.position;
        elements.playerTeam.value = player.team;
        elements.playerStatus.value = player.status;

        this.updateSlotDropdown(player);
        elements.playerSlot.value = player.slot || "";
        this.showEditForm();
    },

    addNewPlayer(targetSlot = null) {
        if (!isEditing) {
            showToast("Enable edit mode first", "warning");
            return;
        }

        if (!currentTeam) {
            currentTeam = { team_id: elements.teamId.value, players: [] };
        }
        if (!currentTeam.players) currentTeam.players = [];

        elements.editPlayerIndex.value = -1;
        elements.playerName.value = "";
        elements.playerPosition.value = "QB";
        elements.playerTeam.value = "";
        elements.playerStatus.value = targetSlot ? "starter" : "bench";

        this.updateSlotDropdown({ position: "QB" });
        elements.playerSlot.value = targetSlot || "";
        this.showEditForm();
    },

    savePlayer() {
        const index = parseInt(elements.editPlayerIndex.value);
        const playerData = {
            name: elements.playerName.value.trim(),
            position: elements.playerPosition.value,
            team: elements.playerTeam.value.trim().toUpperCase(),
            status: elements.playerStatus.value,
            slot: elements.playerSlot.value === "bench" ? null : elements.playerSlot.value,
            player_id: Utils.generatePlayerId(elements.playerName.value, elements.playerPosition.value)
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

        if (!currentTeam.players) currentTeam.players = [];

        if (index === -1) {
            currentTeam.players.push(playerData);
            showToast("Player added successfully", "success");
        } else {
            currentTeam.players[index] = playerData;
            showToast("Player updated successfully", "success");
        }

        DisplayManager.showRoster(currentTeam.players);
        this.hideEditForm();
    },

    removePlayer() {
        const index = parseInt(elements.editPlayerIndex.value);
        if (index === -1) {
            this.hideEditForm();
            return;
        }

        if (confirm("Are you sure you want to remove this player?")) {
            currentTeam.players.splice(index, 1);
            DisplayManager.showRoster(currentTeam.players);
            this.hideEditForm();
            showToast("Player removed successfully", "success");
        }
    },

    cancelEdit() {
        this.hideEditForm();
    },

    showEditForm() {
        elements.editRosterForm.style.display = "block";
        elements.playerName.focus();
    },

    hideEditForm() {
        elements.editRosterForm.style.display = "none";
    },

    updateSlotDropdown(player) {
        const slotSelect = elements.playerSlot;
        slotSelect.innerHTML = '<option value="">Select Slot (optional)</option>';
        slotSelect.innerHTML += '<option value="bench">Bench</option>';

        LINEUP_SLOTS.forEach(slot => {
            if (this.isPlayerEligibleForSlot(player, slot)) {
                slotSelect.innerHTML += `<option value="${slot.slot}">${slot.slot} (${Utils.getSlotDescription(slot.position)})</option>`;
            }
        });
    },

    isPlayerEligibleForSlot(player, slot) {
        if (!player || !slot) return false;
        
        const playerPos = player.position;
        const slotPos = slot.position;
        
        if (playerPos === slotPos) return true;
        if (slotPos === "FLEX" && ["RB", "WR", "TE"].includes(playerPos)) return true;
        if (slotPos === "OP" && ["QB", "RB", "WR", "TE"].includes(playerPos)) return true;
        
        return false;
    }
};

// Global functions that need to be accessible from HTML onclick handlers
function editPlayer(index) { RosterManager.editPlayer(index); }
function addPlayerToSlot(slotName) { 
    if (!isEditing) {
        showToast("Enable edit mode first", "warning");
        return;
    }
    RosterManager.addNewPlayer(slotName); 
}