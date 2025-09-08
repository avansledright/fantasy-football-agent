import os
import json
import requests
import boto3
from datetime import datetime

# ==============================================================================
# AWS AND API CONFIGURATION
# ==============================================================================

def load_environment_variables():
    """
    Loads environment variables for local testing if they are not set.
    """
    if "LEAGUE_ID" not in os.environ:
        print("Loading local environment variables for testing...")
        # IMPORTANT: Replace these dummy values with your actual information
        os.environ["LEAGUE_ID"] = "82658293"
        os.environ["SEASON_ID"] = "2025"
        os.environ["PLAYER_TABLE_NAME"] = "fantasy-football-agent-2025-waiver-table"
        os.environ["ESPN_S2"] = "AEBLV49KdF2as%2F6rR5%2BqYJrDSDiYKqj3Yc7ZoeinkzAKrZrLZFB0CivW6LleWS%2BoRurxx4BAXP7dL6V9HPMEN%2Bjl0UflFe4JTlUzLCBfdIrqHFXtWgPvN3z%2BNM5lZdiYGORzULHz%2BmDEmfPSjj2%2Ffz7K5wwGMEcrJLVYdP%2FMBG5dlN3xemFgCTzZ6sOsvyuXVKiB3yMu5s4ZQkIJg1LfCG30HwIb43ut60SCKMOlk1JRwFWOWGQlMg7GefA5nsCkxCkVpch6T%2F2Erb52Z7XNx%2BQ87p6m3Q87c7Nn60BpHsNZiA%3D%3D"
        os.environ["SWID"] = "{8535878A-6DD2-49D2-ACB6-8043D652A44C}"

# ==============================================================================
# DYNAMODB INTERACTION FUNCTIONS
# ==============================================================================

def get_dynamodb_resource():
    try:
        boto3.set_stream_logger(name='boto3', level=os.environ.get('BOTO3_LOG_LEVEL', 'ERROR'))
        boto3.set_stream_logger(name='botocore', level=os.environ.get('BOTO3_LOG_LEVEL', 'ERROR'))
        return boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-2"))
    except Exception as e:
        print(f"Error getting DynamoDB resource: {e}")
        return None

def store_players_in_dynamodb(dynamodb_items, table_name):
    dynamodb = get_dynamodb_resource()
    if not dynamodb:
        print("Could not get DynamoDB resource.")
        return

    table = dynamodb.Table(table_name)
    
    try:
        print(f"Starting batch write to DynamoDB table '{table_name}'.")
        with table.batch_writer() as batch:
            for item in dynamodb_items:
                batch.put_item(Item=item)
        print(f"Successfully stored {len(dynamodb_items)} players in DynamoDB.")
    except Exception as e:
        print(f"Error storing data in DynamoDB: {e}")

# ==============================================================================
# ESPN API INTERACTION AND DATA PROCESSING
# ==============================================================================

def get_available_players():
    """
    Fetches a list of all players and then filters for waivers/free agents.
    
    Returns:
        list: A list of dictionaries, where each dictionary represents a player.
              Returns an empty list on failure.
    """
    LEAGUE_ID = os.environ.get("LEAGUE_ID")
    SEASON_ID = os.environ.get("SEASON_ID")
    ESPN_S2 = os.environ.get("ESPN_S2")
    SWID = os.environ.get("SWID")

    print(f"Fetching all player data from ESPN API for league {LEAGUE_ID}, season {SEASON_ID}...")
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "X-Fantasy-Filter": json.dumps({
            "players": {
                "filterStatus": {
                    "value": ["FREEAGENT", "WAIVERS"]
                }
            }
        })
    }
    
    cookies = None
    if ESPN_S2 and SWID:
        cookies = {
            "espn_s2": ESPN_S2,
            "SWID": SWID
        }

    params = {
        "view": "kona_player_info"
    }
    
    API_URL = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON_ID}/players"

    try:
        response = requests.get(API_URL, headers=headers, params=params, cookies=cookies)
        text = json.loads(response.text)
        with open("output.json", "w") as file:
            json.dump(text, file, indent=4)

            file.close()
        response.raise_for_status()
        data = response.json()
        
        if "players" in data:
            print(f"Found {len(data['players'])} players from the API.")
            return data
        else:
            print("API response does not contain a 'players' key.")
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {e}")
        return []

