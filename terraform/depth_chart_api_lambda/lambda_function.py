import json
import requests
import logging
from bs4 import BeautifulSoup
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Footballguys team code mappings
TEAM_MAP = {
    'ARI': 'crd', 'ATL': 'atl', 'BAL': 'rav', 'BUF': 'buf', 'CAR': 'car', 'CHI': 'chi',
    'CIN': 'cin', 'CLE': 'cle', 'DAL': 'dal', 'DEN': 'den', 'DET': 'det', 'GB': 'gnb',
    'HOU': 'htx', 'IND': 'clt', 'JAX': 'jax', 'KC': 'kan', 'LAC': 'sdg', 'LAR': 'ram',
    'LV': 'rai', 'MIA': 'mia', 'MIN': 'min', 'NE': 'nwe', 'NO': 'nor', 'NYG': 'nyg',
    'NYJ': 'nyj', 'PHI': 'phi', 'PIT': 'pit', 'SEA': 'sea', 'SF': 'sfo', 'TB': 'tam',
    'TEN': 'oti', 'WAS': 'was'
}

# Ourlads uses different codes for some teams
OURLADS_TEAM_MAP = {
    'ARI': 'ARZ',  # Arizona uses ARZ on Ourlads
}

def lambda_handler(event, context):
    params = event.get('queryStringParameters') or {}
    team = params.get('team', '').upper()
    source = params.get('source', 'ourlads')

    logger.info(f"Depth chart request - Team: {team}, Source: {source}")

    if not team:
        logger.warning("Team parameter missing")
        return error_response(400, "Team parameter required")

    if team not in TEAM_MAP:
        logger.warning(f"Invalid team code: {team}")
        return error_response(400, f"Invalid team code: {team}")

    try:
        if source == 'ourlads':
            logger.info(f"Scraping Ourlads for {team}")
            depth_chart = scrape_ourlads(team)
        elif source == 'footballguys':
            logger.info(f"Scraping Footballguys for {team}")
            depth_chart = scrape_footballguys(team)
        else:
            logger.warning(f"Invalid source: {source}")
            return error_response(400, f"Invalid source: {source}. Use 'ourlads' or 'footballguys'")

        position_count = len(depth_chart.get('positions', {}))
        logger.info(f"Successfully scraped {position_count} positions for {team} from {source}")
        return success_response(depth_chart)

    except Exception as e:
        logger.error(f"Error scraping depth chart for {team} from {source}: {str(e)}", exc_info=True)
        return error_response(500, f"Scraping failed: {str(e)}")

