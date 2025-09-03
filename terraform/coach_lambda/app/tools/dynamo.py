import os
from typing import Dict, Any, List, TypedDict, Optional
import boto3
from boto3.dynamodb.conditions import Key, Attr
from strands import tool

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


@tool
def get_team_roster(team_id: str) -> TeamRoster:
    """Load a team's roster from DynamoDB (fantasy-football-team-roster).
    Args:
        team_id: the partition key (e.g., "1")
    Returns:
        TeamRoster with list of players
    """
    table = DDB.Table(TABLE_ROSTER)
    # Primary key is team_id in the example
    resp = table.get_item(Key={"team_id": team_id})
    item = resp.get("Item") or {}
    # Ensure shape
    players = item.get("players") or []
    return TeamRoster(
        team_id=item.get("team_id", team_id),
        team_name=item.get("team_name", "My Team"),
        players=players,
    )


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
