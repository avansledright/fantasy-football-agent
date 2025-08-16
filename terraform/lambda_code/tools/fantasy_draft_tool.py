# tools/fantasy_draft_tool.py
import boto3
from strands import tool

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("2025-2026-fantasy-football-player-data")

# Define replacement-level baselines for a 12-team league
REPLACEMENT_VALUES = {
    "QB": 250,   # QB12 baseline
    "RB": 170,   # RB24 baseline
    "WR": 180,   # WR24 baseline
    "TE": 120,   # TE12 baseline
    "K": 100,    # K12 baseline
    "DEF": 90    # DEF12 baseline
}

# Positional scarcity multipliers
SCARCITY_FACTORS = {
    "RB": 1.2,
    "WR": 1.1,
    "TE": 1.0,
    "QB": 0.9,
    "K": 0.7,
    "DEF": 0.7
}

def scan_all_players():
    """Retrieve all players from DynamoDB using pagination."""
    players = []
    response = table.scan()
    players.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        players.extend(response.get("Items", []))

    return players

def calculate_player_score(player, team_needs, drafted_players):
    """Calculate a composite score for a player using VORP + scarcity + team needs."""
    player_id = player["player_id"]
    position = player["position"]
    points = float(player.get("fantasy_points_ppr", 0))

    # Skip already drafted
    if player_id in drafted_players:
        return -9999  

    # Value Over Replacement Player (VORP)
    replacement_value = REPLACEMENT_VALUES.get(position, 0)
    vorp = points - replacement_value

    # Scarcity adjustment
    scarcity_factor = SCARCITY_FACTORS.get(position, 1.0)

    # If position already filled (team needs <= 0), reduce priority
    if team_needs.get(position, 0) <= 0:
        scarcity_factor *= 0.5  

    # Final score
    return vorp * scarcity_factor

@tool
def get_best_available_player(team_needs: dict, already_drafted: list) -> dict:
    """
    Recommend the best available fantasy player.
    Considers PPR, positional needs, and consistency.
    
    Args:
        team_needs (dict): Remaining positions to fill (e.g., {"RB": 1, "WR": 2})
        already_drafted (list): List of player IDs already drafted.
    
    Returns:
        dict: Recommended player
    """

    # Scan all players
    players = scan_all_players()

    # Remove drafted players
    available = [p for p in players if p["player_id"] not in already_drafted]

    if not available:
        return {"error": "No available players left."}

    # Positional priorities based on remaining needs
    # More need = higher weight
    base_priority = {
        "RB": 1.0,
        "WR": 1.0,
        "QB": 0.7,
        "TE": 0.3,
        "K": 0.3,
        "DST": 0.3
    }

    # Adjust priorities adaptively by multiplying with needs
    adaptive_priority = {}
    for pos, base_weight in base_priority.items():
        needed = team_needs.get(pos, 0)
        adaptive_priority[pos] = base_weight * (1 + needed)

    def score(player):
        ppr = float(player.get("fantasy_points_ppr", 0))
        consistency = float(player.get("games", 1))
        position = player.get("position", "NA")

        # Weighted score
        return (
            0.6 * ppr +
            0.3 * adaptive_priority.get(position, 0.1) +
            0.1 * (ppr / consistency if consistency > 0 else 0)
        )

    # Pick best player
    best_player = max(available, key=score)

    return {
        "recommendation": {
            "name": best_player.get("player_display_name"),
            "position": best_player.get("position"),
            "team": best_player.get("recent_team"),
            "fantasy_points_ppr": float(best_player.get("fantasy_points_ppr", 0)),
            "score": score(best_player)
        }
    }