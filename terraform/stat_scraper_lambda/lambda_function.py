import json
import boto3
from botocore.exceptions import ClientError
import requests
from bs4 import BeautifulSoup
import logging
from datetime import datetime, timedelta
import re
from decimal import Decimal, InvalidOperation
import os
from typing import Dict, List, Optional
from utils import nfl_teams
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
table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'fantasy-football-players')
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

        # Determine week status
        week_status = get_week_status(current_week)
        logger.info(f"Week {current_week} status: {week_status}")

        # Scrape stats for each position
        positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']
        total_players_processed = 0
        total_projections_processed = 0

        for position in positions:
            # Scrape stats only if week is completed (games finished)
            if week_status == 'completed':
                logger.info(f"Processing {position} stats for week {current_week} ({week_status})...")
                players_data = scrape_fantasypros_stats(position, current_week)
                logger.info(f"Sample Data after stat scrape: {players_data[1]}")
                if players_data:
                    update_player_stats_in_consolidated_table(players_data, current_week)
                    total_players_processed += len(players_data)
                    logger.info(f"Processed {len(players_data)} {position} players")
                else:
                    logger.warning(f"No stats data found for {position}")
            else:
                logger.info(f"Skipping stats for {position} - week {current_week} is {week_status}")

            # Scrape projections if week is current or upcoming
            if week_status in ['upcoming', 'in_progress']:
                logger.info(f"Getting projection data for {position} week {current_week} ({week_status})...")
                proj_data = scrape_fantasypros_projections(position, current_week)
                
                if proj_data:
                    update_player_projections_in_table(proj_data, current_week)
                    total_projections_processed += len(proj_data)
                    logger.info(f"Processed {len(proj_data)} {position} projections")
                else:
                    logger.warning(f"No projections found for {position}")
            else:
                logger.info(f"Skipping projections for {position} - week {current_week} is {week_status}")

        logger.info(f"Successfully processed {total_players_processed} total players")
        logger.info(f"Successfully proccessed {total_projections_processed} total projections")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully updated {total_players_processed} player stats and processed projections for week {current_week}',
                'week': current_week,
                'week_status': week_status,
                'season': CURRENT_SEASON,
                'stats_processed': total_players_processed,
                'projections_processed': total_projections_processed
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


