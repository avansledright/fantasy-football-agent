#!/usr/bin/env python3
import os
import json
from decimal import Decimal
import boto3
from pathlib import Path
from botocore.exceptions import ClientError

# Constants
TABLE_NAME = "2025-2026-fantasy-football-player-data"
REGION = "us-west-2"
COMBINED_DIR = Path("combined")

# DynamoDB client + resource
dynamodb = boto3.resource("dynamodb", region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

def to_decimal(obj):
    """Recursively convert floats to Decimal for DynamoDB compatibility."""
    if isinstance(obj, list):
        return [to_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj

def load_json_file(filepath: Path):
    """Load JSON array of players from file."""
    with open(filepath, "r") as f:
        return json.load(f)

def purge_table():
    """Delete all items from the DynamoDB table."""
    print(f"🗑️  Clearing table: {TABLE_NAME}")

    # Discover table key schema
    key_schema = table.key_schema
    key_names = [k["AttributeName"] for k in key_schema]
    print(f"📋 Table keys: {key_names}")

    scan_kwargs = {}
    done = False
    start_key = None

    while not done:
        if start_key:
            scan_kwargs["ExclusiveStartKey"] = start_key
        response = table.scan(**scan_kwargs)
        items = response.get("Items", [])

        for item in items:
            key = {k: item[k] for k in key_names}
            table.delete_item(Key=key)
            print(f"   ❌ Deleted {key}")

        start_key = response.get("LastEvaluatedKey", None)
        done = start_key is None

def put_player(player: dict):
    """Put a player object into DynamoDB."""
    try:
        player = to_decimal(player)  # convert floats -> Decimal
        table.put_item(Item=player)
        print(f"✅ Inserted {player.get('Player')} ({player.get('POSITION')})")
    except ClientError as e:
        print(f"❌ Failed to insert {player.get('Player')}: {e}")

def main():
    if not COMBINED_DIR.exists():
        print(f"❌ Folder not found: {COMBINED_DIR}")
        return

    # Purge first
    purge_table()

    # Insert fresh data
    for json_file in COMBINED_DIR.glob("*.json"):
        print(f"\n📂 Processing {json_file.name}")
        players = load_json_file(json_file)

        if not isinstance(players, list):
            print(f"⚠️ Skipping {json_file}, not a list of players")
            continue

        for player in players:
            if "POSITION" not in player:
                player["POSITION"] = json_file.stem  

            player_id = f"{player['Player']}#{player['POSITION']}"
            player["player_id"] = player_id  

            put_player(player)

if __name__ == "__main__":
    main()
