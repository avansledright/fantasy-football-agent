# app/projections.py
"""
Projections using unified player data table instead of external APIs.
"""

from typing import Dict, List, Any
from strands import tool
from app.player_data import load_roster_player_data, extract_2025_projections, extract_2024_history, extract_current_stats
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
    """Create weekly projections using unified player data."""
    
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
        # Calculate weekly projection from multiple sources
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
    """Calculate weekly projection from unified player data."""
    
    if not player_data:
        print("No player data found - returning default 5.0")
        return 5.0
    
    player_name = player_data.get("player_name", "Unknown")
    print(f"DEBUG: Calculating projection for {player_name}")
    
    # Extract different data sources
    projections_2025 = extract_2025_projections(player_data)
    history_2024 = extract_2024_history(player_data)
    current_2025 = extract_current_stats(player_data)
    
    # FIRST: Check for specific weekly projection
    weekly_projections = projections_2025.get("weekly", {})
    if str(week) in weekly_projections:
        weekly_proj_raw = weekly_projections[str(week)].get("fantasy_points", 0)
        weekly_proj = float(weekly_proj_raw)  # Convert Decimal to float
        if weekly_proj > 0:
            print(f"  Found weekly projection for week {week}: {weekly_proj}")
            return round(weekly_proj, 1)
    
    # Base projection from season total - convert Decimal to float
    season_projection = float(projections_2025.get("MISC_FPTS", 0))
    weekly_from_season = (season_projection / 17) if season_projection > 0 else 0
    print(f"  Season total: {season_projection}, weekly: {weekly_from_season}")
    
    # Recent performance from 2024 - convert Decimal to float
    historical_avg = float(history_2024.get("recent4_avg", 0))
    print(f"  2024 recent avg: {historical_avg}")
    
    # Current 2025 performance - convert Decimal to float
    current_weeks = current_2025.get("weeks", [])
    current_avg = 0
    if current_weeks:
        current_avg = sum(float(w.get("fantasy_points", 0)) for w in current_weeks) / len(current_weeks)
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

@tool
def get_roster_projections(week: int, roster_players: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Get projections for roster players using unified table data.
    
    Args:
        week: Week number (for compatibility, not used in unified approach)
        roster_players: List of roster players
    
    Returns:
        Dict with projections by position
    """
    print(f"Creating unified projections for week {week}...")
    
    projections_data = create_unified_projections(roster_players, week)
    
    # Log summary
    total_projections = sum(len(players) for players in projections_data.values())
    print(f"Created {total_projections} unified projections across {len(projections_data)} positions")
    
    for pos, players in projections_data.items():
        print(f"  {pos}: {len(players)} players")
    
    return projections_data

@tool
def get_weekly_projections(week: int) -> Dict[str, List[Dict[str, Any]]]:
    """Get all weekly projections (placeholder - requires roster context for unified approach)."""
    print("Warning: get_weekly_projections requires roster context when using unified data")
    return {}

def get_enhanced_projection_with_matchup(
    player_data: Dict[str, Any], 
    week: int, 
    opponent: str = None
) -> Dict[str, Any]:
    """Get enhanced projection with matchup analysis."""
    
    base_projection = _calculate_weekly_projection(player_data, week)
    
    # Enhanced analysis
    projections_2025 = extract_2025_projections(player_data)
    history_2024 = extract_2024_history(player_data)
    current_2025 = extract_current_stats(player_data)
    
    # Calculate consistency metrics
    if history_2024.get("all"):
        historical_games = history_2024["all"]
        historical_points = [g.get("fantasy_points", 0) for g in historical_games]
        consistency = _calculate_consistency(historical_points)
    else:
        consistency = 0.5  # Default neutral consistency
    
    # Calculate ceiling/floor
    ceiling = base_projection * 1.5  # 50% upside
    floor = base_projection * 0.3   # 70% downside risk
    
    return {
        "player_name": player_data.get("player_name", ""),
        "position": player_data.get("position", ""),
        "projected_points": base_projection,
        "ceiling": round(ceiling, 1),
        "floor": round(floor, 1),
        "consistency": round(consistency, 2),
        "season_total_pace": projections_2025.get("MISC_FPTS", 0),
        "2024_avg": history_2024.get("recent4_avg", 0),
        "2025_current_avg": current_2025.get("weeks", [])
    }

def _calculate_consistency(points_list: List[float]) -> float:
    """Calculate consistency score from historical points."""
    if len(points_list) < 2:
        return 0.5
    
    # Calculate coefficient of variation (lower = more consistent)
    avg = sum(points_list) / len(points_list)
    if avg == 0:
        return 0.0
    
    variance = sum((x - avg) ** 2 for x in points_list) / len(points_list)
    std_dev = variance ** 0.5
    cv = std_dev / avg
    
    # Convert to 0-1 scale where 1 = very consistent, 0 = very inconsistent
    # Typical CV for fantasy players ranges from 0.3 (consistent) to 1.5+ (boom/bust)
    consistency = max(0, min(1, 1 - (cv / 1.5)))
    return consistency