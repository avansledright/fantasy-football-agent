import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

TEAM_MAP = {
    'ARI': 'ari', 'ATL': 'atl', 'BAL': 'bal', 'BUF': 'buf', 'CAR': 'car', 'CHI': 'chi',
    'CIN': 'cin', 'CLE': 'cle', 'DAL': 'dal', 'DEN': 'den', 'DET': 'det', 'GB': 'gb',
    'HOU': 'hou', 'IND': 'ind', 'JAX': 'jax', 'KC': 'kc', 'LAC': 'lac', 'LAR': 'lar',
    'LV': 'lv', 'MIA': 'mia', 'MIN': 'min', 'NE': 'ne', 'NO': 'no', 'NYG': 'nyg',
    'NYJ': 'nyj', 'PHI': 'phi', 'PIT': 'pit', 'SEA': 'sea', 'SF': 'sf', 'TB': 'tb',
    'TEN': 'ten', 'WAS': 'was'
}

def lambda_handler(event, context):
    params = event.get('queryStringParameters') or {}
    team = params.get('team', '').upper()
    source = params.get('source', 'ourlads')

    if not team:
        return error_response(400, "Team parameter required")

    if team not in TEAM_MAP:
        return error_response(400, f"Invalid team code: {team}")

    try:
        if source == 'ourlads':
            depth_chart = scrape_ourlads(team)
        elif source == 'footballguys':
            depth_chart = scrape_footballguys(team)
        else:
            return error_response(400, f"Invalid source: {source}. Use 'ourlads' or 'footballguys'")

        return success_response(depth_chart)

    except Exception as e:
        print(f"Error scraping depth chart: {str(e)}")
        return error_response(500, f"Scraping failed: {str(e)}")

def scrape_ourlads(team):
    url = f"https://www.ourlads.com/nfldepthcharts/depthchart/{team}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    positions = {}

    # Only keep fantasy-relevant positions
    fantasy_positions = {'QB', 'RB', 'FB', 'WR', 'TE', 'K', 'PK'}

    # Normalize position names (PK -> K)
    position_mapping = {'PK': 'K'}

    # Ourlads uses tables - find all table rows
    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')

        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 3:  # Need at least Pos, No, Player1
                # First cell is position
                pos_cell = cells[0].get_text().strip()

                # Only process fantasy positions, skip header rows and non-position rows
                if pos_cell and len(pos_cell) <= 3 and pos_cell.isalpha() and pos_cell in fantasy_positions:
                    players = []

                    # Cells 2+ contain players (skip cell 1 which is jersey number)
                    for idx, cell in enumerate(cells[2:], start=1):
                        links = cell.find_all('a')
                        for link in links:
                            name = link.get_text().strip()
                            # Remove draft info like "23/1" from name
                            name = name.split('[')[0].strip()
                            if name:
                                players.append({
                                    "name": name,
                                    "depth": idx,
                                    "status": "Starter" if idx == 1 else "Backup"
                                })
                                break  # Only take first player per cell

                    if players:
                        # Normalize position name (PK -> K)
                        normalized_pos = position_mapping.get(pos_cell, pos_cell)
                        positions[normalized_pos] = players

    # Add DST placeholder
    if not positions.get('DST'):
        positions['DST'] = [{"name": f"{team} Defense", "depth": 1, "status": "Team"}]

    return {
        "team": team,
        "source": "ourlads",
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "positions": positions
    }

def scrape_footballguys(team):
    team_slug = TEAM_MAP.get(team, team.lower())
    url = f"https://www.footballguys.com/depth-charts#{team_slug}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    positions = parse_footballguys_html(soup, team)

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
        print(f"Team anchor not found for {team_slug}")
        positions['QB'] = [{"name": "Unknown", "depth": 1, "status": "Starter"}]
        return positions

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
                name = link.get_text().strip()
                # Remove status indicators like (Q), (O), (IR)
                name = name.split('(')[0].strip()
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
        positions['QB'] = [{"name": "Unknown", "depth": 1, "status": "Starter"}]

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
