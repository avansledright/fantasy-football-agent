import os
import requests
import csv
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
from decimal import Decimal

# Configuration (use your defaults or override via env vars)
TABLE_NAME = os.getenv("DDB_TABLE_NAME", "2025-2026-fantasy-football-player-data")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
BASE_URL_TEMPLATE = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "player_stats/stats_player_week_{season}.csv"
)

def fetch_weekly_stats(season: int):
    """Download NFL player-level weekly stats CSV for the given season."""
    url = BASE_URL_TEMPLATE.format(season=season)
    print(f"Fetching weekly stats from {url} …")
    resp = requests.get(url)
    resp.raise_for_status()
    decoded = resp.content.decode("utf-8").splitlines()
    reader = csv.DictReader(decoded)
    return list(reader)

def write_to_dynamodb(records: list):
    """Write each record into DynamoDB in batch."""
    dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
    table = dynamodb.Table(TABLE_NAME)

    with table.batch_writer() as batch:
        for rec in records:
            pid = rec.get("player_id") or rec.get("player_name")
            if not pid:
                continue
            item = {"player_id": str(pid)}
            # Include all available fields—convert numeric values as needed
            for k, v in rec.items():
                item[k] = _convert_value(v)
            try:
                batch.put_item(Item=item)
            except ClientError as e:
                print(f"Error writing player {pid}: {e}")

def _convert_value(val: str):
    """Helper to convert strings to int/Decimal when possible (no floats)."""
    if val is None or val == "":
        return None
    try:
        if "." in val:
            return Decimal(val)
        return int(val)
    except Exception:
        return val  # leave as string if not numeric

def main():
    # Determine last completed season based on current month
    now = datetime.today()
    last_season = now.year - 1 if now.month >= 9 else now.year - 2
    print(f"Last completed season determined as: {last_season}")

    stats = fetch_weekly_stats(last_season)
    print(f"Fetched {len(stats)} weekly player records.")

    print("Writing to DynamoDB …")
    write_to_dynamodb(stats)
    print("Done!")

if __name__ == "__main__":
    main()
