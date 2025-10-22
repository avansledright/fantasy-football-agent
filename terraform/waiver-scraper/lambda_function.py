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

def get_rostered_players(roster_table_name):
    """
    Fetches all team rosters and returns a set of rostered player names.
    
    Args:
        roster_table_name (str): Name of the DynamoDB table containing team rosters
        
    Returns:
        set: Set of player names that are currently rostered
    """
    dynamodb = get_dynamodb_resource()
    if not dynamodb:
        print("Could not get DynamoDB resource for roster data.")
        return set()

    table = dynamodb.Table(roster_table_name)
    rostered_players = set()
    
    try:
        print(f"Fetching team rosters from table '{roster_table_name}'...")
        
        # Scan the entire table to get all teams
        response = table.scan()
        
        while True:
            # Process items from current page
            for team_item in response.get('Items', []):
                players = team_item.get('players', [])
                
                for player in players:
                    player_name = player.get('name')
                    if player_name:
                        # Normalize player name for consistent matching
                        normalized_name = normalize_rostered_player_name(player_name)
                        rostered_players.add(normalized_name)
            
            # Check if there are more pages
            if 'LastEvaluatedKey' not in response:
                break
                
            # Get next page
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        
        print(f"Found {len(rostered_players)} rostered players across all teams.")
        return rostered_players
        
    except Exception as e:
        print(f"Error fetching roster data: {e}")
        return set()

def normalize_rostered_player_name(player_name):
    """
    Normalize rostered player names for consistent matching with waiver players.
    
    Args:
        player_name (str): Player name from roster data
        
    Returns:
        str: Normalized player name
    """
    # Remove extra whitespace
    name = " ".join(player_name.split())
    
    # Handle D/ST names - remove #DST suffix if present
    if name.endswith("#DST"):
        name = name.replace("#DST", "")
    
    # Handle D/ST variations
    if " D/ST" in name:
        name = name.replace(" D/ST", "")
    
    # Convert to lowercase for case-insensitive matching
    return name.lower().strip()

def is_player_rostered(player_name, position, rostered_players):
    """
    Check if a player is already rostered by comparing against the rostered players set.
    
    Args:
        player_name (str): Player name from waiver wire
        position (str): Player position
        rostered_players (set): Set of normalized rostered player names
        
    Returns:
        bool: True if player is already rostered, False otherwise
    """
    # Normalize the waiver player name
    normalized_name = normalize_rostered_player_name(player_name)
    
    # Direct match
    if normalized_name in rostered_players:
        return True
    
    # For D/ST, try different variations
    if position == "D/ST":
        # Try just the team name without D/ST
        team_name_only = normalized_name.replace(" d/st", "").replace("#dst", "").strip()
        if team_name_only in rostered_players:
            return True
        
        # Try with team abbreviations for D/ST
        for team_abbr in ["ATL", "BUF", "CHI", "CIN", "CLE", "DAL", "DEN", "DET",
                         "GB", "TEN", "IND", "KC", "LV", "LAR", "MIA", "MIN",
                         "NE", "NO", "NYG", "NYJ", "PHI", "ARI", "PIT", "LAC",
                         "SF", "SEA", "TB", "WAS", "CAR", "JAX", "BAL", "HOU"]:
            if team_abbr.lower() in normalized_name:
                # Check if this team's D/ST is rostered
                dst_variations = [
                    f"{team_abbr.lower()}",
                    f"{team_abbr.lower()} d/st",
                    f"{team_abbr.lower()}#dst"
                ]
                for variation in dst_variations:
                    if variation in rostered_players:
                        return True
    
    return False

