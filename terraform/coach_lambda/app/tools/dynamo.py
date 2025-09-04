import os
from typing import Dict, Any, List, TypedDict, Optional
import boto3
from boto3.dynamodb.conditions import Key, Attr
from strands import tool
import json

DDB = boto3.resource("dynamodb")
TABLE_STATS = os.environ.get("DDB_TABLE_STATS", "fantasy-football-2024-stats")
TABLE_ROSTER = os.environ.get("DDB_TABLE_ROSTER", "fantasy-football-team-roster")


class RosterPlayer(TypedDict, total=False):
    name: str
    player_id: str
    position: str
    status: str
    team: str


class TeamRoster(TypedDict, total=False):
    team_id: str
    team_name: str
    players: List[RosterPlayer]


class HistoryRow(TypedDict, total=False):
    week: int
    fantasy_points: float
    opponent: str


def load_team_roster(team_id: str) -> TeamRoster:
    """Load a team's roster from DynamoDB at runtime (not as a tool).
    
    Args:
        team_id: the partition key (e.g., "1")
    Returns:
        TeamRoster with list of players
    """
    table = DDB.Table(TABLE_ROSTER)
    
    try:
        resp = table.get_item(Key={"team_id": team_id})
        item = resp.get("Item") or {}
        
        # Ensure proper shape
        players = item.get("players") or []
        
        return TeamRoster(
            team_id=item.get("team_id", team_id),
            team_name=item.get("team_name", "My Team"),
            players=players,
        )
    except Exception as e:
        # Return empty roster on error to prevent lambda failure
        print(f"Error loading roster for team {team_id}: {str(e)}")
        return TeamRoster(
            team_id=team_id,
            team_name="My Team",
            players=[],
        )

def format_roster_for_agent(roster: TeamRoster) -> str:
    """Format roster data as a clean string for the agent prompt."""
    if not roster.get("players"):
        return f"Team {roster['team_id']} has no players in roster."
    
    formatted = f"Team: {roster.get('team_name', 'My Team')} (ID: {roster['team_id']})\n"
    formatted += f"Total Players: {len(roster['players'])}\n"
    formatted += "*** USE THESE TEAM AFFILIATIONS (2025 CURRENT SEASON) ***\n\n"
    
    # Group by position for cleaner display
    by_position = {}
    for player in roster["players"]:
        pos = player.get("position", "UNKNOWN")
        if pos not in by_position:
            by_position[pos] = []
        by_position[pos].append(player)
    
    # Display by position
    position_order = ["QB", "RB", "WR", "TE", "K", "DST"]  # Common fantasy positions
    
    for pos in position_order:
        if pos in by_position:
            formatted += f"{pos}:\n"
            for player in by_position[pos]:
                status = player.get("status", "")
                team = player.get("team", "")
                status_str = f" ({status})" if status and status != "active" else ""
                team_str = f" - {team}" if team else ""
                formatted += f"  • {player.get('name', 'Unknown')}{team_str}{status_str}\n"
            formatted += "\n"
    
    # Add any remaining positions
    for pos, players in by_position.items():
        if pos not in position_order:
            formatted += f"{pos}:\n"
            for player in players:
                team = player.get("team", "")
                team_str = f" - {team}" if team else ""
                formatted += f"  • {player.get('name', 'Unknown')}{team_str}\n"
            formatted += "\n"
    
    formatted += "*** END CURRENT ROSTER - These are the correct 2025 team assignments ***\n"
    
    return formatted.strip()

def roster_to_json(roster: TeamRoster) -> str:
    """Convert roster to JSON string for agent context."""
    return json.dumps(roster, indent=2, default=str)


@tool
def get_player_history_2024(player_name: str, opponent: Optional[str] = None) -> Dict[str, Any]:
    """Get 2024 historical rows for a player, optionally filtering to an opponent.
    Args:
        player_name: Full display name matching your 2024 table
        opponent: Optional 2-3 letter team code to filter (e.g., 'CLE')
    Returns:
        dict with 'all' (list[HistoryRow]), 'recent4_avg', 'vs_opp_avg' (if any)
    """
    table = DDB.Table(TABLE_STATS)

    # The example item shows player_season key like "Rico Dowdle#2024"; we query by GSI or scan.
    # If you have a GSI, use it. For now, use a filtered scan to keep code generic.
    # NOTE: For large tables, add a GSI on player_name, season or (player_season).
    scan_kwargs = {
        "FilterExpression": Attr("player_name").eq(player_name) & Attr("season").eq(2024),
        "ProjectionExpression": "#w, fantasy_points, opponent",
        "ExpressionAttributeNames": {"#w": "week"},
    }

    items: List[Dict[str, Any]] = []
    resp = table.scan(**scan_kwargs)
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **scan_kwargs)
        items.extend(resp.get("Items", []))

    # Sort by week
    items.sort(key=lambda x: x.get("week", 0))

    # Compute recent-4 average
    recent = items[-4:] if len(items) >= 1 else []
    recent4_avg = round(sum(float(i.get("fantasy_points", 0.0)) for i in recent) / max(len(recent), 1), 4)

    vs_opp_avg = None
    vs_items = [i for i in items if opponent and i.get("opponent") == opponent]
    if vs_items:
        vs_opp_avg = round(sum(float(i.get("fantasy_points", 0.0)) for i in vs_items) / len(vs_items), 4)

    return {
        "all": [{"week": int(i.get("week", 0)),
                 "fantasy_points": float(i.get("fantasy_points", 0.0)),
                 "opponent": i.get("opponent", "")} for i in items],
        "recent4_avg": recent4_avg,
        "vs_opp_avg": vs_opp_avg,
    }