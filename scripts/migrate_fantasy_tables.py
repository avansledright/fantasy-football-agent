import boto3
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal
import json
from datetime import datetime
from typing import Dict, Any, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS Configuration
REGION = 'us-west-2'
SOURCE_PLAYERS_TABLE = 'fantasy-football-players'
SOURCE_WAIVER_TABLE = 'fantasy-football-agent-2025-waiver-table'
TARGET_TABLE = 'fantasy-football-players-updated'

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name=REGION)
source_players_table = dynamodb.Table(SOURCE_PLAYERS_TABLE)
source_waiver_table = dynamodb.Table(SOURCE_WAIVER_TABLE)
target_table = dynamodb.Table(TARGET_TABLE)


def scan_table(table) -> List[Dict]:
    """Scan entire table and return all items."""
    items = []
    response = table.scan()
    items.extend(response.get('Items', []))
    
    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))
    
    logger.info(f"Scanned {len(items)} items from {table.name}")
    return items


def extract_season_from_historical(historical_seasons: Dict) -> Dict:
    """Transform historical_seasons structure to new seasons structure."""
    seasons = {}
    
    for year, data in historical_seasons.items():
        season_data = {
            'weekly_stats': data.get('weekly_stats', {}),
            'season_totals': data.get('season_totals', {})
        }
        
        # Add team if available in season_totals
        if 'season_totals' in data and 'Player' in data['season_totals']:
            # Team info might not be in historical data, skip if not available
            pass
            
        seasons[year] = season_data
    
    return seasons


def extract_current_season_from_players(player_data: Dict) -> Dict:
    """Extract 2025 season data from the players table."""
    current_season_data = {}
    
    # Extract current season stats
    if 'current_season_stats' in player_data and '2025' in player_data['current_season_stats']:
        weekly_stats = player_data['current_season_stats']['2025']
        current_season_data['weekly_stats'] = weekly_stats
        
        # Extract team from the most recent week's data
        if weekly_stats:
            latest_week = max(weekly_stats.keys(), key=int)
            if 'team' in weekly_stats[latest_week]:
                current_season_data['team'] = weekly_stats[latest_week]['team']
    
    # Extract projections for 2025
    if 'projections' in player_data and '2025' in player_data['projections']:
        projections_2025 = player_data['projections']['2025']
        
        # Season-level projections
        season_projections = {k: v for k, v in projections_2025.items() 
                            if k not in ['weekly', 'Player']}
        if season_projections:
            current_season_data['season_projections'] = season_projections
        
        # Weekly projections
        if 'weekly' in projections_2025:
            weekly_proj = {}
            for week, data in projections_2025['weekly'].items():
                if 'fantasy_points' in data:
                    weekly_proj[week] = data['fantasy_points']
            if weekly_proj:
                current_season_data['weekly_projections'] = weekly_proj
    
    return current_season_data


def merge_waiver_data(season_data: Dict, waiver_data: Dict) -> Dict:
    """Merge waiver table data into season data for 2025."""
    # Add waiver-specific fields
    if 'team' in waiver_data:
        season_data['team'] = waiver_data['team']
    if 'pro_team_id' in waiver_data:
        season_data['pro_team_id'] = waiver_data['pro_team_id']
    if 'jersey_number' in waiver_data:
        season_data['jersey_number'] = waiver_data['jersey_number']
    if 'injury_status' in waiver_data:
        season_data['injury_status'] = waiver_data['injury_status']
    if 'percent_owned' in waiver_data:
        season_data['percent_owned'] = waiver_data['percent_owned']
    
    # Add weekly outlooks
    if 'weekly_outlooks' in waiver_data:
        season_data['weekly_outlooks'] = waiver_data['weekly_outlooks']
    
    # Merge weekly projections (waiver table might have more recent ones)
    if 'weekly_projections' in waiver_data:
        if 'weekly_projections' not in season_data:
            season_data['weekly_projections'] = {}
        
        # Convert to dict if needed and merge
        waiver_proj = waiver_data['weekly_projections']
        if isinstance(waiver_proj, dict):
            for week, points in waiver_proj.items():
                season_data['weekly_projections'][str(week)] = points
    
    return season_data


def consolidate_player_data(player_data: Dict, waiver_data: Dict = None) -> Dict:
    """Consolidate player data from both sources into new structure."""
    consolidated = {
        'player_id': player_data['player_id'],
        'player_name': player_data['player_name'],
        'position': player_data['position'],
        'updated_at': datetime.utcnow().isoformat()
    }
    
    # Add ESPN player ID if available from waiver data
    if waiver_data and 'espn_player_id' in waiver_data:
        consolidated['espn_player_id'] = waiver_data['espn_player_id']
    
    # Initialize seasons dict
    seasons = {}
    
    # Add historical seasons
    if 'historical_seasons' in player_data:
        historical = extract_season_from_historical(player_data['historical_seasons'])
        seasons.update(historical)
    
    # Add current season (2025) data
    current_season = extract_current_season_from_players(player_data)
    if current_season:
        seasons['2025'] = current_season
    
    # Merge waiver data into 2025 season if available
    if waiver_data:
        if '2025' not in seasons:
            seasons['2025'] = {}
        seasons['2025'] = merge_waiver_data(seasons['2025'], waiver_data)
    
    consolidated['seasons'] = seasons
    
    return consolidated