def update_player_in_dynamodb(player_data, table_name, season_id):
    """
    Updates a single player record in DynamoDB using the new consolidated structure.
    Uses UPDATE expression to merge data into seasons.{year}.* instead of overwriting.
    
    Args:
        player_data (dict): Player data to update
        table_name (str): DynamoDB table name
        season_id (str): Current season year
    """
    dynamodb = get_dynamodb_resource()
    if not dynamodb:
        print("Could not get DynamoDB resource.")
        return False

    table = dynamodb.Table(table_name)
    
    try:
        player_id = player_data['player_id']
        
        # Build update expression for nested season data
        update_expression_parts = []
        expression_attribute_names = {}
        expression_attribute_values = {}
        
        # Set root-level fields (only if creating new record)
        update_expression_parts.append("SET #player_name = if_not_exists(#player_name, :player_name)")
        update_expression_parts.append("#position = if_not_exists(#position, :position)")
        update_expression_parts.append("#updated_at = :updated_at")
        
        expression_attribute_names['#player_name'] = 'player_name'
        expression_attribute_names['#position'] = 'position'
        expression_attribute_names['#updated_at'] = 'updated_at'
        
        expression_attribute_values[':player_name'] = player_data['player_name']
        expression_attribute_values[':position'] = player_data['position']
        expression_attribute_values[':updated_at'] = player_data['updated_at']
        
        # Add ESPN player ID if present
        if 'espn_player_id' in player_data:
            update_expression_parts.append("#espn_player_id = if_not_exists(#espn_player_id, :espn_player_id)")
            expression_attribute_names['#espn_player_id'] = 'espn_player_id'
            expression_attribute_values[':espn_player_id'] = player_data['espn_player_id']
        
        # Update season-specific data under seasons.{year}
        season_path = f"#seasons.#{season_id}"
        expression_attribute_names['#seasons'] = 'seasons'
        expression_attribute_names[f'#{season_id}'] = season_id
        
        # Team info
        if 'team' in player_data:
            update_expression_parts.append(f"{season_path}.#team = :team")
            expression_attribute_names['#team'] = 'team'
            expression_attribute_values[':team'] = player_data['team']
        
        if 'pro_team_id' in player_data:
            update_expression_parts.append(f"{season_path}.#pro_team_id = :pro_team_id")
            expression_attribute_names['#pro_team_id'] = 'pro_team_id'
            expression_attribute_values[':pro_team_id'] = player_data['pro_team_id']
        
        if 'jersey_number' in player_data:
            update_expression_parts.append(f"{season_path}.#jersey_number = :jersey_number")
            expression_attribute_names['#jersey_number'] = 'jersey_number'
            expression_attribute_values[':jersey_number'] = player_data['jersey_number']
        
        # Injury status
        if 'injury_status' in player_data:
            update_expression_parts.append(f"{season_path}.#injury_status = :injury_status")
            expression_attribute_names['#injury_status'] = 'injury_status'
            expression_attribute_values[':injury_status'] = player_data['injury_status']
        
        # Ownership percentage
        if 'percent_owned' in player_data:
            update_expression_parts.append(f"{season_path}.#percent_owned = :percent_owned")
            expression_attribute_names['#percent_owned'] = 'percent_owned'
            expression_attribute_values[':percent_owned'] = player_data['percent_owned']
        
        # Weekly projections
        if 'weekly_projections' in player_data and player_data['weekly_projections']:
            update_expression_parts.append(f"{season_path}.#weekly_projections = :weekly_projections")
            expression_attribute_names['#weekly_projections'] = 'weekly_projections'
            expression_attribute_values[':weekly_projections'] = player_data['weekly_projections']
        
        # Weekly outlooks
        if 'weekly_outlooks' in player_data and player_data['weekly_outlooks']:
            update_expression_parts.append(f"{season_path}.#weekly_outlooks = :weekly_outlooks")
            expression_attribute_names['#weekly_outlooks'] = 'weekly_outlooks'
            expression_attribute_values[':weekly_outlooks'] = player_data['weekly_outlooks']
        
        # Season outlook (if present)
        if 'season_outlook' in player_data:
            update_expression_parts.append(f"{season_path}.#season_outlook = :season_outlook")
            expression_attribute_names['#season_outlook'] = 'season_outlook'
            expression_attribute_values[':season_outlook'] = player_data['season_outlook']
        
        # Combine all update expression parts
        update_expression = ", ".join(update_expression_parts)
        
        # Execute update
        table.update_item(
            Key={'player_id': player_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values
        )
        
        return True
        
    except Exception as e:
        print(f"Error updating player {player_data.get('player_id', 'unknown')}: {e}")
        return False

def store_players_in_dynamodb(dynamodb_items, table_name, season_id):
    """
    Stores players in DynamoDB using the new consolidated structure.
    Uses UPDATE operations to merge with existing data.
    
    Args:
        dynamodb_items (list): List of player data dictionaries
        table_name (str): DynamoDB table name
        season_id (str): Current season year
    """
    print(f"Starting updates to DynamoDB table '{table_name}'.")
    
    success_count = 0
    error_count = 0
    
    for item in dynamodb_items:
        # Convert floats to Decimals for DynamoDB compatibility
        converted_item = convert_floats_to_decimal(item)
        
        if update_player_in_dynamodb(converted_item, table_name, season_id):
            success_count += 1
        else:
            error_count += 1
        
        # Small delay to avoid throttling
        if (success_count + error_count) % 25 == 0:
            time.sleep(0.1)
    
    print(f"Successfully updated {success_count} players in DynamoDB.")
    if error_count > 0:
        print(f"Failed to update {error_count} players.")

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
    
    url = f"https://www.fantasypros.com/nfl/projections/{fp_position}.php?week={week}&scoring=PPR"
    
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
        weeks_to_fetch = list(range(7, 19))  # Weeks 1-18
    
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
        0: "QB", 1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 
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

def transform_player_data(players_list, season_id, fantasypros_projections, rostered_players):
    """
    Transforms a list of raw player data into a clean list of DynamoDB items.
    Now uses the new consolidated table structure with player_id format.
    
    Args:
        players_list (list): A list of raw player data from the API.
        season_id (str): The current fantasy football season year.
        fantasypros_projections (dict): FantasyPros projections by position
        rostered_players (set): Set of rostered player names to exclude
        
    Returns:
        list: A list of dictionaries formatted for DynamoDB.
    """
    transformed_list = []
    rostered_count = 0
    
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
        
        # Check if player is already rostered - SKIP if they are
        if is_player_rostered(player_name, position, rostered_players):
            rostered_count += 1
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
        
        # Create player_id in the format "Player Name#Position"
        player_id = f"{player_name}#{position}"
        
        # Create DynamoDB item for new consolidated structure
        dynamodb_item = {
            "player_id": player_id,
            "player_name": player_name,
            "position": position,
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
    print(f"Filtered out {rostered_count} players who are already rostered.")
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
        has_ownership = percent_owned > Decimal('0.6')
        
        # Keep skill position players with minimal activity
        skill_positions = ["QB", "RB", "WR", "TE", "K"]
        if position == "QB" or position == "TQB":
            print(f"Adding QB {position} to the list of players.")
            filtered_players.append(player)
        elif position in skill_positions and (has_projections or has_ownership):
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
    ROSTER_TABLE_NAME = os.environ.get("ROSTER_TABLE_NAME")
    
    if not all([LEAGUE_ID, SEASON_ID, PLAYER_TABLE_NAME, ROSTER_TABLE_NAME]):
        print("Missing required environment variables. Exiting.")
        return {
            "statusCode": 500,
            "body": json.dumps("Missing environment variables.")
        }
    
    print("Starting ESPN Fantasy Football waiver wire script with FantasyPros projections and roster filtering.")
    print(f"Writing to consolidated table: {PLAYER_TABLE_NAME}")
    print(f"Season data will be stored under seasons.{SEASON_ID}")
    
    # Get rostered players to filter out
    print("Fetching current team rosters...")
    rostered_players = get_rostered_players(ROSTER_TABLE_NAME)
    if not rostered_players:
        print("Warning: No rostered players found. Continuing without roster filtering.")
    
    # Get FantasyPros projections for all positions
    print("Fetching FantasyPros projections...")
    fantasypros_projections = {}
    
    positions_to_fetch = ["QB", "RB", "WR", "TE", "D/ST", "K"]
    
    # Determine which weeks to fetch (you may want to make this configurable)
    current_week = int(os.environ.get("CURRENT_WEEK", "7"))
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
    
    # Transform the data with FantasyPros projections and roster filtering
    transformed_players = transform_player_data(raw_players, SEASON_ID, fantasypros_projections, rostered_players)
    
    # Filter to most relevant players
    filtered_players = filter_relevant_players(transformed_players)
    
    if not filtered_players:
        print("No relevant players found after filtering.")
        return {
            "statusCode": 200,
            "body": json.dumps("No relevant players to store.")
        }
    
    # Store in DynamoDB using UPDATE operations to merge with existing data
    store_players_in_dynamodb(filtered_players, PLAYER_TABLE_NAME, SEASON_ID)
    
    print("Script finished.")
    
    return {
        "statusCode": 200,
        "body": json.dumps(f"Successfully processed and updated {len(filtered_players)} players in consolidated table (filtered out rostered players).")
    }