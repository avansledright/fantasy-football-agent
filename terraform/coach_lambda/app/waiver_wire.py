# app/waiver_wire.py
"""
Waiver wire analysis tool for finding available healthy players.
OPTIMIZED VERSION - Caches rostered players to avoid repeated DynamoDB scans.
"""

import os
from typing import Dict, Any, List, Optional, Set
import boto3
from boto3.dynamodb.conditions import Attr
from strands import tool
from app.utils import normalize_position, get_injury_multiplier
from app.player_data import get_players_batch, extract_2025_projections, extract_2024_history

DDB = boto3.resource("dynamodb")
WAIVER_TABLE = os.environ.get("WAIVER_TABLE", "waiver-players")
ROSTER_TABLE = os.environ.get("DDB_TABLE_ROSTER", "fantasy-football-team-roster")

# Cache for rostered players - reset per analysis session
_rostered_players_cache = None

def get_all_rostered_players(use_cache: bool = True) -> Set[str]:
    """Get all player names that are currently rostered across all teams.
    
    Args:
        use_cache: If True, use cached result if available
    """
    global _rostered_players_cache
    
    # Return cached result if available and caching is enabled
    if use_cache and _rostered_players_cache is not None:
        return _rostered_players_cache
    
    table = DDB.Table(ROSTER_TABLE)
    rostered_player_names = set()
    
    try:
        print("Loading rostered players from database...")
        # Scan all teams to get rostered players
        resp = table.scan(
            ProjectionExpression="players"
        )
        
        for team in resp.get("Items", []):
            players = team.get("players", [])
            for player in players:
                player_name = player.get("name")
                if player_name:
                    rostered_player_names.add(player_name.lower())
        
        # Handle pagination
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
        
        # Cache the result
        _rostered_players_cache = rostered_player_names
        print(f"Found {len(rostered_player_names)} rostered players across all teams")
        return rostered_player_names
        
    except Exception as e:
        print(f"Error getting rostered players: {str(e)}")
        return set()

def clear_rostered_players_cache():
    """Clear the rostered players cache. Call this if roster changes during analysis."""
    global _rostered_players_cache
    _rostered_players_cache = None

