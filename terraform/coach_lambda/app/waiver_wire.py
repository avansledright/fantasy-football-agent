# app/waiver_wire.py
"""
Smart waiver wire analysis that considers roster construction and league requirements.
"""

import os
from typing import Dict, Any, List, Optional, Set
import boto3
from boto3.dynamodb.conditions import Attr
from strands import tool
from app.utils import normalize_position, get_injury_multiplier
from app.player_data import get_players_batch, extract_2025_projections, extract_2024_history
from app.roster_construction import analyze_roster_needs_for_waivers, should_target_position_for_waiver

DDB = boto3.resource("dynamodb")
WAIVER_TABLE = os.environ.get("WAIVER_TABLE", "waiver-players")
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

def _extract_weekly_projection(weekly_projections: Dict[str, Any], week: int) -> float:
    """Extract projection for specific week from weekly_projections object."""
    if not weekly_projections or not isinstance(weekly_projections, dict):
        return 0.0
    
    week_str = str(week)
    if week_str in weekly_projections:
        try:
            return float(weekly_projections[week_str])
        except (ValueError, TypeError):
            return 0.0
    
    available_weeks = []
    for w in weekly_projections.keys():
        try:
            available_weeks.append(int(w))
        except (ValueError, TypeError):
            continue
    
    if available_weeks:
        closest_week = min(available_weeks, key=lambda x: abs(x - week))
        try:
            return float(weekly_projections[str(closest_week)])
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
    min_projected_points: float = 3.0,  # Lowered default for TEs
    limit: int = 10,
    rostered_players: Optional[Set[str]] = None
) -> List[Dict[str, Any]]:
    """Get available waiver players for a specific position and week."""
    waiver_table = DDB.Table(WAIVER_TABLE)
    
    if rostered_players is None:
        rostered_players = get_all_rostered_players(use_cache=True)
    
    try:
        filter_expr = Attr("position").eq(normalize_position(position))
        
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ProjectionExpression": "player_season, player_name, #pos, team, injury_status, percent_owned, weekly_projections",
            "ExpressionAttributeNames": {"#pos": "position"}
        }
        
        available_players = []
        resp = waiver_table.scan(**scan_kwargs)
        
        for item in resp.get("Items", []):
            player_name = item.get("player_name", "")
            
            if player_name.lower() in rostered_players:
                continue
            
            weekly_projections = item.get("weekly_projections", {})
            projected_points = _extract_weekly_projection(weekly_projections, week)
            
            if projected_points < min_projected_points:
                continue
            
            injury_status = _normalize_injury_status(item.get("injury_status", ""))
            if injury_status != "Healthy":
                continue
            
            available_players.append({
                "player_id": item.get("player_season", ""),
                "player_name": player_name,
                "position": item.get("position"),
                "team": item.get("team"),
                "projected_points": projected_points,
                "ownership_pct": float(item.get("percent_owned", 0)),
                "injury_status": injury_status
            })
        
        while "LastEvaluatedKey" in resp and len(available_players) < limit * 2:
            resp = waiver_table.scan(
                ExclusiveStartKey=resp["LastEvaluatedKey"],
                **scan_kwargs
            )
            
            for item in resp.get("Items", []):
                player_name = item.get("player_name", "")
                
                if player_name.lower() in rostered_players:
                    continue
                
                weekly_projections = item.get("weekly_projections", {})
                projected_points = _extract_weekly_projection(weekly_projections, week)
                
                if projected_points < min_projected_points:
                    continue
                
                injury_status = _normalize_injury_status(item.get("injury_status", ""))
                if injury_status != "Healthy":
                    continue
                
                available_players.append({
                    "player_id": item.get("player_season", ""),
                    "player_name": player_name,
                    "position": item.get("position"),
                    "team": item.get("team"),
                    "projected_points": projected_points,
                    "ownership_pct": float(item.get("percent_owned", 0)),
                    "injury_status": injury_status
                })
        
        available_players.sort(key=lambda x: x["projected_points"], reverse=True)
        return available_players[:limit]
        
    except Exception as e:
        print(f"Error querying waiver players: {str(e)}")
        return []