def get_week_status(week: int) -> str:
    """
    Determine the status of an NFL week:
    - 'upcoming': Week hasn't started yet
    - 'in_progress': Week is currently happening (games in progress)
    - 'completed': All games for the week are finished
    """
    today = datetime.now()
    
    # NFL season 2025 started approximately September 4, 2025 (Thursday)
    # Week 1 typically runs Thursday-Monday
    season_start = datetime(2025, 9, 4)  # Adjust based on actual NFL schedule
    
    if today < season_start:
        return 'upcoming'
    
    # Calculate the start of the requested week
    # Week 1 starts on season_start, each subsequent week starts 7 days later
    week_start = season_start + timedelta(days=(week - 1) * 7)
    
    # NFL weeks typically end on Tuesday morning (after Monday Night Football)
    # So a week runs from Thursday to the following Tuesday
    week_end = week_start + timedelta(days=5)  # Thursday to Tuesday
    
    if today < week_start:
        return 'upcoming'
    elif today >= week_start and today <= week_end:
        return 'in_progress'
    else:
        return 'completed'


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
    Only returns data for players with non-zero fantasy points.
    """
    try:
        url = f"https://www.fantasypros.com/nfl/stats/{position.lower()}.php"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Always include week and PPR scoring
        params = {
            'week': week,
            'scoring': 'PPR',
            'range': 'week'
        }

        logger.info(f"Scraping stats URL: {url} with params: {params}")
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, 'html.parser')

        # Check page for indicators this might be showing projections instead of stats
        page_title = soup.find('title')
        if page_title:
            title_text = page_title.get_text().lower()
            if 'projection' in title_text or 'projected' in title_text:
                logger.warning(f"Stats page for {position} week {week} appears to be showing projections based on title: {title_text}")
                return []

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

        logger.info(f"Found headers: {headers}")

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

        logger.info(f"Using player_idx: {player_idx}, fpts_idx: {fpts_idx}")

        # Get table body rows
        tbody = stats_table.find('tbody')
        rows = tbody.find_all('tr') if tbody else stats_table.find_all('tr')[1:]

        logger.info(f"Found {len(rows)} data rows")

        players_data = []
        zero_point_players = 0

        for row in rows:
            try:
                player_data = parse_player_row(row, position, week, player_idx, fpts_idx)
                if not player_data:
                    continue

                # Skip players with zero or negative fantasy points (no games played yet)
                if player_data['fantasy_points'] <= 0:
                    zero_point_players += 1
                    logger.debug(f"Skipping {player_data.get('player_name')} - zero fantasy points (no game played)")
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

        logger.info(f"Processed {len(rows)} rows for {position}: {len(players_data)} with stats, {zero_point_players} with zero points")
        
        if players_data:
            logger.info(f"Sample player data: {players_data[0]}")

        return players_data

    except requests.RequestException as e:
        logger.error(f"Request error for {position}: {str(e)}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error scraping {position} stats: {str(e)}", exc_info=True)
        return []


def scrape_fantasypros_projections(position: str, week: int) -> List[Dict]:
    """
    Scrape weekly projections (FPTS only) from FantasyPros for a given position.

    Uses parse_player_row() to normalize names exactly like the stats scraper so
    player_id's line up with existing DynamoDB records.
    """
    try:
        url = f"https://www.fantasypros.com/nfl/projections/{position.lower()}.php"
        headers = {'User-Agent': 'Mozilla/5.0'}
        params = {'scoring': 'PPR', 'week': week}

        logger.info(f"Scraping projections URL: {url} with params: {params}")

        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, 'html.parser')

        stats_table = soup.find('table', {'id': 'data'}) or soup.find('table', class_='table')
        if not stats_table:
            logger.warning(f"No projections table found for {position} week {week} at {url}")
            return []

        # Grab last header row (handles multi-row headers)
        thead = stats_table.find('thead')
        if not thead:
            logger.warning("No thead found in projections table")
            return []

        header_rows = thead.find_all('tr')
        if not header_rows:
            logger.warning("No header rows in projections thead")
            return []

        header_cells = header_rows[-1].find_all(['th', 'td'])
        headers = [hc.get_text(strip=True).upper() for hc in header_cells]
        header_index = {h: i for i, h in enumerate(headers)}

        logger.info(f"Projections headers: {headers}")

        # helper like stats scraper: find header index by exact or prefix match
        def find_header_index(targets):
            for t in targets:
                for h, idx in header_index.items():
                    if h == t or h.startswith(t):
                        return idx
            return None

        player_idx = find_header_index(['PLAYER'])
        team_idx = find_header_index(['TEAM'])  # if projections table has a separate TEAM column
        fpts_idx = find_header_index(['FPTS']) or find_header_index(['FPTS/G']) or (len(headers) - 1)

        logger.info(f"Projections using player_idx: {player_idx}, team_idx: {team_idx}, fpts_idx: {fpts_idx}")

        # iterate body rows
        tbody = stats_table.find('tbody')
        rows = tbody.find_all('tr') if tbody else stats_table.find_all('tr')[1:]
        players = []

        for row in rows:
            try:
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue

                # Reuse parse_player_row to normalize player_name/team exactly the same way
                parsed = parse_player_row(row, position, week, player_idx, fpts_idx)
                if not parsed:
                    continue

                # If the table provides a separate TEAM column, prefer that value (more reliable)
                if team_idx is not None and team_idx < len(cells):
                    team_text = cells[team_idx].get_text(strip=True).upper()
                    # team_text might be full team name or 2-4 letter code; try to extract code
                    m = re.match(r'^([A-Z]{2,4})$', team_text)
                    if m:
                        team_code = m.group(1)
                    else:
                        # fallback: take last token if it's an uppercase abbr
                        toks = team_text.split()
                        if toks and re.match(r'^[A-Z]{2,4}$', toks[-1]):
                            team_code = toks[-1]
                        else:
                            team_code = team_text  # last resort: use the raw team_text
                    # override parsed team and strip trailing code from player_name if present
                    parsed['team'] = team_code
                    if parsed['player_name'].endswith(' ' + team_code):
                        parsed['player_name'] = parsed['player_name'][:-(len(team_code) + 1)]

                # For DST, ensure same naming convention as stats scraper
                if position == "DST":
                    logger.info(f"PARSED: {parsed}")
                    parsed['player_name'] = parsed['player_name'].replace(" DST", "")
                    logger.info(f"Found DST parsed name == {parsed['player_name']}")
                    if parsed.get('team') and parsed['team'] != "UNK":
                        parsed['player_name'] = f"{parsed['team']}"

                # fantasy_points from parse_player_row is already Decimal when possible; ensure type
                fpts = parsed.get('fantasy_points', Decimal('0'))
                try:
                    if not isinstance(fpts, Decimal):
                        fpts = Decimal(str(fpts))
                except Exception:
                    fpts = Decimal('0')

                # Skip projections with zero or negative fantasy points
                if fpts <= 0:
                    logger.debug(f"Skipping {parsed['player_name']} projection - zero/negative points: {fpts}")
                    continue

                players.append({
                    'player_name': parsed['player_name'],
                    'position': position,
                    'fantasy_points': fpts,
                    'week': int(week),
                    'season': int(CURRENT_SEASON),
                    'updated_at': datetime.now().isoformat()
                })
            except Exception as e:
                logger.warning(f"Error parsing projection row for {position}: {e}", exc_info=True)
                continue

        logger.info(f"Processed projections for {position}: {len(players)} players with non-zero projections")
        return players

    except requests.RequestException as e:
        logger.error(f"Request error while scraping projections for {position}: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error scraping projections for {position}: {e}", exc_info=True)
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
    Returns dict with player data for updating consolidated table.
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
                player_name = f"{team}"
            else:
                # fallback: use whatever we parsed
                player_name = f"{player_name}"

        # Extract fantasy points from fpts_idx
        fantasy_points = Decimal('0')
        fpts_text = ""
        
        if fpts_idx is not None and fpts_idx < len(cells):
            fpts_text = cells[fpts_idx].get_text(strip=True).replace(',', '')
            try:
                if fpts_text == '' or fpts_text == '-':
                    fantasy_points = Decimal('0')
                else:
                    fantasy_points = Decimal(str(float(fpts_text)))
            except (ValueError, InvalidOperation):
                logger.debug(f"Could not parse FPTS '{fpts_text}' for {player_name}, trying fallback")
                # fallback: scan cells for a numeric-looking value (but exclude roster %)
                for i, c in enumerate(reversed(cells)):
                    txt = c.get_text(strip=True).replace(',', '').replace('%', '')
                    # Skip if this looks like a percentage (roster %)
                    if '%' in c.get_text(strip=True):
                        continue
                    if re.match(r'^\d+(\.\d+)?$', txt):
                        try:
                            potential_points = Decimal(str(float(txt)))
                            # Sanity check: fantasy points should be reasonable (0-100 range typically)
                            if potential_points <= 100:
                                fantasy_points = potential_points
                                logger.debug(f"Used fallback value {fantasy_points} from column {len(cells)-i-1}")
                                break
                        except (ValueError, InvalidOperation):
                            continue
        else:
            # Complete fallback: scan last few columns, excluding roster %
            for i, c in enumerate(reversed(cells)):
                txt = c.get_text(strip=True).replace(',', '')
                # Skip if this looks like a percentage
                if '%' in txt:
                    continue
                txt = txt.replace('%', '')
                if re.match(r'^\d+(\.\d+)?$', txt):
                    try:
                        potential_points = Decimal(str(float(txt)))
                        if potential_points <= 100:  # Sanity check
                            fantasy_points = potential_points
                            break
                    except (ValueError, InvalidOperation):
                        continue

        # Debug logging for troubleshooting
        logger.debug(f"Parsed row - Player: {player_name}, Team: {team}, FPTS Text: '{fpts_text}', FPTS Value: {fantasy_points}")

        # Build player data for updating consolidated table
        player_data = {
            'player_name': player_name,
            'position': position,
            'team': team,
            'fantasy_points': fantasy_points,
            'opponent': get_opponent_from_row(cells, team),  # may be empty; will be overwritten by schedule lookup if available
            'week': int(week),
            'season': int(CURRENT_SEASON),
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


def update_player_stats_in_consolidated_table(players_data: List[Dict], week: int):
    """
    Update player stats in the consolidated fantasy-football-players table.
    Each player's current_season_stats gets updated with the new week's data.
    """
    try:
        logger.info(f"*** UPDATING CURRENT_SEASON_STATS for week {week} with {len(players_data)} players ***")
        if players_data:
            logger.info(f"First player sample: {players_data[0]}")

        batch_size = 25

        for i in range(0, len(players_data), batch_size):
            batch = players_data[i:i + batch_size]

            with table.batch_writer() as batch_writer:
                for player_data in batch:
                    if player_data['position'] == "DST":
                        player_data['player_name'] = nfl_teams[player_data['player_name']]
                        logger.info(f"Found DST. New player name = {player_data['player_name']}")
                    player_name = player_data['player_name']
                    position = player_data['position']
                    player_id = f"{player_name}#{position}"
                    
                    logger.debug(f"Processing stats update for {player_id}: {player_data['fantasy_points']} points")
                    
                    # Check if player exists in consolidated table
                    try:
                        response = table.get_item(Key={'player_id': player_id})
                        
                        if 'Item' in response:
                            # Update existing player
                            existing_item = response['Item']
                            
                            # Initialize current_season_stats if not present
                            if 'current_season_stats' not in existing_item:
                                existing_item['current_season_stats'] = {}
                            
                            # Initialize 2025 season if not present
                            if str(CURRENT_SEASON) not in existing_item['current_season_stats']:
                                existing_item['current_season_stats'][str(CURRENT_SEASON)] = {}
                            
                            # Update the specific week's stats
                            existing_item['current_season_stats'][str(CURRENT_SEASON)][str(week)] = {
                                'fantasy_points': player_data['fantasy_points'],
                                'opponent': player_data['opponent'],
                                'team': player_data['team'],
                                'updated_at': player_data['updated_at']
                            }
                            
                            # Write updated item back to table
                            batch_writer.put_item(Item=existing_item)
                            logger.debug(f"Updated existing player: {player_id} week {week}")
                            
                        else:
                            # Create new player entry
                            new_item = {
                                'player_id': player_id,
                                'player_name': player_name,
                                'position': position,
                                'historical_seasons': {},
                                'projections': {},
                                'current_season_stats': {
                                    str(CURRENT_SEASON): {
                                        str(week): {
                                            'fantasy_points': player_data['fantasy_points'],
                                            'opponent': player_data['opponent'],
                                            'team': player_data['team'],
                                            'updated_at': player_data['updated_at']
                                        }
                                    }
                                }
                            }
                            
                            batch_writer.put_item(Item=new_item)
                            logger.debug(f"Created new player: {player_id} week {week}")
                            
                    except Exception as e:
                        logger.error(f"Error processing player {player_id}: {str(e)}")
                        continue

            logger.info(f"Processed batch of {len(batch)} players for week {week}")

    except Exception as e:
        logger.error(f"Error updating consolidated table: {str(e)}", exc_info=True)
        raise


def update_player_projections_in_table(players_data: List[Dict], week: int):
    """
    Update player projections in the consolidated table.
    Stores weekly projections under: projections[<season>]['weekly'][<week>].
    Simple, safe: get -> mutate -> put.
    """
    try:
        logger.info(f"*** UPDATING PROJECTIONS for week {week} with {len(players_data)} players ***")
        if players_data:
            logger.info(f"First projection sample: {players_data[0]}")

        season_key = str(CURRENT_SEASON)
        week_key = str(week)

        with table.batch_writer() as batch:
            for player in players_data:
                player_id = f"{player['player_name']}#{player['position']}"

                # Ensure fantasy_points is Decimal
                try:
                    fpts = player.get('fantasy_points', 0)
                    if not isinstance(fpts, Decimal):
                        fpts = Decimal(str(fpts))
                except Exception:
                    fpts = Decimal('0')

                week_val = {
                    'fantasy_points': fpts,
                    'updated_at': player.get('updated_at', datetime.now().isoformat())
                }

                try:
                    resp = table.get_item(Key={'player_id': player_id})
                    logger.debug(f"Updating projections for {player_id}: {fpts} points")
                    
                    if 'Item' in resp:
                        item = resp['Item']

                        # make sure projections exists
                        if 'projections' not in item or not isinstance(item['projections'], dict):
                            item['projections'] = {}

                        # make sure this season exists
                        if season_key not in item['projections'] or not isinstance(item['projections'][season_key], dict):
                            # preserve old value if it was not a dict
                            prev_val = item['projections'].get(season_key)
                            if prev_val and not isinstance(prev_val, dict):
                                item['projections'][season_key] = {'season_totals': prev_val}
                            else:
                                item['projections'][season_key] = {}

                        # make sure weekly exists
                        if 'weekly' not in item['projections'][season_key]:
                            item['projections'][season_key]['weekly'] = {}

                        # set this week's projection
                        item['projections'][season_key]['weekly'][week_key] = week_val
                        
                        try:
                            batch.put_item(Item=item)
                        except ClientError as e:
                            logger.error(f"Failed to put updated item for {player_id}: {e}")

                    else:
                        # new item
                        new_item = {
                            'player_id': player_id,
                            'player_name': player['player_name'],
                            'position': player['position'],
                            'historical_seasons': {},
                            'current_season_stats': {},
                            'projections': {
                                season_key: {
                                    'weekly': {
                                        week_key: week_val
                                    }
                                }
                            }
                        }
                        batch.put_item(Item=new_item)

                except Exception as e:
                    logger.error(f"Error updating projections for {player_id}: {e}", exc_info=True)

        logger.info(f"Processed projections for {len(players_data)} players, week {week}")

    except Exception as e:
        logger.error(f"Error in update_player_projections_in_table: {e}", exc_info=True)