def scrape_ourlads(team):
    # Use special mapping for Ourlads if available, otherwise use team code as-is
    ourlads_code = OURLADS_TEAM_MAP.get(team, team)
    url = f"https://www.ourlads.com/nfldepthcharts/depthchart/{ourlads_code}"

    logger.info(f"Ourlads URL: {url} (mapped {team} -> {ourlads_code})")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    logger.info(f"Ourlads HTTP {response.status_code}, Content length: {len(response.text)}")

    soup = BeautifulSoup(response.text, 'html.parser')

    positions = {}

    # Only keep fantasy-relevant positions
    # Include split WR positions: LWR (Left WR), RWR (Right WR), SWR (Slot WR)
    fantasy_positions = {'QB', 'RB', 'FB', 'WR', 'LWR', 'RWR', 'SWR', 'TE', 'K', 'PK'}

    # Normalize position names (PK -> K, LWR/RWR/SWR -> WR)
    position_mapping = {
        'PK': 'K',
        'LWR': 'WR',  # Left Wide Receiver
        'RWR': 'WR',  # Right Wide Receiver
        'SWR': 'WR'   # Slot Wide Receiver
    }

    # Ourlads uses tables - find all table rows, but ONLY from active roster sections
    # Find all heading tags (h1, h2, h3) to identify sections
    all_elements = soup.find_all(['h1', 'h2', 'h3', 'table'])
    logger.info(f"Found {len(all_elements)} total elements (headings + tables)")

    current_section = None
    tables_processed = 0

    for element in all_elements:
        if element.name in ['h1', 'h2', 'h3']:
            # This is a heading - update current section
            section_text = element.get_text().strip().lower()
            if 'offense' in section_text:
                current_section = 'offense'
                logger.info(f"Detected Offense section: '{element.get_text().strip()}'")
            elif 'defense' in section_text:
                current_section = 'defense'
                logger.info(f"Detected Defense section: '{element.get_text().strip()}'")
            elif 'special teams' in section_text:
                current_section = 'special_teams'
                logger.info(f"Detected Special Teams section: '{element.get_text().strip()}'")
            elif 'practice squad' in section_text or 'reserves' in section_text or 'injured reserve' in section_text:
                current_section = 'excluded'
                logger.info(f"Detected excluded section: '{element.get_text().strip()}'")
            else:
                # Unknown section, keep previous section
                pass
        elif element.name == 'table' and current_section in ['offense', 'defense', 'special_teams']:
            # This is a table in an active roster section - process it
            tables_processed += 1
            logger.info(f"Processing table #{tables_processed} in section: {current_section}")
            rows = element.find_all('tr')

            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:  # Need at least Pos, No, Player1
                    # First cell is position
                    pos_cell = cells[0].get_text().strip()

                    # Check for injury marker (caret symbol ^) and skip injured players
                    if '^' in pos_cell:
                        logger.info(f"  Skipping injured player row: {pos_cell} (marked with ^)")
                        continue

                    # Clean position code (remove any remaining special characters)
                    pos_cell_clean = pos_cell.replace('^', '').strip()

                    # Only process fantasy positions, skip header rows and non-position rows
                    if pos_cell_clean and len(pos_cell_clean) <= 3 and pos_cell_clean.isalpha() and pos_cell_clean in fantasy_positions:
                        players = []

                        # Cells 2+ contain players (skip cell 1 which is jersey number)
                        for idx, cell in enumerate(cells[2:], start=1):
                            links = cell.find_all('a')
                            for link in links:
                                # Check for injury CSS class (lc_red indicates injured/inactive)
                                css_class = link.get('class', [])
                                if 'lc_red' in css_class:
                                    player_name_preview = link.get_text().strip()[:30]
                                    logger.info(f"    Skipping injured player (lc_red): {player_name_preview}")
                                    continue

                                name = link.get_text().strip()
                                # Remove draft info like "23/1" from name
                                name = name.split('[')[0].strip()
                                # Skip if player name contains injury marker (legacy check)
                                if '^' in name:
                                    logger.info(f"    Skipping injured player: {name}")
                                    continue
                                if name:
                                    players.append({
                                        "name": name,
                                        "depth": idx,
                                        "status": "Starter" if idx == 1 else "Backup"
                                    })
                                    break  # Only take first player per cell

                        if players:
                            # Normalize position name (PK -> K, LWR/RWR/SWR -> WR)
                            normalized_pos = position_mapping.get(pos_cell_clean, pos_cell_clean)

                            # If position already exists (e.g., multiple WR positions), merge players
                            if normalized_pos in positions:
                                # Add new players with adjusted depth
                                current_depth = len(positions[normalized_pos])
                                for player in players:
                                    player['depth'] = current_depth + player['depth']
                                    # First 2-3 WRs are typically starters in fantasy
                                    player['status'] = "Starter" if player['depth'] <= 3 else "Backup"
                                positions[normalized_pos].extend(players)
                                player_names = [p['name'] for p in players][:2]
                                logger.info(f"  {normalized_pos} (merged {pos_cell_clean}): +{len(players)} players {player_names}, total now: {len(positions[normalized_pos])}")
                            else:
                                positions[normalized_pos] = players
                                player_names = [p['name'] for p in players][:3]
                                logger.info(f"  {normalized_pos} (from {pos_cell_clean}): {len(players)} players - {player_names}")

    # Add DST placeholder
    if not positions.get('DST'):
        positions['DST'] = [{"name": f"{team} Defense", "depth": 1, "status": "Team"}]

    logger.info(f"Ourlads scrape complete: {len(positions)} positions extracted")

    return {
        "team": team,
        "source": "ourlads",
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "positions": positions
    }

def scrape_footballguys(team):
    team_slug = TEAM_MAP.get(team, team.lower())
    url = f"https://www.footballguys.com/depth-charts#{team_slug}"

    logger.info(f"Footballguys URL: {url} (mapped {team} -> {team_slug})")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    logger.info(f"Footballguys HTTP {response.status_code}, Content length: {len(response.text)}")

    soup = BeautifulSoup(response.text, 'html.parser')

    positions = parse_footballguys_html(soup, team)

    logger.info(f"Footballguys scrape complete: {len(positions)} positions extracted")

    return {
        "team": team,
        "source": "footballguys",
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "positions": positions
    }