def batch_write_items(items: List[Dict], batch_size: int = 25):
    """Write items to target table in batches."""
    total_items = len(items)
    logger.info(f"Starting batch write of {total_items} items")
    
    for i in range(0, total_items, batch_size):
        batch = items[i:i + batch_size]
        
        with target_table.batch_writer() as writer:
            for item in batch:
                try:
                    writer.put_item(Item=item)
                except Exception as e:
                    logger.error(f"Error writing item {item.get('player_id')}: {str(e)}")
        
        logger.info(f"Wrote batch {i//batch_size + 1}/{(total_items + batch_size - 1)//batch_size}")


def migrate_data():
    """Main migration function."""
    logger.info("Starting data migration...")
    
    # Step 1: Scan both source tables
    logger.info(f"Scanning {SOURCE_PLAYERS_TABLE}...")
    players_data = scan_table(source_players_table)
    
    logger.info(f"Scanning {SOURCE_WAIVER_TABLE}...")
    waiver_data = scan_table(source_waiver_table)
    
    # Step 2: Create lookup map for waiver data by player name
    waiver_lookup = {}
    for item in waiver_data:
        player_name = item.get('player_name')
        if player_name:
            waiver_lookup[player_name] = item
    
    logger.info(f"Created waiver lookup with {len(waiver_lookup)} players")
    
    # Step 3: Consolidate data
    consolidated_items = []
    players_with_waiver_data = 0
    players_without_waiver_data = 0
    
    for player in players_data:
        player_name = player.get('player_name')
        waiver_info = waiver_lookup.get(player_name)
        
        if waiver_info:
            players_with_waiver_data += 1
        else:
            players_without_waiver_data += 1
        
        consolidated = consolidate_player_data(player, waiver_info)
        consolidated_items.append(consolidated)
    
    logger.info(f"Consolidated {len(consolidated_items)} players")
    logger.info(f"  - {players_with_waiver_data} with waiver data")
    logger.info(f"  - {players_without_waiver_data} without waiver data")
    
    # Step 4: Check for players only in waiver table
    players_only_in_waiver = []
    for waiver_player_name, waiver_item in waiver_lookup.items():
        # Check if this player is in the consolidated items
        found = any(item['player_name'] == waiver_player_name for item in consolidated_items)
        if not found:
            players_only_in_waiver.append(waiver_item)
    
    if players_only_in_waiver:
        logger.warning(f"Found {len(players_only_in_waiver)} players only in waiver table:")
        for wp in players_only_in_waiver[:5]:  # Show first 5
            logger.warning(f"  - {wp.get('player_name')} ({wp.get('position')})")
        
        # Create minimal entries for these players
        for waiver_item in players_only_in_waiver:
            player_name = waiver_item['player_name']
            position = waiver_item['position']
            player_id = f"{player_name}#{position}"
            
            consolidated = {
                'player_id': player_id,
                'player_name': player_name,
                'position': position,
                'updated_at': datetime.utcnow().isoformat(),
                'seasons': {
                    '2025': merge_waiver_data({}, waiver_item)
                }
            }
            
            if 'espn_player_id' in waiver_item:
                consolidated['espn_player_id'] = waiver_item['espn_player_id']
            
            consolidated_items.append(consolidated)
        
        logger.info(f"Added {len(players_only_in_waiver)} players from waiver table only")
    
    # Step 5: Write to target table
    logger.info(f"Writing {len(consolidated_items)} items to {TARGET_TABLE}...")
    batch_write_items(consolidated_items)
    
    logger.info("Migration completed successfully!")
    logger.info(f"Total players migrated: {len(consolidated_items)}")
    
    return {
        'total_migrated': len(consolidated_items),
        'with_waiver_data': players_with_waiver_data,
        'without_waiver_data': players_without_waiver_data,
        'waiver_only': len(players_only_in_waiver)
    }


def verify_migration(sample_size: int = 5):
    """Verify migration by checking a few random records."""
    logger.info(f"\nVerifying migration with {sample_size} sample records...")
    
    response = target_table.scan(Limit=sample_size)
    items = response.get('Items', [])
    
    for item in items:
        logger.info(f"\nPlayer: {item['player_name']} ({item['position']})")
        logger.info(f"  Player ID: {item['player_id']}")
        logger.info(f"  Seasons: {list(item.get('seasons', {}).keys())}")
        
        if '2025' in item.get('seasons', {}):
            season_2025 = item['seasons']['2025']
            logger.info(f"  2025 Data:")
            logger.info(f"    - Team: {season_2025.get('team', 'N/A')}")
            logger.info(f"    - Injury Status: {season_2025.get('injury_status', 'N/A')}")
            logger.info(f"    - Percent Owned: {season_2025.get('percent_owned', 'N/A')}")
            logger.info(f"    - Weekly Stats: {len(season_2025.get('weekly_stats', {}))} weeks")
            logger.info(f"    - Weekly Projections: {len(season_2025.get('weekly_projections', {}))} weeks")


if __name__ == "__main__":
    try:
        # Run migration
        stats = migrate_data()
        
        # Print summary
        print("\n" + "="*60)
        print("MIGRATION SUMMARY")
        print("="*60)
        print(f"Total Players Migrated: {stats['total_migrated']}")
        print(f"  - With Waiver Data: {stats['with_waiver_data']}")
        print(f"  - Without Waiver Data: {stats['without_waiver_data']}")
        print(f"  - Waiver Only: {stats['waiver_only']}")
        print("="*60)
        
        # Verify migration
        verify_migration()
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}", exc_info=True)
        raise