def transform_player_data(player_data_list, season_id):
    """
    Transforms a list of raw player data into a clean list of DynamoDB items.
    It also filters out players that are not free agents or waivers.
    
    Args:
        player_data_list (list): A list of raw player data from the API.
        season_id (str): The current fantasy football season year.
        
    Returns:
        list: A list of dictionaries formatted for DynamoDB.
    """
    transformed_list = []
    
    # We now filter the players locally as requested.
    available_players = [
        player_entry for player_entry in player_data_list
        if player_entry.get("onTeamId") == 0
    ]

    print(f"Found {len(available_players)} available players after local filtering.")

    for player_entry in available_players:
        player_info = player_entry.get("player")
        if not player_info or not player_info.get("active"):
            continue

        weekly_projections = {}
        for stats in player_info.get("stats", []):
            if stats.get("statSourceId") == 1 and stats.get("seasonId") == int(season_id):
                week = str(stats.get("scoringPeriodId"))
                fantasy_points = stats.get("appliedTotal", 0)
                weekly_projections[week] = fantasy_points
                
        player_name = player_info.get("fullName", "Unknown Player")
        player_season_key = f"{player_name}#{season_id}"
        
        dynamodb_item = {
            "player_season": player_season_key,
            "player_name": player_name,
            "position": player_info.get("defaultPositionId"),
            "season": int(season_id),
            "team": player_info.get("proTeamId"),
            "updated_at": datetime.utcnow().isoformat(),
            "weekly_projections": weekly_projections
        }
        
        position_map = {
            0: "QB", 1: "P", 2: "RB", 3: "WR", 4: "TE", 5: "K", 6: "D/ST",
            7: "LB", 8: "DB", 9: "DL", 10: "IDP", 11: "OFFENSE", 12: "DEFENSE",
            13: "FLEX", 14: "D/ST", 15: "K", 16: "D/ST", 17: "K", 18: "K",
            19: "RB/WR/TE", 20: "IR", 21: "RB/WR/TE", 22: "RB/WR/TE", 23: "FLEX"
        }
        dynamodb_item["position"] = position_map.get(dynamodb_item["position"], "N/A")

        transformed_list.append(dynamodb_item)
        
    return transformed_list

# ==============================================================================
# AWS LAMBDA HANDLER
# ==============================================================================

def lambda_handler(event, context):
    load_environment_variables()
    
    LEAGUE_ID = os.environ.get("LEAGUE_ID")
    SEASON_ID = os.environ.get("SEASON_ID")
    PLAYER_TABLE_NAME = os.environ.get("PLAYER_TABLE_NAME")
    
    if not all([LEAGUE_ID, SEASON_ID, PLAYER_TABLE_NAME]):
        print("Missing required environment variables. Exiting.")
        return {
            "statusCode": 500,
            "body": json.dumps("Missing environment variables.")
        }
    
    print("Starting ESPN Fantasy Football waiver wire script.")
    
    raw_players = get_available_players()
    if not raw_players:
        print("No players found or an error occurred. Exiting.")
        return {
            "statusCode": 500,
            "body": json.dumps("Failed to retrieve player data.")
        }
    
    dynamodb_data = transform_player_data(raw_players, SEASON_ID)
    
    store_players_in_dynamodb(dynamodb_data, PLAYER_TABLE_NAME)
    
    print("Script finished.")
    
    return {
        "statusCode": 200,
        "body": json.dumps(f"Successfully processed and stored {len(dynamodb_data)} players.")
    }

if __name__ == "__main__":
    lambda_handler(None, None)
