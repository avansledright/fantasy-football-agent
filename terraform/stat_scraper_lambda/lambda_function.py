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
from utils import nfl_teams, espn_team_slugs
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
table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'fantasy-football-players-updated')
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
        total_injuries_updated = 0

        # --- NEW: ESPN Injury Status Updates (use espn_player_id from Dynamo) ---
        try:
            count = update_injury_status_from_espn()
            total_injuries_updated += count
            logger.info(f"Updated injury status for {count} players from ESPN API")
        except Exception as e:
            logger.error(f"Error updating injuries from ESPN: {e}", exc_info=True)

        for position in positions:
            # Scrape stats only if week is completed (games finished)
            if week_status == 'completed':
                logger.info(f"Processing {position} stats for week {current_week} ({week_status})...")
                players_data = scrape_fantasypros_stats(position, current_week)
                if players_data:
                    logger.info(f"Sample Data after stat scrape: {players_data[0]}")
                    update_player_stats_in_consolidated_table(players_data, current_week)
                    total_players_processed += len(players_data)
                    logger.info(f"Processed {len(players_data)} {position} players")
                else:
                    logger.warning(f"No stats data found for {position}")
            else:
                logger.info(f"Skipping stats for {position} - week {current_week} is {week_status}")

            # Scrape projections logic:
            # - If week is upcoming/in_progress: scrape projections for current week
            # - If week is completed: scrape projections for NEXT week
            if week_status in ['upcoming', 'in_progress']:
                projection_week = current_week
                logger.info(f"Getting projection data for {position} week {projection_week} ({week_status})...")
                proj_data = scrape_fantasypros_projections(position, projection_week)
                
                if proj_data:
                    update_player_projections_in_table(proj_data, projection_week)
                    total_projections_processed += len(proj_data)
                    logger.info(f"Processed {len(proj_data)} {position} projections")
                else:
                    logger.warning(f"No projections found for {position}")
            elif week_status == 'completed' and current_week < 18:
                # Week just finished, get projections for next week
                projection_week = current_week + 1
                logger.info(f"Week {current_week} completed - getting projection data for {position} week {projection_week}...")
                proj_data = scrape_fantasypros_projections(position, projection_week)
                
                if proj_data:
                    update_player_projections_in_table(proj_data, projection_week)
                    total_projections_processed += len(proj_data)
                    logger.info(f"Processed {len(proj_data)} {position} projections for upcoming week")
                else:
                    logger.warning(f"No projections found for {position} week {projection_week}")
            else:
                logger.info(f"Skipping projections for {position} - week {current_week} is {week_status}")

        logger.info(f"Successfully processed {total_players_processed} total players")
        logger.info(f"Successfully processed {total_projections_processed} total projections")
        logger.info(f"Successfully updated {total_injuries_updated} injury statuses")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully updated {total_players_processed} player stats and processed projections for week {current_week}',
                'week': current_week,
                'week_status': week_status,
                'season': CURRENT_SEASON,
                'stats_processed': total_players_processed,
                'projections_processed': total_projections_processed,
                'injuries_updated': total_injuries_updated
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


# -------------------------
# ESPN INJURY FETCHERS
# -------------------------
def search_espn_player_id(player_name: str, position: str, team: str = None) -> Optional[int]:
    """Search for a player's ESPN ID using team roster API."""
    try:
        # Remove Jr., Sr., etc. from name for better matching
        clean_name = re.sub(r'\s+(Jr\.?|Sr\.?|III?|IV?)$', '', player_name, flags=re.IGNORECASE).strip()

        # If no team provided, we can't search rosters
        if not team or team.upper() not in espn_team_slugs:
            logger.warning(f"Cannot search for {player_name} - missing or invalid team: {team}")
            return None

        # Get ESPN team slug
        team_slug = espn_team_slugs.get(team.upper())
        if not team_slug:
            logger.warning(f"No ESPN team slug found for {team}")
            return None

        # Use ESPN team roster API
        roster_url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_slug}/roster"
        headers = {'User-Agent': 'Mozilla/5.0'}

        response = requests.get(roster_url, headers=headers, timeout=15)
        if response.status_code != 200:
            logger.warning(f"ESPN roster API returned {response.status_code} for team {team}")
            return None

        data = response.json()
        athletes = data.get('athletes', [])

        # Search through all position groups
        for position_group in athletes:
            items = position_group.get('items', [])
            for athlete in items:
                athlete_name = athlete.get('displayName', '')
                athlete_position = athlete.get('position', {}).get('abbreviation', '')
                athlete_id = athlete.get('id')

                # Match by name (case-insensitive, flexible matching)
                if athlete_name and athlete_id:
                    clean_athlete_name = re.sub(r'\s+(Jr\.?|Sr\.?|III?|IV?)$', '', athlete_name, flags=re.IGNORECASE).strip()

                    # Check if names match and position matches
                    if clean_name.lower() in clean_athlete_name.lower() and athlete_position == position:
                        logger.info(f"Found ESPN ID {athlete_id} for {player_name} ({position}) on team {team}")
                        return int(athlete_id)

        logger.warning(f"No ESPN ID found for {player_name} ({position}) on team {team}")
        return None

    except Exception as e:
        logger.warning(f"Error searching for ESPN ID for {player_name}: {e}")
        return None


