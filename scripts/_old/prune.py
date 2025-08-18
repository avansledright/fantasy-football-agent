# prune_dynamodb.py
import boto3

# DynamoDB setup
dynamodb = boto3.resource("dynamodb")
table_name = "2025-2026-fantasy-football-player-data"
table = dynamodb.Table(table_name)

# Positions to exclude (non-fantasy skill positions)
DEFENSIVE_POSITIONS = {"DL", "DE", "DT", "NT", "LB", "OLB", "ILB", "CB", "S", "SS", "FS", "DB", "EDGE"}


def scan_all_players():
    """Paginated scan to retrieve all players from DynamoDB."""
    players = []
    response = table.scan()
    players.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        players.extend(response.get("Items", []))

    return players


def prune_table():
    """Remove irrelevant players from DynamoDB."""
    players = scan_all_players()
    print(f"Scanned {len(players)} players…")

    removed_count = 0

    for player in players:
        pos = player.get("position")
        points = float(player.get("fantasy_points_ppr", 0))
        injured = player.get("injury_status", "").lower() in ["injured", "out", "ir"]

        should_remove = False

        # Rule 1: Remove defensive players
        if pos in DEFENSIVE_POSITIONS:
            should_remove = True

        # Rule 2: Remove 0-point players if not injured
        if points == 0 and not injured:
            should_remove = True

        if should_remove:
            table.delete_item(Key={"player_id": player["player_id"]})
            removed_count += 1
            print(f"❌ Removed {player.get('player_display_name')} ({pos})")

    print(f"✅ Pruning complete. Removed {removed_count} players.")


if __name__ == "__main__":
    prune_table()
