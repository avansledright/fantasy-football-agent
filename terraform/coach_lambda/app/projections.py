# app/projections.py
"""
Projections using unified player data table with NEW seasons.{year}.* structure.
"""

from typing import Dict, List, Any
from strands import tool
from app.player_data import load_roster_player_data, extract_2025_projections, extract_2024_history, extract_current_stats, extract_2025_weekly_projections
from app.schedule import matchups_by_week, nfl_games_and_times

def safe_float(value):
    """Safely convert Decimal or any numeric type to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0
    
def create_unified_projections(
    roster_players: List[Dict[str, Any]], 
    week: int
) -> Dict[str, List[Dict[str, Any]]]:
    """Create weekly projections using unified player data with NEW structure."""
    
    # Load comprehensive data for all roster players
    unified_data = load_roster_player_data(roster_players)
    
    # Group projections by position
    projections_by_position = {}
    
    for player in roster_players:
        player_name = player.get("name", "")
        position = player.get("position", "").upper()
        team = player.get("team", "")
        
        if not player_name or position not in ("QB", "RB", "WR", "TE", "K", "DST"):
            continue
        
        # Get player data from unified table
        player_data = unified_data.get(player_name, {})
        
        # Calculate weekly projection from multiple sources (NEW structure)
        weekly_projection = _calculate_weekly_projection(player_data, week)
        
        # Get opponent from matchups_by_week
        opponent = ""
        is_home = False
        if week in matchups_by_week:
            week_matchups = matchups_by_week[week]
            
            # Check if team is the away team (key in the dictionary)
            if team in week_matchups:
                opponent = week_matchups[team]
                is_home = False  # Away team
            else:
                # Check if team is the home team (value in the dictionary)
                for away_team, home_team in week_matchups.items():
                    if home_team == team:
                        opponent = away_team
                        is_home = True  # Home team
                        break
        
        if opponent == "":
            opponent = "BYE"
        
        print(f"Opponent is: {opponent} and {team} is home? {is_home}")
        
        # Create projection entry
        projection_entry = {
            "name": player_name,
            "team": team,
            "opp": opponent,
            "home": is_home,
            "position": position,
            "projected": weekly_projection
        }
        
        # Group by position
        if position not in projections_by_position:
            projections_by_position[position] = []
        projections_by_position[position].append(projection_entry)
        
        print(f"Unified projection for {player_name} ({position}): {weekly_projection} points")
    
    return projections_by_position

def _calculate_weekly_projection(player_data: Dict[str, Any], week: int) -> float:
    """Calculate weekly projection from unified player data using NEW structure."""
    
    if not player_data:
        print("No player data found - returning default 5.0")
        return 5.0
    
    player_name = player_data.get("player_name", "Unknown")
    print(f"DEBUG: Calculating projection for {player_name}")
    
    # Extract different data sources from NEW structure
    projections_2025 = extract_2025_projections(player_data)
    weekly_projections_2025 = extract_2025_weekly_projections(player_data)
    history_2024 = extract_2024_history(player_data)
    current_2025 = extract_current_stats(player_data)
    
    # Check if player has no 2025 projections
    if not projections_2025 and not weekly_projections_2025:
        print(f"WARNING: No 2025 projections found for {player_name} - returning 0.0")
        return 0.0
    
    # FIRST: Check for specific weekly projection from NEW structure
    # NEW: seasons.2025.weekly_projections.{week}
    if str(week) in weekly_projections_2025:
        weekly_proj_raw = weekly_projections_2025[str(week)]
        # Weekly projections are stored as direct numbers now
        if isinstance(weekly_proj_raw, dict):
            weekly_proj = safe_float(weekly_proj_raw.get("fantasy_points", 0))
        else:
            weekly_proj = safe_float(weekly_proj_raw)
        
        if weekly_proj > 0:
            print(f"  Found weekly projection for week {week}: {weekly_proj}")
            return round(weekly_proj, 1)
    
    # Base projection from season total - convert Decimal to float
    season_projection = safe_float(projections_2025.get("MISC_FPTS", 0))
    weekly_from_season = (season_projection / 17) if season_projection > 0 else 0
    print(f"  Season total: {season_projection}, weekly: {weekly_from_season}")
    
    # Recent performance from 2024 - convert Decimal to float
    historical_avg = safe_float(history_2024.get("recent4_avg", 0))
    print(f"  2024 recent avg: {historical_avg}")
    
    # Current 2025 performance - convert Decimal to float
    current_weeks = current_2025.get("weeks", [])
    current_avg = 0
    if current_weeks:
        current_avg = sum(safe_float(w.get("fantasy_points", 0)) for w in current_weeks) / len(current_weeks)
    print(f"  2025 current avg: {current_avg} from {len(current_weeks)} weeks")
    
    # Weighted calculation
    # 50% season projection, 30% 2024 history, 20% current 2025 performance
    weights = {
        "season": 0.5,
        "historical": 0.3,
        "current": 0.2
    }
    
    projection = (
        weights["season"] * weekly_from_season +
        weights["historical"] * historical_avg +
        weights["current"] * current_avg
    )
    
    print(f"  Raw projection: {projection}")
    
    # Apply position-based adjustments
    position = player_data.get("position", "")
    projection = _apply_position_adjustments(projection, position)
    
    print(f"  After position adjustment: {projection}")
    
    # Ensure minimum projection
    final_projection = max(round(projection, 1), 3.0)
    print(f"  Final projection: {final_projection}")
    
    return final_projection

def _apply_position_adjustments(projection: float, position: str) -> float:
    """Apply position-specific adjustments to projections."""
    
    position_multipliers = {
        "QB": 1.1,    # QBs typically score higher
        "RB": 1.0,    # Baseline
        "WR": 1.0,    # Baseline
        "TE": 0.9,    # TEs typically score lower
        "K": 0.7,     # Kickers much lower
        "DST": 0.8    # Defenses variable but generally lower
    }
    
    multiplier = position_multipliers.get(position.upper(), 1.0)
    return projection * multiplier