def get_espn_injury_status(espn_player_id: int) -> str:
    """Fetch a player's injury status from ESPN API."""
    try:
        url = f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{espn_player_id}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            logger.warning(f"ESPN API returned {response.status_code} for player {espn_player_id}")
            return "UNKNOWN"

        data = response.json()
        athlete = data.get('athlete', {})

        # Check injuries array for actual injury status
        injuries = athlete.get('injuries', [])
        if injuries and len(injuries) > 0:
            # Get the most recent injury (first in array)
            injury = injuries[0]

            # First try fantasyStatus (most reliable for fantasy purposes)
            fantasy_status = injury.get('details', {}).get('fantasyStatus', {}).get('description', '')
            if fantasy_status:
                # Normalize to our standard values: Healthy, Questionable, Doubtful, Out, IR
                status_upper = fantasy_status.upper()
                if status_upper in ['OUT', 'O']:
                    return 'Out'
                elif status_upper in ['QUESTIONABLE', 'Q']:
                    return 'Questionable'
                elif status_upper in ['DOUBTFUL', 'D']:
                    return 'Doubtful'
                elif status_upper in ['IR', 'INJURED RESERVE']:
                    return 'IR'
                else:
                    return fantasy_status

            # Fallback to injury.status field
            injury_status = injury.get('status', '')
            if injury_status:
                return injury_status

        # No injuries found - player is healthy
        return 'Healthy'

    except Exception as e:
        logger.warning(f"Failed to fetch ESPN injury for {espn_player_id}: {e}")
        return 'UNKNOWN'


