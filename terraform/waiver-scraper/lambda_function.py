import os
import json
import requests
import boto3
from datetime import datetime
from decimal import Decimal
from bs4 import BeautifulSoup
import time
import re

# ==============================================================================
# DYNAMODB INTERACTION FUNCTIONS
# ==============================================================================

def get_dynamodb_resource():
    try:
        boto3.set_stream_logger(name='boto3', level=os.environ.get('BOTO3_LOG_LEVEL', 'ERROR'))
        boto3.set_stream_logger(name='botocore', level=os.environ.get('BOTO3_LOG_LEVEL', 'ERROR'))
        return boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-west-2"))
    except Exception as e:
        print(f"Error getting DynamoDB resource: {e}")
        return None

def convert_floats_to_decimal(obj):
    """
    Recursively converts float values to Decimal for DynamoDB compatibility.
    
    Args:
        obj: The object to convert (dict, list, or primitive)
        
    Returns:
        The object with floats converted to Decimals
    """
    if isinstance(obj, dict):
        return {key: convert_floats_to_decimal(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    elif isinstance(obj, float):
        # Convert float to Decimal, handling potential precision issues
        return Decimal(str(obj))
    else:
        return obj

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
                # Convert floats to Decimals for DynamoDB compatibility
                converted_item = convert_floats_to_decimal(item)
                batch.put_item(Item=converted_item)
        print(f"Successfully stored {len(dynamodb_items)} players in DynamoDB.")
    except Exception as e:
        print(f"Error storing data in DynamoDB: {e}")

# ==============================================================================
# FANTASYPROS SCRAPING FUNCTIONS
# ==============================================================================

def normalize_team_name(team_name):
    """
    Normalize team names to match ESPN format.
    """
    team_mapping = {
        # FantasyPros -> ESPN format
        'ARI': 'ARI', 'ATL': 'ATL', 'BAL': 'BAL', 'BUF': 'BUF', 'CAR': 'CAR',
        'CHI': 'CHI', 'CIN': 'CIN', 'CLE': 'CLE', 'DAL': 'DAL', 'DEN': 'DEN',
        'DET': 'DET', 'GB': 'GB', 'HOU': 'HOU', 'IND': 'IND', 'JAX': 'JAX',
        'KC': 'KC', 'LV': 'LV', 'LAC': 'LAC', 'LAR': 'LAR', 'MIA': 'MIA',
        'MIN': 'MIN', 'NE': 'NE', 'NO': 'NO', 'NYG': 'NYG', 'NYJ': 'NYJ',
        'PHI': 'PHI', 'PIT': 'PIT', 'SF': 'SF', 'SEA': 'SEA', 'TB': 'TB',
        'TEN': 'TEN', 'WAS': 'WAS',
        # Handle common variations
        'LAS': 'LV', 'WSH': 'WAS', 'GNB': 'GB'
    }
    return team_mapping.get(team_name.upper(), team_name.upper())

def normalize_player_name(player_name, position):
    """
    Normalize player names to match ESPN format.
    """
    # Handle D/ST names
    if position == "D/ST":
        # Convert "Cardinals" -> "Cardinals D/ST"
        if not player_name.endswith(" D/ST"):
            player_name = f"{player_name} D/ST"
    
    # Remove extra whitespace
    player_name = " ".join(player_name.split())
    
    return player_name

def get_fantasypros_projections(position, week, max_retries=3):
    """
    Scrape FantasyPros projections for a given position and week.
    
    Args:
        position (str): Position code (qb, rb, wr, te, k, dst)
        week (int): Week number (1-18)
        max_retries (int): Maximum number of retry attempts
        
    Returns:
        dict: Dictionary with player names as keys and projected points as values
    """
    position_map = {
        "QB": "qb",
        "RB": "rb", 
        "WR": "wr",
        "TE": "te",
        "K": "k",
        "D/ST": "dst"
    }
    
    fp_position = position_map.get(position)
    if not fp_position:
        print(f"Unknown position: {position}")
        return {}
    
    url = f"https://www.fantasypros.com/nfl/projections/{fp_position}.php?week={week}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    for attempt in range(max_retries):
        try:
            print(f"Fetching {position} projections for week {week} (attempt {attempt + 1})")
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            projections = {}
            
            # Find the projection table
            table = soup.find('table', {'id': 'data'})
            if not table:
                print(f"Could not find projection table for {position} week {week}")
                return {}
            
            tbody = table.find('tbody')
            if not tbody:
                print(f"Could not find table body for {position} week {week}")
                return {}
            
            rows = tbody.find_all('tr')
            
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                
                # Extract player name (usually first cell)
                player_cell = cells[0]
                player_link = player_cell.find('a')
                if player_link:
                    player_name = player_link.get_text(strip=True)
                else:
                    player_name = player_cell.get_text(strip=True)
                
                if not player_name:
                    continue
                
                # Find fantasy points column (usually last column)
                fantasy_points = None
                
                # Look for fantasy points in the last few columns
                for cell in reversed(cells[-3:]):
                    cell_text = cell.get_text(strip=True)
                    try:
                        # Try to parse as float
                        points = float(cell_text)
                        if 0 <= points <= 100:  # Reasonable range for fantasy points
                            fantasy_points = points
                            break
                    except (ValueError, TypeError):
                        continue
                
                if fantasy_points is not None:
                    normalized_name = normalize_player_name(player_name, position)
                    projections[normalized_name] = fantasy_points
                    
            print(f"Successfully scraped {len(projections)} {position} projections for week {week}")
            return projections
            
        except requests.exceptions.RequestException as e:
            print(f"Request error for {position} week {week} (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
        except Exception as e:
            print(f"Parsing error for {position} week {week} (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
        
        break
    
    print(f"Failed to get projections for {position} week {week} after {max_retries} attempts")
    return {}

def get_all_weekly_projections(position, weeks_to_fetch=None):
    """
    Get projections for all weeks for a given position.
    
    Args:
        position (str): Position (QB, RB, WR, TE, K, D/ST)
        weeks_to_fetch (list): List of week numbers to fetch. If None, fetches 1-18
        
    Returns:
        dict: Nested dictionary {player_name: {week: projected_points}}
    """
    if weeks_to_fetch is None:
        weeks_to_fetch = list(range(1, 19))  # Weeks 1-18
    
    all_projections = {}
    
    for week in weeks_to_fetch:
        week_projections = get_fantasypros_projections(position, week)
        
        for player_name, points in week_projections.items():
            if player_name not in all_projections:
                all_projections[player_name] = {}
            all_projections[player_name][str(week)] = Decimal(str(round(points, 2)))
        
        # Be respectful to the server
        time.sleep(1)
    
    return all_projections

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
                },
                "limit": 2000,
                "sortPercOwned": {
                    "sortAsc": False,
                    "sortPriority": 1
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
        response.raise_for_status()
        data = response.json()
        
        print(f"Found {len(data)} players from the API.")
        return data
            
    except requests.exceptions.RequestException as e:
        print(f"Error during API request: {e}")
        return []

def get_team_name(pro_team_id):
    """
    Maps ESPN pro team IDs to team abbreviations.
    """
    team_map = {
        1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN", 8: "DET",
        9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV", 14: "LAR", 15: "MIA", 16: "MIN",
        17: "NE", 18: "NO", 19: "NYG", 20: "NYJ", 21: "PHI", 22: "ARI", 23: "PIT", 24: "LAC",
        25: "SF", 26: "SEA", 27: "TB", 28: "WAS", 29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU"
    }
    return team_map.get(pro_team_id, "FA")

def get_position_name(position_id):
    """
    Maps ESPN position IDs to position abbreviations.
    """
    position_map = {
        0: "QB", 1: "TQB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 
        16: "D/ST", 17: "K", 23: "FLEX"
    }
    return position_map.get(position_id, "UNKNOWN")

def match_fantasypros_projection(player_name, position, fantasypros_data):
    """
    Try to match ESPN player name with FantasyPros projections.
    
    Args:
        player_name (str): Player name from ESPN
        position (str): Player position
        fantasypros_data (dict): FantasyPros projection data
        
    Returns:
        dict: Weekly projections for the player
    """
    # Direct match first
    if player_name in fantasypros_data:
        return fantasypros_data[player_name]
    
    # Try various name matching strategies
    normalized_name = normalize_player_name(player_name, position)
    if normalized_name in fantasypros_data:
        return fantasypros_data[normalized_name]
    
    # For D/ST, try team-based matching
    if position == "D/ST":
        # Extract team name from ESPN format
        for team_abbr in ["ATL", "BUF", "CHI", "CIN", "CLE", "DAL", "DEN", "DET",
                         "GB", "TEN", "IND", "KC", "LV", "LAR", "MIA", "MIN",
                         "NE", "NO", "NYG", "NYJ", "PHI", "ARI", "PIT", "LAC",
                         "SF", "SEA", "TB", "WAS", "CAR", "JAX", "BAL", "HOU"]:
            if team_abbr in player_name:
                # Try different D/ST name formats
                variations = [
                    f"{team_abbr} D/ST",
                    f"{team_abbr}",
                ]
                
                for variation in variations:
                    if variation in fantasypros_data:
                        return fantasypros_data[variation]
    
    # Try fuzzy matching for regular players (simplified)
    player_name_lower = player_name.lower()
    for fp_name in fantasypros_data.keys():
        if player_name_lower in fp_name.lower() or fp_name.lower() in player_name_lower:
            return fantasypros_data[fp_name]
    
    return {}

def transform_player_data(players_list, season_id, fantasypros_projections):
    """
    Transforms a list of raw player data into a clean list of DynamoDB items.
    Now includes FantasyPros projections.
    
    Args:
        players_list (list): A list of raw player data from the API.
        season_id (str): The current fantasy football season year.
        fantasypros_projections (dict): FantasyPros projections by position
        
    Returns:
        list: A list of dictionaries formatted for DynamoDB.
    """
    transformed_list = []
    
    print(f"Processing {len(players_list)} players...")

    for player_entry in players_list:
        # Check if player is available (not on a team)
        on_team_id = player_entry.get("onTeamId", 0)
        if on_team_id != 0:  # Player is on a team, skip
            continue
            
        # Extract player info
        player_info = player_entry
        
        # Skip inactive players
        if not player_info.get("active", False):
            continue
            
        # Skip players without required data
        full_name = player_info.get("fullName")
        if not full_name:
            continue
        
        # Extract basic player information
        player_name = full_name
        position_id = player_info.get("defaultPositionId", 0)
        position = get_position_name(position_id)
        pro_team_id = player_info.get("proTeamId", 0)
        team = get_team_name(pro_team_id)
        
        # Skip certain positions if desired (like kickers, defense)
        skip_positions = []  # Add positions to skip, e.g., ["K", "D/ST"]
        if position in skip_positions:
            continue
        
        # Get FantasyPros projections for this player
        weekly_projections = {}
        if position in fantasypros_projections:
            weekly_projections = match_fantasypros_projection(
                player_name, position, fantasypros_projections[position]
            )
        
        # Extract ownership data for filtering
        ownership = player_info.get("ownership", {})
        percent_owned = ownership.get("percentOwned", 0)
        
        # Create primary key matching your stat table format
        player_season_key = f"{player_name}#{season_id}"
        
        # Create DynamoDB item
        dynamodb_item = {
            "player_season": player_season_key,
            "player_name": player_name,
            "position": position,
            "season": int(season_id),
            "team": team,
            "updated_at": datetime.utcnow().isoformat(),
            "weekly_projections": weekly_projections,
            "percent_owned": Decimal(str(round(percent_owned, 2))),
            "pro_team_id": pro_team_id,
            "espn_player_id": player_info.get("id"),
            "injury_status": player_info.get("injuryStatus", "ACTIVE"),
            "jersey_number": player_info.get("jersey", "")
        }
        
        # Add season outlook if available
        outlooks = player_info.get("outlooks", {})
        season_outlook = outlooks.get("seasonOutlook")
        if season_outlook:
            dynamodb_item["season_outlook"] = season_outlook
        
        # Add weekly outlook for current week if available
        outlooks_by_week = outlooks.get("outlooksByWeek", {})
        if outlooks_by_week:
            dynamodb_item["weekly_outlooks"] = outlooks_by_week
        
        transformed_list.append(dynamodb_item)
        
    print(f"Transformed {len(transformed_list)} available players for DynamoDB.")
    return transformed_list

def filter_relevant_players(transformed_players):
    """
    Additional filtering to keep only the most relevant players.
    
    Args:
        transformed_players (list): List of transformed player dictionaries
        
    Returns:
        list: Filtered list of players
    """
    filtered_players = []
    
    for player in transformed_players:
        # Filter criteria - adjust as needed
        position = player.get("position", "")
        percent_owned = player.get("percent_owned", Decimal('0'))
        weekly_projections = player.get("weekly_projections", {})
            
        # Keep players with some ownership or projections
        has_projections = len(weekly_projections) > 0
        has_ownership = percent_owned > Decimal('0.5')
        
        # Keep skill position players with minimal activity
        skill_positions = ["QB", "RB", "WR", "TE"]
        if position in skill_positions and (has_projections or has_ownership):
            filtered_players.append(player)
        # Keep D/ST with some ownership
        elif position == "D/ST" and (has_ownership or has_projections):
            filtered_players.append(player)
    
    print(f"Filtered down to {len(filtered_players)} relevant players.")
    return filtered_players

# ==============================================================================
# AWS LAMBDA HANDLER
# ==============================================================================

def lambda_handler(event, context):
    LEAGUE_ID = os.environ.get("LEAGUE_ID")
    SEASON_ID = os.environ.get("SEASON_ID")
    PLAYER_TABLE_NAME = os.environ.get("PLAYER_TABLE_NAME")
    
    if not all([LEAGUE_ID, SEASON_ID, PLAYER_TABLE_NAME]):
        print("Missing required environment variables. Exiting.")
        return {
            "statusCode": 500,
            "body": json.dumps("Missing environment variables.")
        }
    
    print("Starting ESPN Fantasy Football waiver wire script with FantasyPros projections.")
    
    # Get FantasyPros projections for all positions
    print("Fetching FantasyPros projections...")
    fantasypros_projections = {}
    
    positions_to_fetch = ["QB", "RB", "WR", "TE", "D/ST"]  # Add "K" if needed
    
    # Determine which weeks to fetch (you may want to make this configurable)
    current_week = int(os.environ.get("CURRENT_WEEK", "1"))
    weeks_ahead = int(os.environ.get("WEEKS_AHEAD", "17"))  # How many weeks ahead to project
    weeks_to_fetch = list(range(current_week, min(current_week + weeks_ahead, 19)))
    
    for position in positions_to_fetch:
        try:
            projections = get_all_weekly_projections(position, weeks_to_fetch)
            fantasypros_projections[position] = projections
            print(f"Fetched projections for {len(projections)} {position} players")
        except Exception as e:
            print(f"Error fetching {position} projections: {e}")
            fantasypros_projections[position] = {}
        
        # Small delay between position fetches
        time.sleep(2)
    
    # Get raw player data from ESPN
    raw_players = get_available_players()
    if not raw_players:
        print("No players found or an error occurred. Exiting.")
        return {
            "statusCode": 500,
            "body": json.dumps("Failed to retrieve player data.")
        }
    
    # Transform the data with FantasyPros projections
    transformed_players = transform_player_data(raw_players, SEASON_ID, fantasypros_projections)
    
    # Filter to most relevant players
    filtered_players = filter_relevant_players(transformed_players)
    
    if not filtered_players:
        print("No relevant players found after filtering.")
        return {
            "statusCode": 200,
            "body": json.dumps("No relevant players to store.")
        }
    print(filtered_players)
    # Store in DynamoDB
    store_players_in_dynamodb(filtered_players, PLAYER_TABLE_NAME)
    
    print("Script finished.")
    
    return {
        "statusCode": 200,
        "body": json.dumps(f"Successfully processed and stored {len(filtered_players)} players with FantasyPros projections.")
    }