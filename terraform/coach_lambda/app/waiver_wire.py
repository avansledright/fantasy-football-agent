# app/waiver_wire.py
"""
Smart waiver wire analysis using unified fantasy-football-players-updated table.
UPDATED for seasons.{year}.* structure
"""

import os
from typing import Dict, Any, List, Optional, Set
import boto3
from boto3.dynamodb.conditions import Attr, Key
from strands import tool
from app.utils import normalize_position, get_injury_multiplier
from app.player_data import get_players_batch, extract_2025_projections, extract_2024_history, extract_2025_weekly_projections, extract_injury_and_ownership
from app.roster_construction import analyze_roster_needs_for_waivers, should_target_position_for_waiver

DDB = boto3.resource("dynamodb")
PLAYERS_TABLE = os.environ.get("PLAYERS_TABLE", "fantasy-football-players-updated")
ROSTER_TABLE = os.environ.get("DDB_TABLE_ROSTER", "fantasy-football-team-roster")

# Cache for rostered players - reset per analysis session
_rostered_players_cache = None

def get_all_rostered_players(use_cache: bool = True) -> Set[str]:
    """Get all player names that are currently rostered across all teams."""
    global _rostered_players_cache
    
    if use_cache and _rostered_players_cache is not None:
        return _rostered_players_cache
    
    table = DDB.Table(ROSTER_TABLE)
    rostered_player_names = set()
    
    try:
        print("Loading rostered players from database...")
        resp = table.scan(ProjectionExpression="players")
        
        for team in resp.get("Items", []):
            players = team.get("players", [])
            for player in players:
                player_name = player.get("name")
                if player_name:
                    rostered_player_names.add(player_name.lower())
        
        while "LastEvaluatedKey" in resp:
            resp = table.scan(
                ExclusiveStartKey=resp["LastEvaluatedKey"],
                ProjectionExpression="players"
            )
            for team in resp.get("Items", []):
                players = team.get("players", [])
                for player in players:
                    player_name = player.get("name")
                    if player_name:
                        rostered_player_names.add(player_name.lower())
        
        _rostered_players_cache = rostered_player_names
        print(f"Found {len(rostered_player_names)} rostered players across all teams")
        return rostered_player_names
        
    except Exception as e:
        print(f"Error getting rostered players: {str(e)}")
        return set()

def _extract_weekly_projection_from_unified(
    weekly_projections: Dict[str, Any], 
    week: int
) -> float:
    """Extract projection for specific week from unified table's weekly_projections.
    
    NEW: seasons.2025.weekly_projections.{week} stores direct numbers or objects
    """
    if not weekly_projections or not isinstance(weekly_projections, dict):
        return 0.0
    
    week_str = str(week)
    if week_str in weekly_projections:
        try:
            proj_value = weekly_projections[week_str]
            # Handle both direct number and object with fantasy_points
            if isinstance(proj_value, dict):
                return float(proj_value.get("fantasy_points", 0))
            else:
                return float(proj_value)
        except (ValueError, TypeError):
            return 0.0
    
    # Fallback: find closest week
    available_weeks = []
    for w in weekly_projections.keys():
        try:
            available_weeks.append(int(w))
        except (ValueError, TypeError):
            continue
    
    if available_weeks:
        closest_week = min(available_weeks, key=lambda x: abs(x - week))
        try:
            proj_value = weekly_projections[str(closest_week)]
            if isinstance(proj_value, dict):
                return float(proj_value.get("fantasy_points", 0))
            else:
                return float(proj_value)
        except (ValueError, TypeError):
            return 0.0
    
    return 0.0

def _normalize_injury_status(injury_status: str) -> str:
    """Normalize injury status to standard format."""
    if not injury_status:
        return "Unknown"
    
    status = injury_status.upper().strip()
    if status in ("ACTIVE", "HEALTHY"):
        return "Healthy"
    elif status in ("QUESTIONABLE", "Q"):
        return "Questionable"
    elif status in ("DOUBTFUL", "D"):
        return "Doubtful"
    elif status in ("OUT", "O", "INACTIVE"):
        return "Out"
    elif status in ("IR", "INJURED_RESERVE"):
        return "IR"
    else:
        return status