def parse_footballguys_html(soup, team):
    positions = {}
    team_slug = TEAM_MAP.get(team, team.lower())

    # Find the team's anchor marker
    team_anchor = soup.find('a', {'id': team_slug}) or soup.find('a', {'name': team_slug})

    if not team_anchor:
        logger.warning(f"Team anchor not found for {team_slug}")
        positions['QB'] = [{"name": "Unknown", "depth": 1, "status": "Starter"}]
        return positions

    logger.info(f"Found team anchor for {team_slug}")

    # Get all elements after the team anchor until the next team anchor
    current = team_anchor
    team_elements = []

    # Collect all elements in this team's section
    while current:
        current = current.find_next()
        if not current:
            break

        # Stop if we hit another team anchor
        if current.name == 'a' and (current.get('id') or current.get('name')) and current.get('id') != team_slug:
            # Check if this looks like a team anchor (short alphanumeric ID)
            anchor_id = current.get('id') or current.get('name')
            if anchor_id and len(anchor_id) <= 4 and anchor_id in TEAM_MAP.values():
                break

        team_elements.append(current)

    # Parse positions from the team's elements
    fantasy_positions = ['QB', 'RB', 'FB', 'WR', 'TE', 'K', 'PK', 'DST']
    non_fantasy_positions = ['DE', 'DT', 'NT', 'LB', 'MLB', 'OLB', 'ILB', 'CB', 'S', 'SS', 'FS', 'DB',
                             'LT', 'LG', 'C', 'RG', 'RT', 'OL', 'DL',
                             'LDE', 'RDE', 'LDT', 'RDT', 'WLB', 'SLB', 'LCB', 'RCB', 'SCB',
                             'P', 'LS', 'H', 'KR', 'PR']
    # Normalize position names (PK -> K)
    position_mapping = {'PK': 'K'}
    current_position = None

    for element in team_elements:
        # Skip non-elements
        if not hasattr(element, 'get_text'):
            continue

        text = element.get_text().strip()

        # Check if this is a position header
        position_found = False
        for pos in fantasy_positions:
            # Match "QB:", "QB ", or just "QB" followed by players
            if text.startswith(pos + ':') or (text == pos):
                # Normalize position name (PK -> K)
                normalized_pos = position_mapping.get(pos, pos)
                current_position = normalized_pos
                if normalized_pos not in positions:
                    positions[normalized_pos] = []
                position_found = True
                break

        # If we hit a non-fantasy position, reset current_position
        if not position_found:
            for non_pos in non_fantasy_positions:
                if text.startswith(non_pos + ':') or text == non_pos:
                    current_position = None
                    break

        # If we have a current position and this element contains player links
        if current_position and element.name in ['li', 'p', 'div']:
            player_links = element.find_all('a', href=True)
            for link in player_links:
                full_text = link.get_text().strip()

                # Check for injury status indicators and skip injured players
                # (O) = Out, (IR) = Injured Reserve, (PUP) = Physically Unable to Perform
                if '(O)' in full_text or '(IR)' in full_text or '(PUP)' in full_text or '(SUSP)' in full_text:
                    logger.info(f"  Skipping injured/inactive player: {full_text}")
                    continue

                # Remove all status indicators like (Q), (D), etc.
                name = full_text.split('(')[0].strip()
                # Remove comma separators
                name = name.rstrip(',')

                # Filter out navigation links and ensure it's a player name
                if name and len(name) > 2 and not name.startswith('['):
                    # Check if player already added to avoid duplicates
                    if not any(p['name'] == name for p in positions[current_position]):
                        depth = len(positions[current_position]) + 1
                        positions[current_position].append({
                            "name": name,
                            "depth": depth,
                            "status": "Starter" if depth == 1 else "Backup"
                        })

    # Fallback if parsing failed
    if not positions:
        logger.warning(f"No positions found for {team}, using fallback")
        positions['QB'] = [{"name": "Unknown", "depth": 1, "status": "Starter"}]
    else:
        logger.info(f"Parsed {len(positions)} positions from Footballguys for {team}")

    return positions

def success_response(data):
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Cache-Control': 'max-age=3600'
        },
        'body': json.dumps(data, ensure_ascii=False)
    }

def error_response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': message})
    }