def _extract_weekly_projection(weekly_projections: Dict[str, Any], week: int) -> float:
    """Extract projection for specific week from weekly_projections object."""
    if not weekly_projections or not isinstance(weekly_projections, dict):
        return 0.0
    
    # Try exact week match first
    week_str = str(week)
    if week_str in weekly_projections:
        try:
            return float(weekly_projections[week_str])
        except (ValueError, TypeError):
            return 0.0
    
    # If no exact match, try to find closest week
    available_weeks = []
    for w in weekly_projections.keys():
        try:
            available_weeks.append(int(w))
        except (ValueError, TypeError):
            continue
    
    if available_weeks:
        # Find closest week
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
    min_projected_points: float = 5.0,
    limit: int = 10,
    rostered_players: Optional[Set[str]] = None  # Accept pre-fetched roster
) -> List[Dict[str, Any]]:
    """Get available waiver players for a specific position and week.
    
    Args:
        position: Position to search for
        week: Week number for projections
        min_projected_points: Minimum projection threshold
        limit: Maximum number of results
        rostered_players: Pre-fetched set of rostered player names (for efficiency)
    """
    waiver_table = DDB.Table(WAIVER_TABLE)
    
    # Use provided roster or fetch once
    if rostered_players is None:
        rostered_players = get_all_rostered_players(use_cache=True)
    
    try:
        # Query waiver table for position - use correct field names
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
            
            # Skip if already rostered
            if player_name.lower() in rostered_players:
                continue
            
            # Extract weekly projection for the specified week
            weekly_projections = item.get("weekly_projections", {})
            projected_points = _extract_weekly_projection(weekly_projections, week)
            
            # Skip if below minimum projection
            if projected_points < min_projected_points:
                continue
            
            # Normalize injury status
            injury_status = _normalize_injury_status(item.get("injury_status", ""))
            
            # Only include healthy players
            if injury_status != "Healthy":
                continue
            
            # Map to expected structure
            available_players.append({
                "player_id": item.get("player_season", ""),
                "player_name": player_name,
                "position": item.get("position"),
                "team": item.get("team"),
                "projected_points": projected_points,
                "ownership_pct": float(item.get("percent_owned", 0)),
                "injury_status": injury_status
            })
        
        # Handle pagination
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
        
        # Sort by projected points descending and limit results
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
    projection_threshold: float = 10.0
) -> Dict[str, Any]:
    """Analyze waiver wire opportunities using external projection data.
    
    Args:
        current_roster: List of current roster players
        external_projections: External projections data by position
        week: Current week number for projections
        projection_threshold: Minimum projection to avoid waiver search (default 10.0)
    
    Returns:
        Dict with waiver recommendations for positions with low projections
    """
    print(f"Analyzing waiver opportunities for week {week} for players projected under {projection_threshold} points...")
    
    # OPTIMIZATION: Fetch rostered players once at the start
    rostered_players = get_all_rostered_players(use_cache=True)
    
    # Build projection lookup from external data
    projection_lookup = {}
    for pos, players in external_projections.items():
        if isinstance(players, list):
            for player in players:
                if isinstance(player, dict):
                    name = player.get("name", "").lower()
                    projected = player.get("projected", 0)
                    projection_lookup[name] = projected
    
    # Identify positions that need help
    positions_needing_help = []
    
    for player in current_roster:
        # Skip if player is injured (they might have reduced projections due to injury)
        injury_status = player.get("injury_status", "Healthy")
        if injury_status != "Healthy":
            continue
            
        # Get projected points from external projections
        player_name = player.get("name", "").lower()
        projected_points = projection_lookup.get(player_name, 0)
        
        if projected_points < projection_threshold:
            positions_needing_help.append({
                "current_player": player.get("name"),
                "position": player.get("position"),
                "current_projection": projected_points,
                "team": player.get("team"),
                "player_id": player.get("player_id"),
                "injury_status": injury_status
            })
    
    if not positions_needing_help:
        return {
            "waiver_recommendations": [],
            "positions_analyzed": len(current_roster),
            "positions_needing_help": 0,
            "analysis": f"All healthy players projected above {projection_threshold} points. No waiver moves needed."
        }
    
    # Find waiver alternatives for each position
    waiver_recommendations = []
    
    for position_info in positions_needing_help:
        position = position_info["position"]
        current_projection = position_info["current_projection"]
        
        # OPTIMIZATION: Pass the pre-fetched rostered_players
        available_players = get_available_waiver_players(
            position=position,
            week=week,
            min_projected_points=max(current_projection + 1.0, 5.0),
            limit=5,
            rostered_players=rostered_players  # Pass cached roster
        )
        
        if available_players:
            # Get enhanced data for top waiver options using player name lookup
            top_options = []
            
            for waiver_player in available_players[:3]:
                player_name = waiver_player["player_name"]
                
                # Try to get enhanced data using player name lookup
                enhanced_info = {}
                try:
                    from app.player_data import get_player_by_name
                    enhanced_info = get_player_by_name(player_name) or {}
                except Exception as e:
                    print(f"Could not get enhanced data for {player_name}: {e}")
                
                # Get additional context
                projections_2025 = extract_2025_projections(enhanced_info) if enhanced_info else {}
                history_2024 = extract_2024_history(enhanced_info) if enhanced_info else {}
                
                season_projection = projections_2025.get("MISC_FPTS", 0)
                historical_avg = history_2024.get("recent4_avg", 0)
                
                improvement = waiver_player["projected_points"] - current_projection
                
                top_options.append({
                    "player_name": waiver_player["player_name"],
                    "team": waiver_player["team"],
                    "projected_points": waiver_player["projected_points"],
                    "ownership_pct": waiver_player["ownership_pct"],
                    "improvement": round(improvement, 1),
                    "season_projection": season_projection,
                    "2024_avg": historical_avg,
                    "recommendation_strength": _calculate_recommendation_strength(
                        improvement, waiver_player["ownership_pct"], historical_avg
                    )
                })
            
            waiver_recommendations.append({
                "position": position,
                "current_player": position_info["current_player"],
                "current_projection": current_projection,
                "waiver_options": top_options,
                "top_recommendation": top_options[0] if top_options else None,
                "urgency": "HIGH" if current_projection < 5 else "MEDIUM"
            })
    
    return {
        "waiver_recommendations": waiver_recommendations,
        "positions_analyzed": len(current_roster),
        "positions_needing_help": len(positions_needing_help),
        "total_waiver_options": sum(len(r["waiver_options"]) for r in waiver_recommendations),
        "analysis": f"Found waiver opportunities for {len(waiver_recommendations)} positions with projections under {projection_threshold} points.",
        "critical_needs": [r for r in waiver_recommendations if r.get("urgency") == "HIGH"]
    }