def get_available_waiver_players(
    position: str, 
    week: int,
    min_projected_points: float = 3.0,
    limit: int = 10,
    rostered_players: Optional[Set[str]] = None
) -> List[Dict[str, Any]]:
    """Get available waiver players from unified table with NEW structure."""
    table = DDB.Table(PLAYERS_TABLE)
    
    if rostered_players is None:
        rostered_players = get_all_rostered_players(use_cache=True)
    
    try:
        # Query unified table using position-index GSI for efficient lookups
        query_kwargs = {
            "IndexName": "position-index",
            "KeyConditionExpression": Key("position").eq(normalize_position(position)),
            "ProjectionExpression": "player_id, player_name, #pos, seasons",
            "ExpressionAttributeNames": {"#pos": "position"}
        }

        available_players = []
        resp = table.query(**query_kwargs)
        
        for item in resp.get("Items", []):
            player_name = item.get("player_name", "")
            
            # Skip if rostered
            if player_name.lower() in rostered_players:
                continue
            
            # Extract NEW structure data: seasons.2025.*
            seasons = item.get("seasons", {})
            season_2025 = seasons.get("2025", {})
            
            # Get weekly projections
            weekly_projections = season_2025.get("weekly_projections", {})
            projected_points = _extract_weekly_projection_from_unified(weekly_projections, week)
            
            if projected_points < min_projected_points:
                continue
            
            # Get injury status
            injury_status = _normalize_injury_status(season_2025.get("injury_status", ""))
            if injury_status != "Healthy":
                continue
            
            # Get team and ownership
            team = season_2025.get("team", "")
            ownership_pct = float(season_2025.get("percent_owned", 0.0))
            
            available_players.append({
                "player_id": item.get("player_id", ""),
                "player_name": player_name,
                "position": item.get("position"),
                "team": team,
                "projected_points": projected_points,
                "ownership_pct": ownership_pct,
                "injury_status": injury_status
            })
        
        # Continue querying if needed
        while "LastEvaluatedKey" in resp and len(available_players) < limit * 2:
            resp = table.query(
                ExclusiveStartKey=resp["LastEvaluatedKey"],
                **query_kwargs
            )
            
            for item in resp.get("Items", []):
                player_name = item.get("player_name", "")
                
                if player_name.lower() in rostered_players:
                    continue
                
                seasons = item.get("seasons", {})
                season_2025 = seasons.get("2025", {})
                
                weekly_projections = season_2025.get("weekly_projections", {})
                projected_points = _extract_weekly_projection_from_unified(weekly_projections, week)
                
                if projected_points < min_projected_points:
                    continue
                
                injury_status = _normalize_injury_status(season_2025.get("injury_status", ""))
                if injury_status != "Healthy":
                    continue
                
                team = season_2025.get("team", "")
                ownership_pct = float(season_2025.get("percent_owned", 0.0))
                
                available_players.append({
                    "player_id": item.get("player_id", ""),
                    "player_name": player_name,
                    "position": item.get("position"),
                    "team": team,
                    "projected_points": projected_points,
                    "ownership_pct": ownership_pct,
                    "injury_status": injury_status
                })
        
        available_players.sort(key=lambda x: x["projected_points"], reverse=True)
        return available_players[:limit]
        
    except Exception as e:
        print(f"Error querying waiver players from unified table: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

@tool
def analyze_waiver_opportunities_with_projections(
    current_roster: List[Dict[str, Any]], 
    external_projections: Dict[str, List[Dict[str, Any]]],
    week: int,
    projection_threshold: float = 8.0
) -> Dict[str, Any]:
    """Smart waiver analysis using unified table with roster construction awareness."""
    
    print(f"Analyzing smart waiver opportunities for week {week} (unified table)...")
    
    # STEP 1: Analyze roster construction needs
    roster_needs = analyze_roster_needs_for_waivers(current_roster)
    priority_positions = roster_needs["waiver_priorities"]
    avoid_positions = [p["position"] for p in roster_needs["positions_to_avoid"]]
    
    print(f"Roster priorities: {[p['position'] for p in priority_positions]}")
    print(f"Avoid positions: {avoid_positions}")
    
    # STEP 2: Get rostered players
    rostered_players = get_all_rostered_players(use_cache=True)
    
    # STEP 3: Find waiver candidates for priority positions only
    waiver_recommendations = []
    
    for position_need in priority_positions:
        position = position_need["position"]
        priority_level = position_need["priority"]
        
        # Skip positions we should avoid
        if position in avoid_positions:
            continue
        
        # Get position-appropriate minimum
        min_points = _get_position_min_points(position, priority_level)
        
        print(f"Searching {position} waivers (priority: {priority_level}, min: {min_points} pts)...")
        
        # Get available players from unified table
        available = get_available_waiver_players(
            position=position,
            week=week,
            min_projected_points=min_points,
            limit=15,
            rostered_players=rostered_players
        )
        
        if not available:
            print(f"No available {position} players found")
            continue
        
        # Enhance with historical data
        enhanced_candidates = []
        for waiver_player in available[:5]:  # Top 5 per position
            try:
                # Get enhanced data from unified table
                from app.player_data import get_player_by_name
                enhanced_data = get_player_by_name(waiver_player["player_name"]) or {}
                
                season_proj = 0
                historical_avg = 0
                
                if enhanced_data:
                    projections_2025 = extract_2025_projections(enhanced_data)
                    history_2024 = extract_2024_history(enhanced_data)
                    season_proj = float(projections_2025.get("MISC_FPTS", 0))
                    historical_avg = float(history_2024.get("recent4_avg", 0))
                
                # Calculate roster-based value
                roster_value = _calculate_roster_value(
                    waiver_player, 
                    position_need, 
                    season_proj, 
                    historical_avg
                )
                
                # Calculate recommendation strength
                rec_strength = _calculate_smart_recommendation_strength(
                    waiver_player,
                    position_need,
                    historical_avg
                )
                
                enhanced_candidates.append({
                    "player_name": waiver_player["player_name"],
                    "team": waiver_player["team"],
                    "projected_points": waiver_player["projected_points"],
                    "ownership_pct": waiver_player["ownership_pct"],
                    "season_projection": season_proj,
                    "2024_avg": historical_avg,
                    "roster_value": roster_value,
                    "recommendation": rec_strength
                })
            except Exception as e:
                print(f"Error enhancing {waiver_player['player_name']}: {e}")
                continue
        
        # Add to recommendations if we have candidates
        if enhanced_candidates:
            enhanced_candidates.sort(key=lambda x: x["roster_value"], reverse=True)
            
            waiver_recommendations.append({
                "position": position,
                "priority": priority_level,
                "reason": position_need["reason"],
                "top_recommendation": enhanced_candidates[0],
                "alternatives": enhanced_candidates[1:3],
                "urgency": priority_level
            })
    
    # STEP 4: Generate smart summary
    smart_analysis = _generate_smart_analysis(waiver_recommendations, avoid_positions, roster_needs)
    
    return {
        "roster_construction": roster_needs["roster_breakdown"],
        "waiver_recommendations": waiver_recommendations,
        "positions_to_avoid": avoid_positions,
        "total_recommendations": len(waiver_recommendations),
        "analysis": smart_analysis
    }

@tool  
def get_position_waiver_targets(
    position: str,
    week: int,
    min_points: float = None,
    max_ownership: float = 50.0
) -> Dict[str, Any]:
    """Get waiver targets from unified table with roster construction awareness."""
    
    # Set position-appropriate minimums if not specified
    if min_points is None:
        min_points = _get_position_min_points(position, "MEDIUM")
    
    print(f"Finding {position} waiver targets for week {week} from unified table...")
    
    rostered_players = get_all_rostered_players(use_cache=True)
    
    available_players = get_available_waiver_players(
        position=position,
        week=week,
        min_projected_points=min_points,
        limit=15,
        rostered_players=rostered_players
    )
    
    low_owned_targets = []
    
    for player in available_players:
        if player["ownership_pct"] <= max_ownership:
            # Get enhanced data from unified table
            enhanced_data = {}
            try:
                from app.player_data import get_player_by_name
                enhanced_data = get_player_by_name(player["player_name"]) or {}
            except Exception as e:
                print(f"Could not get enhanced data for {player['player_name']}: {e}")
            
            projections_2025 = extract_2025_projections(enhanced_data) if enhanced_data else {}
            history_2024 = extract_2024_history(enhanced_data) if enhanced_data else {}
            
            upside_score = _calculate_upside_score(
                player["projected_points"],
                player["ownership_pct"], 
                projections_2025.get("MISC_FPTS", 0),
                history_2024.get("recent4_avg", 0)
            )
            
            low_owned_targets.append({
                "player_name": player["player_name"],
                "team": player["team"],
                "projected_points": player["projected_points"],
                "ownership_pct": player["ownership_pct"],
                "season_projection": projections_2025.get("MISC_FPTS", 0),
                "2024_avg": history_2024.get("recent4_avg", 0),
                "upside_score": upside_score,
                "target_type": _classify_target_type(player["ownership_pct"], upside_score)
            })
    
    low_owned_targets.sort(key=lambda x: x["upside_score"], reverse=True)
    
    return {
        "position": position,
        "week": week,
        "targets_found": len(low_owned_targets),
        "waiver_targets": low_owned_targets[:10],
        "top_sleeper": low_owned_targets[0] if low_owned_targets else None,
        "analysis": f"Found {len(low_owned_targets)} {position} targets under {max_ownership}% ownership for week {week} from unified table"
    }

def _get_position_min_points(position: str, priority: str) -> float:
    """Get position-appropriate minimum points based on priority."""
    
    base_minimums = {
        "QB": 12.0,
        "RB": 8.0, 
        "WR": 8.0,
        "TE": 8.0,
        "K": 4.0,
        "DST": 5.0
    }
    
    # Adjust based on priority
    priority_multipliers = {
        "CRITICAL": 0.6,  # Lower standards when desperate
        "HIGH": 0.8,
        "MEDIUM": 1.0,
        "LOW": 1.2
    }
    
    base = base_minimums.get(position.upper(), 6.0)
    multiplier = priority_multipliers.get(priority, 1.0)
    
    return round(base * multiplier, 1)

def _calculate_roster_value(
    waiver_player: Dict[str, Any], 
    position_need: Dict[str, Any], 
    season_proj: float, 
    historical: float
) -> float:
    """Calculate value based on roster construction need."""
    
    base_value = waiver_player["projected_points"]
    
    # Priority multiplier
    priority_bonus = {
        "CRITICAL": 2.0,
        "HIGH": 1.5,
        "MEDIUM": 1.0,
        "LOW": 0.7
    }
    
    priority = position_need.get("priority", "LOW")
    multiplier = priority_bonus.get(priority, 1.0)
    
    # Health depth bonus
    healthy_count = position_need.get("healthy_count", 3)
    if healthy_count <= 1:
        multiplier *= 1.5  # Desperate need bonus
    
    return round(base_value * multiplier, 1)

def _calculate_smart_recommendation_strength(
    waiver_player: Dict[str, Any], 
    position_need: Dict[str, Any], 
    historical_avg: float
) -> str:
    """Calculate recommendation strength based on roster need."""
    
    priority = position_need.get("priority", "LOW")
    projected = waiver_player["projected_points"]
    ownership = waiver_player["ownership_pct"]
    
    if priority == "CRITICAL" and projected >= 5:
        return "Must Add"
    elif priority == "HIGH" and projected >= 6:
        return "Strongly Recommended"
    elif priority in ["HIGH", "MEDIUM"] and projected >= 8 and ownership < 90:
        return "Recommended"
    elif projected >= 10:
        return "Good Value"
    else:
        return "Consider"

def _generate_smart_analysis(
    recommendations: List[Dict[str, Any]], 
    avoid_positions: List[str], 
    roster_needs: Dict[str, Any]
) -> str:
    """Generate intelligent waiver analysis summary."""
    
    if not recommendations:
        return "Roster analysis shows no critical needs. Focus on best player available or handcuffs."
    
    analysis_parts = []
    
    # Critical needs first
    critical_recs = [r for r in recommendations if r["priority"] == "CRITICAL"]
    if critical_recs:
        critical_positions = [r["position"] for r in critical_recs]
        analysis_parts.append(f"CRITICAL NEEDS: {', '.join(critical_positions)} - Immediate action required")
    
    # High priority positions
    high_recs = [r for r in recommendations if r["priority"] == "HIGH"]
    if high_recs:
        high_positions = [r["position"] for r in high_recs]
        analysis_parts.append(f"HIGH PRIORITY: {', '.join(high_positions)} - Strongly consider adding")
    
    # Positions to avoid
    if avoid_positions:
        analysis_parts.append(f"AVOID: {', '.join(avoid_positions)} - At roster maximums")
    
    # Top recommendation
    if recommendations:
        top_rec = recommendations[0]
        top_player = top_rec.get("top_recommendation", {})
        if top_player:
            analysis_parts.append(
                f"TOP TARGET: {top_player['player_name']} ({top_rec['position']}) - "
                f"{top_player['projected_points']} pts, {top_player['ownership_pct']:.1f}% owned"
            )
    
    return " | ".join(analysis_parts)

def _calculate_upside_score(projected: float, ownership: float, season_proj: float, historical: float) -> float:
    """Calculate upside score for waiver targets."""
    projection_score = projected * 0.4
    season_score = (season_proj / 17) * 0.2 if season_proj > 0 else 0
    historical_score = historical * 0.1 if historical > 0 else 0
    
    return round(projection_score + season_score + historical_score, 2)

def _classify_target_type(ownership: float, upside_score: float) -> str:
    """Classify the type of waiver target."""
    if ownership < 10 and upside_score > 15:
        return "Deep Sleeper"
    elif ownership < 25 and upside_score > 12:
        return "Sleeper"
    elif ownership < 50 and upside_score > 10:
        return "Solid Add"
    else:
        return "Depth Option"