@tool
def analyze_waiver_opportunities_with_projections(
    current_roster: List[Dict[str, Any]], 
    external_projections: Dict[str, List[Dict[str, Any]]],
    week: int,
    projection_threshold: float = 8.0
) -> Dict[str, Any]:
    """Smart waiver analysis that considers roster construction and league requirements."""
    
    print(f"Analyzing smart waiver opportunities for week {week}...")
    
    # STEP 1: Analyze roster construction needs
    roster_needs = analyze_roster_needs_for_waivers(current_roster)
    priority_positions = roster_needs["waiver_priorities"]
    avoid_positions = [p["position"] for p in roster_needs["positions_to_avoid"]]
    
    print(f"Roster analysis: {len(priority_positions)} positions need attention, avoiding {avoid_positions}")
    
    # STEP 2: Get rostered players once
    rostered_players = get_all_rostered_players(use_cache=True)
    
    # STEP 3: Focus waiver search on priority positions only
    waiver_recommendations = []
    
    for pos_info in priority_positions:
        position = pos_info["position"]
        priority_level = pos_info["priority"]
        
        print(f"Searching {position} waivers - {priority_level} priority: {pos_info['reason']}")
        
        # Adjust thresholds based on priority and position
        min_points = _get_position_min_points(position, priority_level)
        search_limit = 8 if priority_level == "CRITICAL" else 5
        
        available_players = get_available_waiver_players(
            position=position,
            week=week,
            min_projected_points=min_points,
            limit=search_limit,
            rostered_players=rostered_players
        )
        
        if available_players:
            # Get enhanced data for top options
            top_options = []
            
            for waiver_player in available_players[:3]:
                player_name = waiver_player["player_name"]
                
                enhanced_info = {}
                try:
                    from app.player_data import get_player_by_name
                    enhanced_info = get_player_by_name(player_name) or {}
                except Exception as e:
                    print(f"Could not get enhanced data for {player_name}: {e}")
                
                projections_2025 = extract_2025_projections(enhanced_info) if enhanced_info else {}
                history_2024 = extract_2024_history(enhanced_info) if enhanced_info else {}
                
                season_projection = projections_2025.get("MISC_FPTS", 0)
                historical_avg = history_2024.get("recent4_avg", 0)
                
                # Calculate value based on roster need
                roster_value = _calculate_roster_value(waiver_player, pos_info, season_projection, historical_avg)
                
                top_options.append({
                    "player_name": waiver_player["player_name"],
                    "team": waiver_player["team"],
                    "projected_points": waiver_player["projected_points"],
                    "ownership_pct": waiver_player["ownership_pct"],
                    "season_projection": season_projection,
                    "2024_avg": historical_avg,
                    "roster_value": roster_value,
                    "recommendation_strength": _calculate_smart_recommendation_strength(
                        waiver_player, pos_info, historical_avg
                    )
                })
            
            waiver_recommendations.append({
                "position": position,
                "priority": priority_level,
                "roster_need": pos_info["reason"],
                "healthy_count": pos_info["healthy_count"],
                "waiver_options": top_options,
                "top_recommendation": top_options[0] if top_options else None,
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
    min_points: float = None,  # Make dynamic based on position
    max_ownership: float = 50.0  # Increased from 25.0 for better selection
) -> Dict[str, Any]:
    """Get waiver targets with roster construction awareness."""
    
    # Set position-appropriate minimums if not specified
    if min_points is None:
        min_points = _get_position_min_points(position, "MEDIUM")
    
    print(f"Finding {position} waiver targets for week {week} with <{max_ownership}% ownership and >{min_points} projected points...")
    
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
        "analysis": f"Found {len(low_owned_targets)} {position} targets under {max_ownership}% ownership for week {week}"
    }

def _get_position_min_points(position: str, priority: str) -> float:
    """Get position-appropriate minimum points based on priority."""
    
    base_minimums = {
        "QB": 12.0,
        "RB": 8.0, 
        "WR": 8.0,
        "TE": 8.0,  # Lower for TEs
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