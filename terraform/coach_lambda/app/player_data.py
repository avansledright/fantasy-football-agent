# app/player_data.py
"""
Streamlined player data access for the unified fantasy-football-players table.
"""

import os
from typing import Dict, Any, List, Optional
import boto3
from boto3.dynamodb.conditions import Attr
from strands import tool
from app.utils import generate_player_id_candidates, normalize_player_name

DDB = boto3.resource("dynamodb")
PLAYERS_TABLE = os.environ.get("PLAYERS_TABLE", "fantasy-football-players")

def get_players_batch(player_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """Efficiently load multiple players using batch_get_item."""
    if not player_ids:
        return {}
    
    table = DDB.Table(PLAYERS_TABLE)
    all_data = {}
    
    try:
        # Process in batches of 100 (DynamoDB limit)
        for i in range(0, len(player_ids), 100):
            batch_ids = player_ids[i:i+100]
            
            request_items = {
                PLAYERS_TABLE: {
                    'Keys': [{'player_id': pid} for pid in batch_ids]
                }
            }
            
            resp = DDB.batch_get_item(RequestItems=request_items)
            
            for item in resp.get('Responses', {}).get(PLAYERS_TABLE, []):
                player_id = item.get('player_id')
                if player_id:
                    all_data[player_id] = item
            
            # Handle unprocessed keys
            while 'UnprocessedKeys' in resp and resp['UnprocessedKeys']:
                resp = DDB.batch_get_item(RequestItems=resp['UnprocessedKeys'])
                for item in resp.get('Responses', {}).get(PLAYERS_TABLE, []):
                    player_id = item.get('player_id')
                    if player_id:
                        all_data[player_id] = item
        
        return all_data
        
    except Exception as e:
        print(f"Error batch loading player data: {str(e)}")
        return {}

def get_player_by_name(player_name: str) -> Optional[Dict[str, Any]]:
    """Find a player by name using ID generation."""
    candidates = generate_player_id_candidates(player_name)
    player_data = get_players_batch(candidates)
    
    # Return first match found
    for player_id, data in player_data.items():
        stored_name = data.get("player_name", "")
        if (stored_name.lower() == player_name.lower() or 
            normalize_player_name(stored_name) == normalize_player_name(player_name)):
            return data
    
    return None

def extract_2024_history(player_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and format 2024 historical data."""
    historical = player_data.get("historical_seasons", {}).get("2024", {})
    weekly_stats = historical.get("weekly_stats", {})
    
    if not weekly_stats:
        return {"all": [], "recent4_avg": 0.0, "vs_opp_avg": None}
    
    # Convert to expected format
    all_weeks = []
    for week_str, week_data in weekly_stats.items():
        try:
            week_num = int(week_str)
            all_weeks.append({
                "week": week_num,
                "fantasy_points": float(week_data.get("fantasy_points", 0)),  # Convert to float
                "opponent": week_data.get("opponent", "")
            })
        except (ValueError, TypeError):
            continue
    
    all_weeks.sort(key=lambda x: x["week"])
    
    # Calculate recent 4 average
    recent_4 = all_weeks[-4:] if len(all_weeks) >= 4 else all_weeks
    recent4_avg = 0.0
    if recent_4:
        recent4_avg = round(sum(g["fantasy_points"] for g in recent_4) / len(recent_4), 2)
    
    return {"all": all_weeks, "recent4_avg": recent4_avg, "vs_opp_avg": None}

def extract_2025_projections(player_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract 2025 season projections."""
    return player_data.get("projections", {}).get("2025", {})

def extract_current_stats(player_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract 2025 current season stats."""
    current_stats = player_data.get("current_season_stats", {}).get("2025", {})
    
    all_weeks = []
    for week_str, week_data in current_stats.items():
        try:
            week_num = int(week_str)
            all_weeks.append({
                "week": week_num,
                "fantasy_points": float(week_data.get("fantasy_points", 0)),
                "opponent": week_data.get("opponent", ""),
                "team": week_data.get("team", "")
            })
        except (ValueError, TypeError):
            continue
    
    return {"weeks": sorted(all_weeks, key=lambda x: x["week"])}

def load_roster_player_data(roster_players: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Load comprehensive data for all roster players."""
    # Extract player IDs from roster
    player_ids = [p.get("player_id") for p in roster_players if p.get("player_id")]
    if not player_ids:
        # Fallback to name-based lookup
        all_data = {}
        for player in roster_players:
            name = player.get("name")
            if name:
                player_data = get_player_by_name(name)
                if player_data:
                    all_data[name] = player_data
        return all_data
    
    # Batch load by IDs
    unified_data = get_players_batch(player_ids)
    
    # Map back to player names for compatibility
    name_mapped_data = {}
    for player in roster_players:
        player_id = player.get("player_id")
        player_name = player.get("name")
        
        if player_id in unified_data and player_name:
            name_mapped_data[player_name] = unified_data[player_id]
    
    return name_mapped_data

def format_player_histories(all_data: Dict[str, Dict[str, Any]]) -> str:
    """Format player data for agent context."""
    if not all_data:
        return "No player data available."
    
    formatted = "COMPREHENSIVE PLAYER DATA (Unified Table):\n\n"
    
    for player_name, player_data in all_data.items():
        if not player_data:
            formatted += f"{player_name}: No data available\n\n"
            continue
        
        # 2024 History
        history = extract_2024_history(player_data)
        history_summary = f"2024: {len(history['all'])} games, {history['recent4_avg']} avg"
        
        # 2025 Projections  
        projections = extract_2025_projections(player_data)
        season_fpts = projections.get("MISC_FPTS", 0)
        proj_summary = f"2025 Proj: {season_fpts} season points"
        
        # Current 2025 stats
        current = extract_current_stats(player_data)
        current_games = len(current["weeks"])
        current_summary = f"2025: {current_games} games played"
        
        formatted += f"{player_name}:\n"
        formatted += f"  • {history_summary}\n"
        formatted += f"  • {proj_summary}\n" 
        formatted += f"  • {current_summary}\n\n"
    
    return formatted.strip()

@tool
def analyze_player_performance(player_name: str, weeks_back: int = 4) -> Dict[str, Any]:
    """Comprehensive player performance analysis using unified data."""
    player_data = get_player_by_name(player_name)
    
    if not player_data:
        return {
            "player_name": player_name,
            "error": "Player not found in unified database",
            "analysis": "No data available"
        }
    
    # Extract all data types
    history_2024 = extract_2024_history(player_data)
    projections_2025 = extract_2025_projections(player_data)
    current_2025 = extract_current_stats(player_data)
    
    # Calculate recent performance
    recent_weeks = current_2025["weeks"][-weeks_back:] if current_2025["weeks"] else []
    recent_avg = 0.0
    if recent_weeks:
        recent_avg = round(sum(w["fantasy_points"] for w in recent_weeks) / len(recent_weeks), 2)
    
    return {
        "player_name": player_name,
        "position": player_data.get("position"),
        "2024_season_avg": history_2024["recent4_avg"],
        "2024_games": len(history_2024["all"]),
        "2025_recent_avg": recent_avg,
        "2025_games_played": len(current_2025["weeks"]),
        "2025_projected_points": projections_2025.get("MISC_FPTS", 0),
        "recent_games": recent_weeks,
        "analysis": f"{player_name}: Recent avg {recent_avg}, 2024 avg {history_2024['recent4_avg']}, projected {projections_2025.get('MISC_FPTS', 0)}"
    }

@tool  
def compare_roster_players(player_names: List[str], metric: str = "recent") -> Dict[str, Any]:
    """Compare multiple players across different performance metrics."""
    if not player_names:
        return {"error": "No players provided"}
    
    comparisons = []
    
    for name in player_names:
        player_data = get_player_by_name(name)
        
        if not player_data:
            comparisons.append({
                "player_name": name,
                "error": "Player not found"
            })
            continue
        
        history_2024 = extract_2024_history(player_data)
        projections_2025 = extract_2025_projections(player_data)
        current_2025 = extract_current_stats(player_data)
        
        if metric == "recent":
            recent_weeks = current_2025["weeks"][-4:] if current_2025["weeks"] else []
            score = round(sum(w["fantasy_points"] for w in recent_weeks) / len(recent_weeks), 2) if recent_weeks else 0
        elif metric == "2024":
            score = history_2024["recent4_avg"]
        elif metric == "projected":
            score = projections_2025.get("MISC_FPTS", 0)
        else:
            score = 0
        
        comparisons.append({
            "player_name": name,
            "position": player_data.get("position"),
            "score": score,
            "metric": metric
        })
    
    # Sort by score
    comparisons.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return {
        "metric": metric,
        "comparisons": comparisons,
        "top_performer": comparisons[0] if comparisons else None
    }

@tool
def analyze_injury_impact(roster_players: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze injury impact across the roster and suggest healthy alternatives."""
    injured_players = []
    healthy_alternatives = {}
    
    # Group players by position
    by_position = {}
    for player in roster_players:
        pos = player.get("position", "")
        if pos not in by_position:
            by_position[pos] = []
        by_position[pos].append(player)
    
    # Analyze each position for injury concerns
    for position, players in by_position.items():
        injured_in_pos = []
        healthy_in_pos = []
        
        for player in players:
            injury_status = player.get("injury_status", "Healthy")
            if injury_status != "Healthy":
                injured_players.append({
                    "name": player.get("name"),
                    "position": position,
                    "injury_status": injury_status,
                    "team": player.get("team"),
                    "severity": _get_injury_severity(injury_status)
                })
                injured_in_pos.append(player)
            else:
                healthy_in_pos.append(player)
        
        # If there are injured starters, note healthy alternatives
        if injured_in_pos and healthy_in_pos:
            healthy_alternatives[position] = [
                p.get("name") for p in healthy_in_pos
            ]
    
    return {
        "total_injured": len(injured_players),
        "injured_players": injured_players,
        "healthy_alternatives": healthy_alternatives,
        "recommendation": _generate_injury_recommendation(injured_players, healthy_alternatives),
        "analysis": f"Found {len(injured_players)} injured players across roster. "
                   f"Healthy alternatives available for {len(healthy_alternatives)} positions."
    }

def _get_injury_severity(injury_status: str) -> str:
    """Get injury severity level."""
    severity_map = {
        "Healthy": "None",
        "Questionable": "Low",
        "Doubtful": "High", 
        "Out": "Critical",
        "IR": "Critical",
        "PUP": "Critical",
        "Suspended": "Critical"
    }
    return severity_map.get(injury_status, "Unknown")

def _generate_injury_recommendation(injured_players: List[Dict], healthy_alternatives: Dict) -> str:
    """Generate injury-based lineup recommendations."""
    if not injured_players:
        return "No injury concerns. Proceed with normal optimization."
    
    critical_injuries = [p for p in injured_players if p["severity"] == "Critical"]
    
    if critical_injuries:
        critical_names = [p["name"] for p in critical_injuries]
        return f"AVOID: {', '.join(critical_names)} should not be started due to critical injury status."
    
    risky_injuries = [p for p in injured_players if p["severity"] == "High"]
    if risky_injuries:
        risky_names = [p["name"] for p in risky_injuries]
        return f"CAUTION: {', '.join(risky_names)} are high-risk due to injury. Consider healthy alternatives."
    
    return "Monitor questionable players closely. Consider healthy alternatives if available."