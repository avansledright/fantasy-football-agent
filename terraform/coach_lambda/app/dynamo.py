# app/dynamo.py
"""
Simplified team roster loading (keeping existing roster table structure).
"""

import os
from typing import Dict, Any, List
import boto3

DDB = boto3.resource("dynamodb")
TABLE_ROSTER = os.environ.get("DDB_TABLE_ROSTER", "fantasy-football-team-roster")

def load_team_roster(team_id: str) -> Dict[str, Any]:
    """Load team roster from DynamoDB."""
    table = DDB.Table(TABLE_ROSTER)
    
    try:
        resp = table.get_item(Key={"team_id": team_id})
        item = resp.get("Item", {})
        
        return {
            "team_id": item.get("team_id", team_id),
            "team_name": item.get("team_name", "My Team"),
            "players": item.get("players", []),
        }
    except Exception as e:
        print(f"Error loading roster for team {team_id}: {str(e)}")
        return {
            "team_id": team_id,
            "team_name": "My Team", 
            "players": [],
        }

def format_roster_for_agent(roster: Dict[str, Any]) -> str:
    """Format roster for agent context with injury status highlighting."""
    if not roster.get("players"):
        return f"Team {roster['team_id']} has no players."
    
    formatted = f"Team: {roster.get('team_name', 'My Team')} (ID: {roster['team_id']})\n"
    formatted += f"Total Players: {len(roster['players'])}\n\n"
    
    # Group by position
    by_position = {}
    for player in roster["players"]:
        pos = player.get("position", "UNKNOWN")
        if pos not in by_position:
            by_position[pos] = []
        by_position[pos].append(player)
    
    # Display by position with injury alerts
    for pos in ["QB", "RB", "WR", "TE", "K", "DST"]:
        if pos in by_position:
            formatted += f"{pos}:\n"
            for player in by_position[pos]:
                team = player.get("team", "")
                status = player.get("status", "")
                injury_status = player.get("injury_status", "Healthy")
                
                # Build status string
                status_parts = []
                if status != "starter":
                    status_parts.append(status)
                if injury_status != "Healthy":
                    status_parts.append(f"INJURY: {injury_status}")
                
                status_str = f" ({', '.join(status_parts)})" if status_parts else ""
                formatted += f"  • {player.get('name', 'Unknown')} - {team}{status_str}\n"
            formatted += "\n"
    
    return formatted.strip()