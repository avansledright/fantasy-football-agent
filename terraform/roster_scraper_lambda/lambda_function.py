import json
import os
import logging
import boto3
import requests
from datetime import datetime
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')

def generate_player_id(name, position):
    """Generate player_id in format: name_position (e.g., josh_allen_qb)"""
    clean_name = name.lower().replace(' ', '_').replace('.', '').replace("'", '').replace('-', '_')
    return f"{clean_name}_{position.lower()}"

def get_team_abbreviation(pro_team_id):
    """Map ESPN pro team ID to team abbreviation"""
    teams = {
        1: 'ATL', 2: 'BUF', 3: 'CHI', 4: 'CIN', 5: 'CLE', 6: 'DAL', 7: 'DEN', 8: 'DET',
        9: 'GB', 10: 'TEN', 11: 'IND', 12: 'KC', 13: 'LV', 14: 'LAR', 15: 'MIA', 16: 'MIN',
        17: 'NE', 18: 'NO', 19: 'NYG', 20: 'NYJ', 21: 'PHI', 22: 'ARI', 23: 'PIT', 24: 'LAC',
        25: 'SF', 26: 'SEA', 27: 'TB', 28: 'WSH', 29: 'CAR', 30: 'JAX', 33: 'BAL', 34: 'HOU'
    }
    return teams.get(pro_team_id, 'FA')

def get_position_name(position_id):
    """Convert ESPN position ID to position name"""
    positions = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE', 5: 'K', 16: 'DST'}
    return positions.get(position_id, 'UNKNOWN')

def get_injury_status(player):
    """Extract and format injury status from player data"""
    try:
        # ESPN API provides injuryStatus in the player object
        injury_status = player.get('injuryStatus', 'ACTIVE')
        
        # Map ESPN injury status codes to readable format
        injury_mapping = {
            'ACTIVE': 'Healthy',
            'QUESTIONABLE': 'Questionable',
            'DOUBTFUL': 'Doubtful', 
            'OUT': 'Out',
            'IR': 'IR',
            'PUP': 'PUP',
            'SUSPENSION': 'Suspended',
            'NA': 'Healthy'
        }
        
        return injury_mapping.get(injury_status, injury_status)
    except:
        return 'Healthy'

def get_owner_name(owner_id, members_data):
    """Convert owner UUID to display name"""
    for member in members_data:
        if member.get('id') == owner_id:
            # Try to get display name, fall back to first/last name
            display_name = member.get('displayName')
            if display_name:
                return display_name
            
            first_name = member.get('firstName', '')
            last_name = member.get('lastName', '')
            if first_name or last_name:
                return f"{first_name} {last_name}".strip()
            
            # Fall back to UUID if no name found
            return owner_id
    return owner_id
    