@tool
def get_position_waiver_targets(
    position: str,
    week: int,
    min_points: float = 4.0, 
    max_ownership: float = 25.0
) -> Dict[str, Any]:
    """Get specific waiver targets for a position with low ownership.
    
    Args:
        position: Position to analyze (QB, RB, WR, TE, K, DST)
        week: Current week number for projections
        min_points: Minimum projected points to consider
        max_ownership: Maximum ownership percentage for true "sleepers"
    
    Returns:
        Dict with top waiver targets for the position
    """
    print(f"Finding {position} waiver targets for week {week} with <{max_ownership}% ownership and >{min_points} projected points...")
    
    # OPTIMIZATION: Use cached roster
    rostered_players = get_all_rostered_players(use_cache=True)
    
    available_players = get_available_waiver_players(
        position=position,
        week=week,
        min_projected_points=min_points,
        limit=15,
        rostered_players=rostered_players  # Pass cached roster
    )
    
    # Filter by ownership and enhance with additional data
    low_owned_targets = []
    
    for player in available_players:
        if player["ownership_pct"] <= max_ownership:
            # Try to get enhanced data using player name
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
    
    # Sort by upside score
    low_owned_targets.sort(key=lambda x: x["upside_score"], reverse=True)
    
    return {
        "position": position,
        "week": week,
        "targets_found": len(low_owned_targets),
        "waiver_targets": low_owned_targets[:10],
        "top_sleeper": low_owned_targets[0] if low_owned_targets else None,
        "analysis": f"Found {len(low_owned_targets)} {position} targets under {max_ownership}% ownership for week {week}"
    }

def _calculate_recommendation_strength(improvement: float, ownership: float, historical_avg: float) -> str:
    """Calculate recommendation strength based on multiple factors."""
    if improvement >= 5 and ownership < 50 and historical_avg > 8:
        return "Strong"
    elif improvement >= 3 and ownership < 75:
        return "Moderate"
    elif improvement >= 1:
        return "Weak"
    else:
        return "Not Recommended"

def _calculate_upside_score(projected: float, ownership: float, season_proj: float, historical: float) -> float:
    """Calculate upside score for waiver targets."""
    # Higher projection = higher upside
    projection_score = projected * 0.4
    
    # Lower ownership = higher upside (inverse relationship)
    ownership_score = (100 - ownership) * 0.3 / 100
    
    # Season projection consistency
    season_score = (season_proj / 17) * 0.2 if season_proj > 0 else 0
    
    # Historical performance
    historical_score = historical * 0.1 if historical > 0 else 0
    
    return round(projection_score + ownership_score + season_score + historical_score, 2)

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

@tool
def debug_waiver_table(position: str = "TE", week: int = 1) -> Dict[str, Any]:
    """Debug tool to check waiver table contents and structure."""
    waiver_table = DDB.Table(WAIVER_TABLE)
    
    try:
        # Get a sample of waiver players
        resp = waiver_table.scan(
            FilterExpression=Attr("position").eq(normalize_position(position)),
            Limit=10
        )
        
        items = resp.get("Items", [])
        
        # Analyze the structure
        if items:
            sample_item = items[0]
            available_fields = list(sample_item.keys())
            
            # Check for required fields
            required_fields = ["player_season", "player_name", "position", "injury_status", "weekly_projections"]
            missing_fields = [field for field in required_fields if field not in available_fields]
            
            # Check data quality
            active_count = len([item for item in items if item.get("injury_status") == "ACTIVE"])
            projected_count = 0
            for item in items:
                weekly_projs = item.get("weekly_projections", {})
                if weekly_projs and str(week) in weekly_projs:
                    projected_count += 1
            
            return {
                "table_name": WAIVER_TABLE,
                "sample_count": len(items),
                "available_fields": available_fields,
                "missing_fields": missing_fields,
                "active_players": active_count,
                "players_with_week_projections": projected_count,
                "sample_data": items[:2],
                "analysis": f"Found {len(items)} {position} players, {active_count} active, {projected_count} with week {week} projections"
            }
        else:
            return {
                "table_name": WAIVER_TABLE,
                "error": f"No {position} players found in waiver table",
                "total_items_check": _check_total_table_size()
            }
            
    except Exception as e:
        return {
            "table_name": WAIVER_TABLE,
            "error": f"Error accessing waiver table: {str(e)}",
            "suggestion": "Check if WAIVER_TABLE environment variable is set correctly"
        }

def _check_total_table_size() -> Dict[str, Any]:
    """Quick check of total table size."""
    try:
        waiver_table = DDB.Table(WAIVER_TABLE)
        resp = waiver_table.scan(Limit=5)
        return {
            "total_sample": len(resp.get("Items", [])),
            "has_data": len(resp.get("Items", [])) > 0
        }
    except Exception as e:
        return {"error": str(e)}