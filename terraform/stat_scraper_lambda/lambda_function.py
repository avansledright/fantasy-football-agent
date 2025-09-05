import json
import boto3
import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta
import re
from decimal import Decimal, InvalidOperation
import os
from typing import Dict, List, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Try to import schedule/bye info from nfl_schedule.py (user-provided)
try:
    from nfl_schedule import matchups_by_week, bye_weeks
except Exception as e:
    logger.warning("Could not import nfl_schedule.py (opponent lookup & bye weeks disabled): %s", e)
    matchups_by_week = {}
    bye_weeks = {}

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'fantasy-football-2025-stats')
table = dynamodb.Table(table_name)

# Current season
CURRENT_SEASON = 2025


def lambda_handler(event, context):
    """
    Main Lambda handler function
    Accepts optional 'week' in event to override the calculated week (for testing/manual runs).
    """
    try:
        logger.info("Starting fantasy stats collection...")

        # Allow test event to override week
        if isinstance(event, dict) and event.get("week"):
            current_week = int(event.get("week"))
            logger.info(f"Week override from event: {current_week}")
        else:
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
        logger.error(f"Error in lambda_handler: {str(e)}", exc_info=True)
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
    # Adjust this date based on actual NFL schedule if needed
    season_start = datetime(2025, 9, 4)

    if today < season_start:
        return 1

    days_since_start = (today - season_start).days
    week = (days_since_start // 7) + 1

    # Cap at week 18 (regular season)
    return min(week, 18)


def scrape_fantasypros_stats(position: str, week: int) -> List[Dict]:
    """
    Scrape fantasy stats from FantasyPros for a specific position and week (PPR scoring).
    This function detects the header row and uses header indices to find PLAYER and FPTS columns.
    """
    try:
        url = f"https://www.fantasypros.com/nfl/stats/{position.lower()}.php"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Always include week and PPR scoring
        params = {
            'week': week,
            'scoring': 'PPR'
        }

        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Find the stats table - FantasyPros typically has <table id="data">
        stats_table = soup.find('table', {'id': 'data'}) or soup.find('table', class_='table')

        if not stats_table:
            logger.warning(f"No stats table found for {position} week {week} at {url} with params {params}")
            return []

        # Get the last header row (handles multi-row grouped headers)
        thead = stats_table.find('thead')
        if not thead:
            logger.warning("No thead found in stats table")
            return []

        header_rows = thead.find_all('tr')
        if not header_rows:
            logger.warning("No header rows found in thead")
            return []

        header_cells = header_rows[-1].find_all(['th', 'td'])
        headers = [hc.get_text(strip=True).upper() for hc in header_cells]

        # Build index map for headers
        header_index = {h: i for i, h in enumerate(headers)}

        # Helper to find header index by name or substring
        def find_header_index(targets):
            for t in targets:
                for h, idx in header_index.items():
                    if h == t or h.startswith(t):
                        return idx
            return None

        player_idx = find_header_index(['PLAYER', 'TEAM'])  # sometimes labelled differently
        fpts_idx = find_header_index(['FPTS'])  # prefer exact FPTS
        if fpts_idx is None:
            # fallback to FPTS/G or last numeric column
            fpts_idx = find_header_index(['FPTS/G']) or (len(headers) - 1)

        # Get table body rows
        tbody = stats_table.find('tbody')
        rows = tbody.find_all('tr') if tbody else stats_table.find_all('tr')[1:]

        players_data = []

        for row in rows:
            try:
                player_data = parse_player_row(row, position, week, player_idx, fpts_idx)
                if not player_data:
                    continue

                # Normalize team to uppercase abbreviation
                team = (player_data.get('team') or "UNK").upper()
                player_data['team'] = team

                # 1) Skip players on bye week
                if team in bye_weeks and int(bye_weeks[team]) == int(week):
                    logger.info(f"Skipping {player_data.get('player_name')} ({team}) - bye week {week}")
                    continue

                # 2) Populate opponent using matchups_by_week when possible
                opponent = resolve_opponent_from_schedule(team, week)
                if opponent:
                    player_data['opponent'] = opponent
                else:
                    # keep previous parsing attempt if available, or empty string
                    player_data['opponent'] = player_data.get('opponent', "")

                players_data.append(player_data)
            except Exception as e:
                logger.warning(f"Error parsing row for {position}: {str(e)}", exc_info=True)
                continue

        return players_data

    except requests.RequestException as e:
        logger.error(f"Request error for {position}: {str(e)}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error scraping {position} stats: {str(e)}", exc_info=True)
        return []


def resolve_opponent_from_schedule(team: str, week: int) -> str:
    """
    Given an uppercase team abbreviation and week, return the opponent abbreviation
    using matchups_by_week structure. matchups_by_week expected to be {week: {away: home, ...}, ...}
    """
    try:
        if not matchups_by_week:
            return ""
        week_map = matchups_by_week.get(int(week), {})
        if not week_map:
            return ""
        # week_map is likely mapping away -> home
        # if team is away
        if team in week_map:
            return week_map[team].upper()
        # if team is home, find the away team whose value == team
        for away_team, home_team in week_map.items():
            if (home_team or "").upper() == team:
                return away_team.upper()
        return ""
    except Exception as e:
        logger.warning(f"Error resolving opponent from schedule for {team} week {week}: {e}")
        return ""


def parse_player_row(row, position: str, week: int, player_idx: Optional[int], fpts_idx: Optional[int]) -> Optional[Dict]:
    """
    Parse a single player row from the stats table using header indices.
    Returns dict with 'player_season', 'week', 'fantasy_points', 'opponent', 'player_name', 'position', 'season', 'team', 'updated_at'
    """
    try:
        cells = row.find_all(['td', 'th'])
        if not cells:
            return None

        # If header indices missing, fallback with safe defaults
        if player_idx is None:
            # try to find a link with player text in row
            player_cell_text = row.get_text(" ", strip=True)
        else:
            if player_idx >= len(cells):
                player_cell_text = cells[-1].get_text(strip=True)
            else:
                player_cell_text = cells[player_idx].get_text(" ", strip=True)

        # Player name and team extraction -- examples:
        # "Javonte Williams (DAL)" or "Saquon Barkley (PHI)" or "Buffalo Bills (BUF)" for DST
        player_name = player_cell_text
        team = "UNK"

        # Try common patterns
        m = re.match(r'^(.*?)\s*\((\w{2,4})\)\s*$', player_cell_text)
        if m:
            player_name = m.group(1).strip()
            team = m.group(2).strip()
        else:
            # Sometimes player cell is "Javonte Williams DAL" or "Buffalo Bills BUF"
            m2 = re.match(r'^(.*?)[\s,]+([A-Z]{2,4})$', player_cell_text)
            if m2:
                player_name = m2.group(1).strip()
                team = m2.group(2).strip()
            else:
                # For rows that include rank at front "1. Javonte Williams (DAL)"
                m3 = re.search(r'(\w.*?)(?:\s*\((\w{2,4})\))?$', player_cell_text)
                if m3:
                    player_name = m3.group(1).strip()
                    if m3.group(2):
                        team = m3.group(2).strip()

        # For DST ensure naming like "BUF DST"
        if position == "DST":
            # If team is known, create DST name
            if team != "UNK":
                player_name = f"{team} DST"
            else:
                # fallback: use whatever we parsed
                player_name = f"{player_name} DST"

        # Extract fantasy points from fpts_idx
        fantasy_points = Decimal('0')
        if fpts_idx is not None and fpts_idx < len(cells):
            fpts_text = cells[fpts_idx].get_text(strip=True).replace(',', '')
            try:
                if fpts_text == '':
                    fantasy_points = Decimal('0')
                else:
                    fantasy_points = Decimal(str(float(fpts_text)))
            except (ValueError, InvalidOperation):
                # fallback: scan cells for a numeric-looking value
                for c in reversed(cells):
                    txt = c.get_text(strip=True).replace(',', '')
                    if re.match(r'^\d+(\.\d+)?$', txt):
                        try:
                            fantasy_points = Decimal(str(float(txt)))
                            break
                        except (ValueError, InvalidOperation):
                            continue
        else:
            # fallback: scan last few columns
            for c in reversed(cells):
                txt = c.get_text(strip=True).replace(',', '')
                if re.match(r'^\d+(\.\d+)?$', txt):
                    try:
                        fantasy_points = Decimal(str(float(txt)))
                        break
                    except (ValueError, InvalidOperation):
                        continue

        # Build player data
        player_data = {
            'player_season': f"{player_name}#{CURRENT_SEASON}",
            'week': int(week),
            'fantasy_points': fantasy_points,
            'opponent': get_opponent_from_row(cells, team),  # may be empty; will be overwritten by schedule lookup if available
            'player_name': player_name,
            'position': position,
            'season': int(CURRENT_SEASON),
            'team': team,
            'updated_at': datetime.now().isoformat()
        }

        return player_data

    except Exception as e:
        logger.warning(f"Error parsing player row ({position}): {str(e)}", exc_info=True)
        return None


def get_opponent_from_row(cells, team: str) -> str:
    """
    Attempt to extract opponent from cells if present (looks for 'vs' or '@' followed by team abbr)
    If not found, returns empty string.
    """
    try:
        for cell in cells:
            text = cell.get_text(" ", strip=True)
            m = re.search(r'(?:vs|@)\s*([A-Z]{2,4})', text, flags=re.IGNORECASE)
            if m:
                return m.group(1).upper()
        return ""
    except:
        return ""


def batch_write_to_dynamodb(players_data: List[Dict]):
    """
    Write player data to DynamoDB in batches (25 item batch limit).
    Ensures numeric types are Decimal for DynamoDB compatibility.
    """
    try:
        batch_size = 25

        for i in range(0, len(players_data), batch_size):
            batch = players_data[i:i + batch_size]

            with table.batch_writer() as batch_writer:
                for player_data in batch:
                    item = dict(player_data)  # copy
                    # Convert floats to Decimal
                    for k, v in list(item.items()):
                        if isinstance(v, float):
                            item[k] = Decimal(str(v))
                        # already Decimal -> leave alone
                    batch_writer.put_item(Item=item)

            logger.info(f"Wrote batch of {len(batch)} items to DynamoDB")

    except Exception as e:
        logger.error(f"Error writing to DynamoDB: {str(e)}", exc_info=True)
        raise
