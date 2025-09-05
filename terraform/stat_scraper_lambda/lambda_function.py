import json
import boto3
import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta
import re
from decimal import Decimal
import os
from typing import Dict, List, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'fantasy-football-2025-stats')
table = dynamodb.Table(table_name)

# Current season
CURRENT_SEASON = 2025

def lambda_handler(event, context):
    """
    Main Lambda handler function
    """
    try:
        logger.info("Starting fantasy stats collection...")
        
        # Get current week number
        current_week = get_current_nfl_week()
        logger.info(f"Processing week {current_week} stats")
        
        # Scrape stats for each position
        positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']
        total_players_processed = 0
        
        for position in positions:
            logger.info(f"Processing {position} stats...")
            players_data = scrape_fantasypros_stats(position, current_week)
            
            if players_data:
                batch_write_to_dynamodb(players_data)
                total_players_processed += len(players_data)
                logger.info(f"Processed {len(players_data)} {position} players")
            else:
                logger.warning(f"No data found for {position}")
        
        logger.info(f"Successfully processed {total_players_processed} total players")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully updated {total_players_processed} player stats for week {current_week}',
                'week': current_week,
                'season': CURRENT_SEASON
            })
        }
        
    except Exception as e:
        logger.error(f"Error in lambda_handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }

def get_current_nfl_week() -> int:
    """
    Calculate current NFL week based on the date
    NFL season typically starts first week of September
    """
    today = datetime.now()
    
    # NFL season 2025 started approximately September 4, 2025
    # Adjust this date based on actual NFL schedule
    season_start = datetime(2025, 9, 4)
    
    if today < season_start:
        return 1
    
    days_since_start = (today - season_start).days
    week = (days_since_start // 7) + 1
    
    # Cap at week 18 (regular season)
    return min(week, 18)

def scrape_fantasypros_stats(position: str, week: int) -> List[Dict]:
    """
    Scrape fantasy stats from FantasyPros for a specific position and week
    """
    try:
        # FantasyPros weekly stats URL pattern
        url = f"https://www.fantasypros.com/nfl/stats/{position.lower()}.php"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Add week parameter if not current week
        params = {}
        if week > 1:
            params['week'] = week
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the stats table - FantasyPros typically uses a table with class 'table'
        stats_table = soup.find('table', {'id': 'data'}) or soup.find('table', class_='table')
        
        if not stats_table:
            logger.warning(f"No stats table found for {position}")
            return []
        
        players_data = []
        rows = stats_table.find('tbody').find_all('tr') if stats_table.find('tbody') else stats_table.find_all('tr')[1:]
        
        for row in rows:
            try:
                player_data = parse_player_row(row, position, week)
                if player_data:
                    players_data.append(player_data)
            except Exception as e:
                logger.warning(f"Error parsing row for {position}: {str(e)}")
                continue
        
        return players_data
        
    except requests.RequestException as e:
        logger.error(f"Request error for {position}: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Error scraping {position} stats: {str(e)}")
        return []

def parse_player_row(row, position: str, week: int) -> Optional[Dict]:
    """
    Parse a single player row from the stats table
    """
    try:
        cells = row.find_all(['td', 'th'])
        
        if len(cells) < 3:
            return None
        
        # Extract player name and team (usually in first or second cell)
        player_cell = cells[0] if cells[0].get_text(strip=True) else cells[1]
        player_text = player_cell.get_text(strip=True)
        
        # Parse player name and team
        # Format is usually "Player Name (TEAM)" or "Player Name TEAM"
        player_match = re.match(r'^(.*?)\s*[\(\s]([A-Z]{2,4})[\)\s]*', player_text)
        
        if not player_match:
            # Fallback: assume entire text is player name
            player_name = player_text
            team = "UNK"
        else:
            player_name = player_match.group(1).strip()
            team = player_match.group(2).strip()
        
        # Find fantasy points column (usually last column or labeled "FPTS")
        fantasy_points = 0.0
        
        # Look for fantasy points in different possible columns
        for i, cell in enumerate(cells):
            cell_text = cell.get_text(strip=True)
            # Check if this cell contains fantasy points
            if re.match(r'^\d+\.?\d*$', cell_text):
                try:
                    points = float(cell_text)
                    # Fantasy points are usually the last numeric column or highest value
                    if i >= len(cells) - 3:  # One of the last few columns
                        fantasy_points = points
                except ValueError:
                    continue
        
        # Create player data object
        player_data = {
            'player_season': f"{player_name}#{CURRENT_SEASON}",
            'week': week,
            'fantasy_points': Decimal(str(fantasy_points)),
            'opponent': get_opponent_from_row(cells, team),
            'player_name': player_name,
            'position': position,
            'season': CURRENT_SEASON,
            'team': team,
            'updated_at': datetime.now().isoformat()
        }
        
        return player_data
        
    except Exception as e:
        logger.warning(f"Error parsing player row: {str(e)}")
        return None

def get_opponent_from_row(cells, team: str) -> str:
    """
    Extract opponent information from the row cells
    """
    try:
        # Look for opponent in cells (usually shows as "vs OPP" or "@OPP")
        for cell in cells:
            text = cell.get_text(strip=True)
            opponent_match = re.search(r'(?:vs|@)\s*([A-Z]{2,4})', text)
            if opponent_match:
                return opponent_match.group(1)
        
        # If no opponent found, return empty string
        return ""
        
    except:
        return ""

def batch_write_to_dynamodb(players_data: List[Dict]):
    """
    Write player data to DynamoDB in batches
    """
    try:
        # DynamoDB batch write limit is 25 items
        batch_size = 25
        
        for i in range(0, len(players_data), batch_size):
            batch = players_data[i:i + batch_size]
            
            with table.batch_writer() as batch_writer:
                for player_data in batch:
                    # Convert any float values to Decimal for DynamoDB
                    for key, value in player_data.items():
                        if isinstance(value, float):
                            player_data[key] = Decimal(str(value))
                    
                    batch_writer.put_item(Item=player_data)
            
            logger.info(f"Wrote batch of {len(batch)} items to DynamoDB")
            
    except Exception as e:
        logger.error(f"Error writing to DynamoDB: {str(e)}")
        raise

# Alternative scraping function using API if available
def scrape_with_api_fallback(position: str, week: int) -> List[Dict]:
    """
    Fallback method using alternative data sources or APIs
    This is a placeholder for potential API integration
    """
    # This could be implemented to use other fantasy football APIs
    # like ESPN, Yahoo, or paid services as fallback
    logger.info(f"Using API fallback for {position} week {week}")
    return []