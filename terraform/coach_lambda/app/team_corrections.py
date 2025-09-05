# app/team_corrections.py
# Current team affiliations for 2025 NFL season

# Major player moves/corrections for 2025
TEAM_CORRECTIONS = {
    # Player name -> correct team abbreviation
    "DK Metcalf": "PIT",  # Traded to Pittsburgh
    "Sam Darnold": "SEA", # Signed with Seattle
    "Saquon Barkley": "PHI", # Signed with Philadelphia 
    "Josh Jacobs": "GB",  # Signed with Green Bay
    "Cooper Kupp": "LAR", # Still with Rams
    "Calvin Ridley": "TEN", # Signed with Titans
    "Mike Evans": "TB",   # Re-signed with Tampa Bay
    "Chris Godwin": "TB", # Still with Tampa Bay
    "Stefon Diggs": "NE", # Signed with Patriots
    "Keenan Allen": "CHI", # Traded to Chicago
    "DJ Moore": "CHI",    # Still with Chicago
    "Terry McLaurin": "WAS", # Still with Washington
    # Add more as needed...
}

# Team abbreviation standardization
TEAM_ABBREVIATIONS = {
    "LA": "LAR",  # Standardize Rams
    "LV": "LVR",  # Las Vegas Raiders
    "NO": "NOR",  # New Orleans
    "NE": "NEP",  # New England
    "SF": "SFO",  # San Francisco
    "TB": "TAM",  # Tampa Bay
    "GB": "GBP",  # Green Bay
    # Add more standardizations as needed
}

def correct_player_team(player_name: str, current_team: str) -> str:
    """
    Correct a player's team affiliation for the current season.
    
    Args:
        player_name: Player's full name
        current_team: Team from projections/roster data
        
    Returns:
        Corrected team abbreviation
    """
    # Check for direct correction
    if player_name in TEAM_CORRECTIONS:
        return TEAM_CORRECTIONS[player_name]
    
    # Standardize team abbreviation
    if current_team in TEAM_ABBREVIATIONS:
        return TEAM_ABBREVIATIONS[current_team]
    
    # Return original if no correction needed
    return current_team

def validate_team_data(lineup_data: dict) -> dict:
    """
    Validate and correct team data in lineup response.
    
    Args:
        lineup_data: Lineup dictionary with player data
        
    Returns:
        Corrected lineup data with updated team affiliations
    """
    corrected_lineup = lineup_data.copy()
    
    corrections_made = []
    
    # Correct lineup players
    if "lineup" in corrected_lineup:
        for player in corrected_lineup["lineup"]:
            if "player" in player and player["player"]:
                original_team = player.get("team", "")
                corrected_team = correct_player_team(player["player"], original_team)
                
                if corrected_team != original_team:
                    player["team"] = corrected_team
                    corrections_made.append(f"{player['player']}: {original_team} → {corrected_team}")
    
    # Correct bench players
    if "bench" in corrected_lineup:
        for player in corrected_lineup["bench"]:
            if "name" in player and player["name"]:
                original_team = player.get("team", "")
                corrected_team = correct_player_team(player["name"], original_team)
                
                if corrected_team != original_team:
                    player["team"] = corrected_team
                    corrections_made.append(f"{player['name']}: {original_team} → {corrected_team}")
    
    # Add correction note to explanations
    if corrections_made and "explanations" in corrected_lineup:
        correction_note = f"\n\n🔄 Team corrections applied: {', '.join(corrections_made[:3])}"
        if len(corrections_made) > 3:
            correction_note += f" and {len(corrections_made) - 3} others"
        corrected_lineup["explanations"] += correction_note
    
    return corrected_lineup

# Quick reference for major 2025 moves
MAJOR_2025_MOVES = {
    "DK Metcalf": "Traded from SEA to PIT",
    "Sam Darnold": "Signed with SEA as free agent", 
    "Saquon Barkley": "Signed with PHI as free agent",
    "Josh Jacobs": "Signed with GB as free agent",
    "Stefon Diggs": "Traded from BUF to HOU",
    "Keenan Allen": "Traded from LAC to CHI",
    "Calvin Ridley": "Signed with TEN as free agent",
    "Amari Cooper": "retired. No longer playing"
}
