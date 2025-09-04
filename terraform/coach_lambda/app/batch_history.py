import os
from typing import Dict, Any, List, Optional
import boto3
from boto3.dynamodb.conditions import Attr
from concurrent.futures import ThreadPoolExecutor
import json

DDB = boto3.resource("dynamodb")
TABLE_STATS = os.environ.get("DDB_TABLE_STATS", "fantasy-football-2024-stats")

def load_all_player_histories_batch(player_names: List[str]) -> Dict[str, Dict[str, Any]]:
    """Load 2024 history for all roster players in batch.
    
    Args:
        player_names: List of player names to get history for
    
    Returns:
        Dict mapping player_name -> history data
        {
            "Josh Allen": {
                "all": [...],
                "recent4_avg": 22.4,
                "vs_opp_avg": None
            }
        }
    """
    if not player_names:
        return {}
    
    table = DDB.Table(TABLE_STATS)
    all_histories = {}
    
    # Method 1: Single scan with OR filter (if DynamoDB supports it well)
    try:
        # Create filter for all players at once
        filter_expr = None
        for player_name in player_names:
            player_filter = Attr("player_name").eq(player_name) & Attr("season").eq(2024)
            if filter_expr is None:
                filter_expr = player_filter
            else:
                filter_expr = filter_expr | player_filter
        
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ProjectionExpression": "player_name, #w, fantasy_points, opponent",
            "ExpressionAttributeNames": {"#w": "week"},
        }
        
        # Collect all items
        items = []
        resp = table.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        
        while "LastEvaluatedKey" in resp:
            resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **scan_kwargs)
            items.extend(resp.get("Items", []))
        
        # Group by player
        by_player = {}
        for item in items:
            player_name = item.get("player_name")
            if player_name not in by_player:
                by_player[player_name] = []
            by_player[player_name].append(item)
        
        # Process each player's data
        for player_name in player_names:
            player_items = by_player.get(player_name, [])
            all_histories[player_name] = _process_player_history(player_items)
        
        return all_histories
        
    except Exception as e:
        print(f"Batch scan failed: {e}, falling back to parallel individual queries")
        return load_all_player_histories_parallel(player_names)

def load_all_player_histories_parallel(player_names: List[str]) -> Dict[str, Dict[str, Any]]:
    """Load player histories in parallel using ThreadPoolExecutor."""
    
    def get_single_player_history(player_name: str) -> tuple[str, Dict[str, Any]]:
        """Get history for a single player."""
        table = DDB.Table(TABLE_STATS)
        
        scan_kwargs = {
            "FilterExpression": Attr("player_name").eq(player_name) & Attr("season").eq(2024),
            "ProjectionExpression": "#w, fantasy_points, opponent",
            "ExpressionAttributeNames": {"#w": "week"},
        }
        
        items = []
        resp = table.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        
        while "LastEvaluatedKey" in resp:
            resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **scan_kwargs)
            items.extend(resp.get("Items", []))
        
        return player_name, _process_player_history(items)
    
    # Use ThreadPoolExecutor to parallelize the queries
    all_histories = {}
    
    with ThreadPoolExecutor(max_workers=min(10, len(player_names))) as executor:
        # Submit all tasks
        future_to_player = {
            executor.submit(get_single_player_history, player_name): player_name 
            for player_name in player_names
        }
        
        # Collect results
        for future in future_to_player:
            try:
                player_name, history = future.result(timeout=30)  # 30 second timeout per player
                all_histories[player_name] = history
            except Exception as e:
                player_name = future_to_player[future]
                print(f"Failed to load history for {player_name}: {e}")
                all_histories[player_name] = _empty_history()
    
    return all_histories

def _process_player_history(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process raw DynamoDB items into structured history data."""
    if not items:
        return _empty_history()
    
    # Sort by week
    items.sort(key=lambda x: x.get("week", 0))
    
    # Compute recent-4 average
    recent = items[-4:] if len(items) >= 1 else []
    recent4_avg = round(
        sum(float(i.get("fantasy_points", 0.0)) for i in recent) / max(len(recent), 1), 
        4
    )
    
    return {
        "all": [
            {
                "week": int(i.get("week", 0)),
                "fantasy_points": float(i.get("fantasy_points", 0.0)),
                "opponent": i.get("opponent", "")
            } 
            for i in items
        ],
        "recent4_avg": recent4_avg,
        "vs_opp_avg": None,  # We'll compute this on-demand if needed
    }

def _empty_history() -> Dict[str, Any]:
    """Return empty history structure."""
    return {
        "all": [],
        "recent4_avg": 0.0,
        "vs_opp_avg": None,
    }

def format_all_histories_for_agent(histories: Dict[str, Dict[str, Any]]) -> str:
    """Format all player histories as context for the agent."""
    if not histories:
        return "No player history data available."
    
    formatted = "2024 PLAYER PERFORMANCE DATA (HISTORICAL - Teams may have changed for 2025):\n\n"
    
    for player_name, history in histories.items():
        if not history.get("all"):
            formatted += f"{player_name}: No 2024 data available\n\n"
            continue
        
        games_played = len(history["all"])
        recent4_avg = history.get("recent4_avg", 0.0)
        total_points = sum(game["fantasy_points"] for game in history["all"])
        season_avg = round(total_points / games_played, 2) if games_played > 0 else 0.0
        
        formatted += f"{player_name}:\n"
        formatted += f"  • Games: {games_played}, Season Avg: {season_avg}, Recent 4 Avg: {recent4_avg}\n"
        
        # Show last 4 games
        recent_games = history["all"][-4:] if len(history["all"]) >= 4 else history["all"]
        if recent_games:
            recent_str = ", ".join([
                f"Wk{game['week']}:{game['fantasy_points']}" 
                for game in recent_games
            ])
            formatted += f"  • Recent: {recent_str}\n"
        
        formatted += "\n"
    
    formatted += "\nNOTE: Team affiliations in this historical data are from 2024 and may not reflect current 2025 teams. Use roster data above for correct team assignments.\n"
    
    return formatted.strip()

def compute_vs_opponent_avg(history: Dict[str, Any], opponent: str) -> Optional[float]:
    """Compute average against specific opponent from history data."""
    if not history.get("all") or not opponent:
        return None
    
    vs_games = [
        game for game in history["all"] 
        if game.get("opponent", "").upper() == opponent.upper()
    ]
    
    if not vs_games:
        return None
    
    return round(
        sum(game["fantasy_points"] for game in vs_games) / len(vs_games), 
        4
    )