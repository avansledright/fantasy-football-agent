import boto3
import json
from decimal import Decimal
import logging
from migrate_fantasy_tables import (
    REGION, SOURCE_PLAYERS_TABLE, SOURCE_WAIVER_TABLE,
    scan_table, consolidate_player_data
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb', region_name=REGION)
source_players_table = dynamodb.Table(SOURCE_PLAYERS_TABLE)
source_waiver_table = dynamodb.Table(SOURCE_WAIVER_TABLE)


class DecimalEncoder(json.JSONEncoder):
    """Helper class to convert DynamoDB Decimal types to JSON."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


def preview_migration(num_samples: int = 3):
    """Preview the migration without writing to database."""
    logger.info("Starting dry-run preview...")
    
    # Scan both source tables
    logger.info(f"Scanning {SOURCE_PLAYERS_TABLE}...")
    players_data = scan_table(source_players_table)
    
    logger.info(f"Scanning {SOURCE_WAIVER_TABLE}...")
    waiver_data = scan_table(source_waiver_table)
    
    # Create waiver lookup
    waiver_lookup = {}
    for item in waiver_data:
        player_name = item.get('player_name')
        if player_name:
            waiver_lookup[player_name] = item
    
    # Sample different types of players
    samples = []
    
    # 1. Player with waiver data
    for player in players_data:
        if player['player_name'] in waiver_lookup and len(samples) < num_samples:
            samples.append(('with_waiver', player, waiver_lookup[player['player_name']]))
            if len(samples) >= num_samples:
                break
    
    # 2. Player without waiver data
    for player in players_data:
        if player['player_name'] not in waiver_lookup and len(samples) < num_samples * 2:
            samples.append(('without_waiver', player, None))
            if len(samples) >= num_samples * 2:
                break
    
    # Display preview
    print("\n" + "="*80)
    print("DRY RUN - DATA TRANSFORMATION PREVIEW")
    print("="*80)
    
    for i, (sample_type, player, waiver) in enumerate(samples, 1):
        print(f"\n{'='*80}")
        print(f"SAMPLE {i}: {player['player_name']} ({sample_type.replace('_', ' ').title()})")
        print(f"{'='*80}")
        
        # Show original data
        print("\n--- ORIGINAL PLAYER DATA ---")
        print(json.dumps(player, indent=2, cls=DecimalEncoder)[:1000] + "...")
        
        if waiver:
            print("\n--- ORIGINAL WAIVER DATA ---")
            print(json.dumps(waiver, indent=2, cls=DecimalEncoder)[:1000] + "...")
        
        # Show consolidated data
        consolidated = consolidate_player_data(player, waiver)
        
        print("\n--- CONSOLIDATED DATA (NEW STRUCTURE) ---")
        print(json.dumps(consolidated, indent=2, cls=DecimalEncoder))
        
        # Highlight key fields
        print("\n--- KEY FIELDS SUMMARY ---")
        print(f"Player ID: {consolidated['player_id']}")
        print(f"Player Name: {consolidated['player_name']}")
        print(f"Position: {consolidated['position']}")
        print(f"ESPN ID: {consolidated.get('espn_player_id', 'N/A')}")
        print(f"Seasons Available: {list(consolidated['seasons'].keys())}")
        
        if '2025' in consolidated['seasons']:
            s2025 = consolidated['seasons']['2025']
            print(f"\n2025 Season Data:")
            print(f"  - Team: {s2025.get('team', 'N/A')}")
            print(f"  - Injury Status: {s2025.get('injury_status', 'N/A')}")
            print(f"  - Percent Owned: {s2025.get('percent_owned', 'N/A')}")
            print(f"  - Weekly Stats: {len(s2025.get('weekly_stats', {}))} weeks")
            print(f"  - Weekly Projections: {len(s2025.get('weekly_projections', {}))} weeks")
            print(f"  - Weekly Outlooks: {len(s2025.get('weekly_outlooks', {}))} weeks")
            print(f"  - Has Season Projections: {'Yes' if 'season_projections' in s2025 else 'No'}")
        
        if '2024' in consolidated['seasons']:
            s2024 = consolidated['seasons']['2024']
            print(f"\n2024 Season Data:")
            print(f"  - Weekly Stats: {len(s2024.get('weekly_stats', {}))} weeks")
            print(f"  - Has Season Totals: {'Yes' if 'season_totals' in s2024 else 'No'}")
    
    # Statistics
    print("\n" + "="*80)
    print("MIGRATION STATISTICS")
    print("="*80)
    print(f"Total Players in Source: {len(players_data)}")
    print(f"Total Players in Waiver: {len(waiver_data)}")
    
    players_with_waiver = sum(1 for p in players_data if p['player_name'] in waiver_lookup)
    players_without_waiver = len(players_data) - players_with_waiver
    
    print(f"Players with Waiver Data: {players_with_waiver}")
    print(f"Players without Waiver Data: {players_without_waiver}")
    
    # Check for waiver-only players
    waiver_only = []
    for waiver_name in waiver_lookup.keys():
        found = any(p['player_name'] == waiver_name for p in players_data)
        if not found:
            waiver_only.append(waiver_name)
    
    if waiver_only:
        print(f"\nPlayers ONLY in Waiver Table: {len(waiver_only)}")
        print("Sample names:")
        for name in waiver_only[:5]:
            print(f"  - {name}")
    
    print("\n" + "="*80)
    print("Dry run complete. Review the output above.")
    print("If everything looks good, run migrate_fantasy_tables.py to perform actual migration.")
    print("="*80 + "\n")


if __name__ == "__main__":
    try:
        preview_migration(num_samples=3)
    except Exception as e:
        logger.error(f"Dry run failed: {str(e)}", exc_info=True)
        raise