# tools/fantasy_draft_tool.py - Updated for 2025 projections + 2024 actuals
import boto3
from strands import tool
from decimal import Decimal
from typing import Dict, List

# DynamoDB setup
dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
table = dynamodb.Table("2025-2026-fantasy-football-player-data")

# Position scarcity and replacement values (12-team league)
POSITION_SCARCITY = {
    "QB": 0.85,
    "RB": 1.25,
    "WR": 1.05,
    "TE": 1.15,
    "K": 0.60,
    "DST": 0.65
}

REPLACEMENT_BASELINES = {
    "QB": 250,
    "RB": 150,
    "WR": 140,
    "TE": 100,
    "K": 80,
    "DST": 75
}

def to_float(value, default=0.0):
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except Exception:
        return default

def get_all_fantasy_players(drafted_players=None):
    """Get all fantasy-relevant players from DynamoDB (using 2025 projections)."""
    try:
        players = []
        response = table.scan()
        players.extend(response.get("Items", []))

        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            players.extend(response.get("Items", []))

        # Strip #POS for comparison if needed
        drafted_names = {d.split("#")[0] for d in (drafted_players or [])}

        # Remove drafted players
        filtered = [
            p for p in players
            if p.get("player_id") not in drafted_players
            and p.get("Player") not in drafted_names
        ]

        print(f"DEBUG: Loaded {len(filtered)} players after excluding drafted")
        return filtered
    except Exception as e:
        print(f"DEBUG: Error loading players: {e}")
        return []

def calculate_player_value(player: Dict, team_needs: Dict, drafted_players: List[str]) -> float:
    """Calculate draft value using 2025 projections with 2024 actuals as context."""
    player_id = player.get("player_id")
    position = player.get("POSITION") or player.get("position")

    if not player_id or not position:
        return -9999

    # Exclude if already drafted (regardless of which team took them)
    if player_id in drafted_players:
        return -9999

    # Grab 2025 projection + 2024 actuals
    proj = player.get("2025_projection", {})
    actuals = player.get("2024_actuals", {})

    proj_points = to_float(proj.get("MISC_FPTS"), 0)
    actual_points = to_float(actuals.get("MISC_FPTS"), 0)

    games_played = int(actuals.get("MISC_G", 16)) if actuals else 16

    if proj_points <= 0 and actual_points <= 0:
        return -9999

    # Weighted fantasy points
    fantasy_points = proj_points * 0.7 + actual_points * 0.3

    replacement = REPLACEMENT_BASELINES.get(position, 50)
    vorp = fantasy_points - replacement

    durability = min(games_played / 17, 1.0) if games_played > 0 else 0.5

    age = int(player.get("age", 25))
    years_exp = int(player.get("years_exp", 1))

    if position == "QB":
        age_factor = 1.0 if 26 <= age <= 34 else 0.95 if age <= 37 else 0.85
    elif position == "RB":
        age_factor = 1.0 if 22 <= age <= 27 else 0.90 if age <= 29 else 0.75
    else:
        age_factor = 1.0 if 24 <= age <= 29 else 0.95 if age <= 31 else 0.85

    exp_factor = 0.85 if years_exp == 0 else (0.95 if years_exp <= 2 else 1.0)

    rank = int(proj.get("Rank") or actuals.get("Rank") or 999)
    if rank > 100:
        injury_factor = 0.7
    elif rank > 50:
        injury_factor = 0.9
    else:
        injury_factor = 1.0

    scarcity = POSITION_SCARCITY.get(position, 1.0)

    position_need = team_needs.get(position, 0)
    flex_need = team_needs.get("FLEX", 0)
    if position_need > 0:
        need_multiplier = 1.5
    elif position in ["RB", "WR", "TE"] and flex_need > 0:
        need_multiplier = 1.2
    else:
        need_multiplier = 0.8

    actual_ppg = actual_points / max(games_played, 1)
    consistency_bonus = min(actual_ppg / 20, 0.1)

    final_score = (
        vorp * durability * age_factor * exp_factor * injury_factor *
        scarcity * need_multiplier * (1 + consistency_bonus)
    )

    return final_score

@tool
def get_best_available_player(team_needs: dict, your_roster: dict, already_drafted: list,
                              top_n: int = 5, scoring_format: str = "ppr",
                              league_size: int = 12) -> dict:
    """Return best players using 2025 projections (with 2024 actuals context).
    
    - team_needs: dict of remaining roster needs
    - your_roster: dict of your current players (for context only)
    - already_drafted: list of all drafted player_ids (exclude them)
    """
    print(f"DEBUG: Starting recommendation with team_needs={team_needs}")
    print(f"DEBUG: Your roster snapshot: {your_roster}")
    print(f"DEBUG: Already drafted count={len(already_drafted)}")

    all_players = get_all_fantasy_players(already_drafted)
    scored = []

    for p in all_players:
        score = calculate_player_value(p, team_needs, already_drafted)
        if score > 0:
            proj = p.get("2025_projection", {})
            actuals = p.get("2024_actuals", {})

            proj_points = to_float(proj.get("MISC_FPTS"), 0)
            actual_points = to_float(actuals.get("MISC_FPTS"), 0)

            games_played = int(actuals.get("MISC_G", 16)) if actuals else 16
            ppg = (proj_points or actual_points) / max(games_played, 1)

            scored.append({
                "player_id": p.get("player_id"),
                "name": p.get("Player"),
                "position": p.get("POSITION"),
                "value_score": round(score, 1),
                "2025_proj_points": proj_points,
                "2024_points": actual_points,
                "points_per_game": round(ppg, 1),
                "rank": int(proj.get("Rank") or actuals.get("Rank") or 999)
            })

    if not scored:
        return {"error": "No players available"}

    scored.sort(key=lambda x: x["value_score"], reverse=True)
    best = scored[0]

    return {
        "primary_recommendation": best,
        "alternatives": scored[1:top_n],
        "team_needs": team_needs,
        "your_roster": your_roster,
        "total_available": len(scored),
        "data_source": "2025 projections + 2024 actuals"
    }