def update_injury_status_from_espn() -> int:
    """
    Iterate through DynamoDB players and update injury statuses using ESPN API.
    For players without espn_player_id, attempts to search for it and store it.
    """
    success_count = 0
    season_key = str(CURRENT_SEASON)

    scan_kwargs = {
        'ProjectionExpression': 'player_id, espn_player_id, player_name, #pos, #seasons.#season.team',
        'ExpressionAttributeNames': {
            '#pos': 'position',
            '#seasons': 'seasons',
            '#season': season_key
        }
    }
    done = False
    start_key = None

    while not done:
        if start_key:
            scan_kwargs['ExclusiveStartKey'] = start_key
        response = table.scan(**scan_kwargs)
        items = response.get('Items', [])

        for item in items:
            player_id = item.get('player_id')
            espn_id = item.get('espn_player_id')
            player_name = item.get('player_name')
            position = item.get('position')

            # Extract team from nested structure
            team = None
            seasons = item.get('seasons', {})
            if seasons and season_key in seasons:
                team = seasons[season_key].get('team')

            if not player_id or not player_name or not position:
                continue

            # If no ESPN ID, try to search for it using team roster
            if not espn_id:
                logger.info(f"Missing ESPN ID for {player_name} ({position}), team: {team}, attempting search...")
                espn_id = search_espn_player_id(player_name, position, team)

                if espn_id:
                    # Store the ESPN ID in DynamoDB for future use
                    try:
                        table.update_item(
                            Key={'player_id': player_id},
                            UpdateExpression="SET espn_player_id = :espn_id",
                            ExpressionAttributeValues={
                                ':espn_id': espn_id
                            }
                        )
                        logger.info(f"Stored ESPN ID {espn_id} for {player_name}")
                    except ClientError as ce:
                        logger.warning(f"Failed to store ESPN ID for {player_id}: {ce}")
                else:
                    logger.debug(f"Could not find ESPN ID for {player_name}, skipping injury update")
                    continue

            # Now fetch and update injury status
            status = get_espn_injury_status(espn_id)
            if not status or status == 'UNKNOWN':
                continue

            try:
                table.update_item(
                    Key={'player_id': player_id},
                    UpdateExpression="SET #seasons.#season.#injury_status = :status, #updated_at = :updated_at",
                    ExpressionAttributeNames={
                        '#seasons': 'seasons',
                        '#season': season_key,
                        '#injury_status': 'injury_status',
                        '#updated_at': 'updated_at'
                    },
                    ExpressionAttributeValues={
                        ':status': status,
                        ':updated_at': datetime.now().isoformat()
                    }
                )
                logger.info(f"Updated injury status for {player_name} to {status}")
                success_count += 1
            except ClientError as ce:
                logger.warning(f"Failed to update injury status for {player_id}: {ce}")

        start_key = response.get('LastEvaluatedKey', None)
        done = start_key is None

    return success_count


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
                        parsed['team'] = m.group(1)
                    else:
                        # try parsing for embedded code
                        m2 = re.search(r'([A-Z]{2,4})', team_text)
                        if m2:
                            parsed['team'] = m2.group(1)

                # DST special handling: the player_name should be the team abbreviation
                if position == "DST":
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
    Update player stats in the consolidated table using UPDATE operations.
    Writes to seasons.{year}.weekly_stats.{week} to match new schema.
    """
    try:
        logger.info(f"*** UPDATING STATS for week {week} with {len(players_data)} players ***")
        if players_data:
            logger.info(f"First player sample: {players_data[0]}")

        season_key = str(CURRENT_SEASON)
        week_key = str(week)
        
        success_count = 0
        error_count = 0

        for player_data in players_data:
            try:
                if player_data['position'] == "DST":
                    player_data['player_name'] = nfl_teams[player_data['player_name']]
                    logger.info(f"Found DST. New player name = {player_data['player_name']}")
                
                player_name = player_data['player_name']
                position = player_data['position']
                player_id = f"{player_name}#{position}"
                
                logger.debug(f"Updating stats for {player_id}: {player_data['fantasy_points']} points")
                
                # Build update expression for nested path
                update_expression = "SET #player_name = if_not_exists(#player_name, :player_name), "
                update_expression += "#position = if_not_exists(#position, :position), "
                update_expression += "#updated_at = :updated_at, "
                update_expression += "#seasons.#season.#weekly_stats.#week = :week_data"
                
                expression_attribute_names = {
                    '#player_name': 'player_name',
                    '#position': 'position',
                    '#updated_at': 'updated_at',
                    '#seasons': 'seasons',
                    '#season': season_key,
                    '#weekly_stats': 'weekly_stats',
                    '#week': week_key
                }
                
                expression_attribute_values = {
                    ':player_name': player_name,
                    ':position': position,
                    ':updated_at': player_data['updated_at'],
                    ':week_data': {
                        'fantasy_points': player_data['fantasy_points'],
                        'opponent': player_data['opponent'],
                        'team': player_data['team'],
                        'updated_at': player_data['updated_at']
                    }
                }
                
                # Execute update
                table.update_item(
                    Key={'player_id': player_id},
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values
                )
                
                success_count += 1
                logger.debug(f"Successfully updated stats for {player_id}")
                
            except Exception as e:
                logger.error(f"Error updating stats for {player_data.get('player_name', 'unknown')}: {str(e)}")
                error_count += 1
                continue

        logger.info(f"Stats update complete: {success_count} successful, {error_count} errors")

    except Exception as e:
        logger.error(f"Error in update_player_stats_in_consolidated_table: {str(e)}", exc_info=True)
        raise


def update_player_projections_in_table(players_data: List[Dict], week: int):
    """
    Update player projections in the consolidated table using UPDATE operations.
    Writes to seasons.{year}.weekly_projections.{week} to match new schema.
    """
    try:
        logger.info(f"*** UPDATING PROJECTIONS for week {week} with {len(players_data)} players ***")
        if players_data:
            logger.info(f"First projection sample: {players_data[0]}")

        season_key = str(CURRENT_SEASON)
        week_key = str(week)
        
        success_count = 0
        error_count = 0

        for player in players_data:
            try:
                player_id = f"{player['player_name']}#{player['position']}"

                # Ensure fantasy_points is Decimal
                try:
                    fpts = player.get('fantasy_points', 0)
                    if not isinstance(fpts, Decimal):
                        fpts = Decimal(str(fpts))
                except Exception:
                    fpts = Decimal('0')

                logger.debug(f"Updating projection for {player_id}: {fpts} points")
                
                # Build update expression for nested path
                update_expression = "SET #player_name = if_not_exists(#player_name, :player_name), "
                update_expression += "#position = if_not_exists(#position, :position), "
                update_expression += "#updated_at = :updated_at, "
                update_expression += "#seasons.#season.#weekly_projections.#week = :projection"
                
                expression_attribute_names = {
                    '#player_name': 'player_name',
                    '#position': 'position',
                    '#updated_at': 'updated_at',
                    '#seasons': 'seasons',
                    '#season': season_key,
                    '#weekly_projections': 'weekly_projections',
                    '#week': week_key
                }
                
                expression_attribute_values = {
                    ':player_name': player['player_name'],
                    ':position': player['position'],
                    ':updated_at': player.get('updated_at', datetime.now().isoformat()),
                    ':projection': fpts
                }
                
                # Execute update
                table.update_item(
                    Key={'player_id': player_id},
                    UpdateExpression=update_expression,
                    ExpressionAttributeNames=expression_attribute_names,
                    ExpressionAttributeValues=expression_attribute_values
                )
                
                success_count += 1
                logger.debug(f"Successfully updated projection for {player_id}")

            except Exception as e:
                logger.error(f"Error updating projection for {player.get('player_name', 'unknown')}: {e}", exc_info=True)
                error_count += 1
                continue

        logger.info(f"Projections update complete: {success_count} successful, {error_count} errors")

    except Exception as e:
        logger.error(f"Error in update_player_projections_in_table: {e}", exc_info=True)