def process_team_roster(team, league_id, league_name, members_data):
    """
    Processes a single team's roster to correctly assign player statuses and slots.
    Returns a dictionary ready to be written to DynamoDB.
    """
    starters_dict = {
        'QB': [],
        'RB': [],
        'WR': [],
        'TE': [],
        'FLEX': [],
        'OP': [],
        'K': [],
        'DST': []
    }
    bench_players = []
    
    # Pass 1: Categorize players based on lineupSlotId and position
    for entry in team.get('roster', {}).get('entries', []):
        player = entry.get('playerPoolEntry', {}).get('player', {})
        if not player:
            continue
        
        name = f"{player.get('firstName', '')} {player.get('lastName', '')}".strip()
        position = get_position_name(player.get('defaultPositionId'))
        slot_id = entry.get('lineupSlotId')
        pro_team_id = player.get('proTeamId', 0)
        
        # Get injury status for the player
        injury_status = get_injury_status(player)
        
        # Log player and their initial lineupSlotId
        logger.info(f"Processing player: {name} (ID: {player.get('id')}), API lineupSlotId: {slot_id}, Injury: {injury_status}")
        
        # Special case for DST
        if position == 'DST':
            name = f"{get_team_abbreviation(pro_team_id)} DST"
            player_id = f"{name.lower().replace(' ', '_')}"
        else:
            player_id = generate_player_id(name, position)

        player_data = {
            'name': name,
            'player_id': player_id,
            'position': position,
            'status': 'starter' if slot_id != 20 else 'bench',
            'team': get_team_abbreviation(pro_team_id),
            'injury_status': injury_status  # New field added here
        }

        if slot_id == 20: # Bench player
            player_data['slot'] = 'BENCH'
            bench_players.append(player_data)
        elif slot_id == 0: # QB
            player_data['slot'] = 'QB'
            starters_dict['QB'].append(player_data)
        elif slot_id == 17: # Kicker
            player_data['slot'] = 'K'
            starters_dict['K'].append(player_data)
        elif slot_id == 16: # DST
            player_data['slot'] = 'DST'
            starters_dict['DST'].append(player_data)
        elif slot_id == 23: # FLEX
            player_data['slot'] = 'FLEX'
            starters_dict['FLEX'].append(player_data)
        elif slot_id == 7: # OP
            player_data['slot'] = 'OP'
            starters_dict['OP'].append(player_data)
        elif slot_id == 6: # TE
            player_data['slot'] = 'TE'
            starters_dict['TE'].append(player_data)
        else: # RB and WR
            if position == 'RB':
                starters_dict['RB'].append(player_data)
            elif position == 'WR':
                starters_dict['WR'].append(player_data)
            elif position == 'TE':
                starters_dict['TE'].append(player_data)

    # Pass 2: Assign numbered slots to players sorted by name for consistency
    final_players = []
    final_players.extend(starters_dict['QB'])
    
    # Assign RB1 and RB2
    starters_dict['RB'].sort(key=lambda p: p['name'])
    if len(starters_dict['RB']) >= 1:
        starters_dict['RB'][0]['slot'] = 'RB1'
        final_players.append(starters_dict['RB'][0])
    if len(starters_dict['RB']) >= 2:
        starters_dict['RB'][1]['slot'] = 'RB2'
        final_players.append(starters_dict['RB'][1])
    
    # Assign WR1 and WR2
    starters_dict['WR'].sort(key=lambda p: p['name'])
    if len(starters_dict['WR']) >= 1:
        starters_dict['WR'][0]['slot'] = 'WR1'
        final_players.append(starters_dict['WR'][0])
    if len(starters_dict['WR']) >= 2:
        starters_dict['WR'][1]['slot'] = 'WR2'
        final_players.append(starters_dict['WR'][1])

    # Assign TE, FLEX, OP, K, and DST
    final_players.extend(starters_dict['TE'])
    final_players.extend(starters_dict['FLEX'])
    final_players.extend(starters_dict['OP'])
    final_players.extend(starters_dict['K'])
    final_players.extend(starters_dict['DST'])

    # Add all bench players
    final_players.extend(bench_players)

    # Log the final processed roster for comparison
    logger.info(f"Final processed roster for team {team.get('id')}:")
    for player in final_players:
        logger.info(f"  Player: {player['name']}, Final Slot: {player['slot']}, Status: {player['status']}, Injury: {player['injury_status']}")

    # Get owner names
    owner_ids = team.get('owners', [])
    owner_names = [get_owner_name(owner_id, members_data) for owner_id in owner_ids]
    
    return {
        'team_id': str(team['id']),
        'last_updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'league_id': league_id,
        'league_name': league_name,
        'owner': ', '.join(owner_names) if owner_names else 'Unknown',
        'team_name': f"{team.get('location', '')} {team.get('nickname', '')}".strip(),
        'players': final_players
    }

def lambda_handler(event, context):
    """Main Lambda handler"""
    
    try:
        # Get configuration
        league_id = os.environ.get('ESPN_LEAGUE_ID')
        swid = os.environ.get('ESPN_SWID')
        s2 = os.environ.get('ESPN_S2')
        table_name = os.environ.get('DYNAMODB_TABLE_NAME')
        
        if not all([league_id, swid, s2, table_name]):
            raise ValueError("Missing required environment variables")
        
        logger.info(f"Starting ESPN scrape for league {league_id}")
        
        # Make ESPN API request - include mTeam, mRoster, and mSettings for complete data
        url = f"https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/2025/segments/0/leagues/{league_id}"
        
        cookies = {"SWID": swid, "espn_s2": s2}
        params = {"view": ["mTeam", "mRoster", "mSettings"]}
        
        response = requests.get(url, cookies=cookies, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Get league name from settings
        league_name = data.get('settings', {}).get('name', f'League {league_id}')
        
        # Get members data for owner name mapping
        members_data = data.get('members', [])
        
        # Process teams
        table = dynamodb.Table(table_name)
        teams_processed = 0
        
        for team in data.get('teams', []):
            team_data = process_team_roster(team, league_id, league_name, members_data)
            
            # Write to DynamoDB
            table.put_item(Item=team_data)
            logger.info(f"DETAILS: {team_data}")
            teams_processed += 1
            
        logger.info(f"Successfully processed {teams_processed} teams")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed {teams_processed} teams',
                'league_id': league_id,
                'league_name': league_name
            })
        }
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }