# tools/fantasy_draft_tool.py
import boto3
from decimal import Decimal
from strands import tool

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = "2025-2026-fantasy-football-player-data"
table = dynamodb.Table(TABLE_NAME)

@tool
def get_best_available_player(my_team_needs: dict, already_drafted: list[str]) -> dict:
    """
    Selects the best available player for the user's fantasy football draft.

    Args:
        my_team_needs (dict): A dictionary showing needed positions (e.g., {"QB": 1, "RB": 2, "WR": 1}).
        already_drafted (list[str]): A list of player_ids that have already been drafted.

    Returns:
        dict: Recommended player details (player_id, name, position, team, fantasy_points_ppr).
    """
    # Scan DynamoDB for all players
    response = table.scan()
    items = response.get("Items", [])

    # Filter out drafted players
    available = [p for p in items if p["player_id"] not in already_drafted]

    # Filter by team needs
    needed_positions = set(my_team_needs.keys())
    filtered = [p for p in available if p["position"] in needed_positions]

    # Sort by fantasy points PPR (descending)
    sorted_players = sorted(
        filtered,
        key=lambda x: Decimal(x.get("fantasy_points_ppr", 0)),
        reverse=True,
    )

    if not sorted_players:
        return {"message": "No suitable players found"}

    # Return top recommended player
    top = sorted_players[0]
    return {
        "player_id": top["player_id"],
        "player_display_name": top.get("player_display_name"),
        "position": top.get("position"),
        "team": top.get("team"),
        "fantasy_points_ppr": str(top.get("fantasy_points_ppr", 0)),
    }
