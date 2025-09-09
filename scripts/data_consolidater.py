import boto3
from decimal import Decimal
from collections import defaultdict
import json
from datetime import datetime

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)
def convert_floats_to_decimal(obj):
    """Recursively convert float values to Decimal for DynamoDB compatibility"""
    if isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(v) for v in obj]
    elif isinstance(obj, float):
        return Decimal(str(obj))
    else:
        return obj
    
def consolidate_fantasy_football_data():
    """
    Consolidates data from multiple DynamoDB tables into a single unified table
    """
    dynamodb = boto3.resource('dynamodb')
    
    # Source tables
    player_data_table = dynamodb.Table('2025-2026-fantasy-football-player-data')
    stats_2024_table = dynamodb.Table('fantasy-football-2024-stats')
    stats_2025_table = dynamodb.Table('fantasy-football-2025-stats')
    
    # Destination table
    consolidated_table = dynamodb.Table('fantasy-football-players')
    
    print("Starting data consolidation...")
    
    # Step 1: Get all player data (projections and 2024 actuals)
    print("Fetching player projection data...")
    player_data = {}
    
    response = player_data_table.scan()
    for item in response['Items']:
        player_id = item['player_id']
        player_data[player_id] = {
            'player_id': player_id,
            'player_name': item['Player'],
            'position': item['POSITION'],
            'historical_seasons': {},
            'projections': {},
            'current_season_stats': {}
        }
        
        # Add 2024 actuals if present
        if '2024_actuals' in item:
            player_data[player_id]['historical_seasons']['2024'] = {
                'season_totals': item['2024_actuals']
            }
        
        # Add 2025 projections if present
        if '2025_projection' in item:
            player_data[player_id]['projections']['2025'] = item['2025_projection']
    
    # Handle pagination if needed
    while 'LastEvaluatedKey' in response:
        response = player_data_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        for item in response['Items']:
            # Convert the entire item to ensure all floats become Decimals
            item = convert_floats_to_decimal(item)
            
            player_id = item['player_id']
            if player_id not in player_data:
                player_data[player_id] = {
                    'player_id': player_id,
                    'player_name': item['Player'],
                    'position': item['POSITION'],
                    'historical_seasons': {},
                    'projections': {},
                    'current_season_stats': {}
                }
            
            if '2024_actuals' in item:
                player_data[player_id]['historical_seasons']['2024'] = {
                    'season_totals': item['2024_actuals']
                }
            
            if '2025_projection' in item:
                player_data[player_id]['projections']['2025'] = item['2025_projection']
    
    print(f"Loaded {len(player_data)} players from projection data")
    
    # Step 2: Add 2024 weekly stats
    print("Fetching 2024 weekly stats...")
    weekly_stats_2024 = defaultdict(dict)
    
    response = stats_2024_table.scan()
    for item in response['Items']:
        player_name = item['player_name']
        position = item['position']
        player_id = f"{player_name}#{position}"
        week = str(item['week'])
        
        weekly_stats_2024[player_id][week] = {
            'fantasy_points': float(item['fantasy_points']),
            'opponent': item['opponent']
        }
    
    # Handle pagination for 2024 stats
    while 'LastEvaluatedKey' in response:
        response = stats_2024_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        for item in response['Items']:
            player_name = item['player_name']
            position = item['position']
            player_id = f"{player_name}#{position}"
            week = str(item['week'])
            
            weekly_stats_2024[player_id][week] = {
                'fantasy_points': float(item['fantasy_points']),
                'opponent': item['opponent']
            }
    
    print(f"Loaded weekly stats for {len(weekly_stats_2024)} players from 2024")
    
    # Step 3: Add 2025 weekly stats
    print("Fetching 2025 weekly stats...")
    weekly_stats_2025 = defaultdict(dict)
    
    response = stats_2025_table.scan()
    for item in response['Items']:
        player_name = item['player_name']
        position = item['position']
        player_id = f"{player_name}#{position}"
        week = str(item['week'])
        
        weekly_stats_2025[player_id][week] = {
            'fantasy_points': float(item['fantasy_points']),
            'opponent': item['opponent'],
            'team': item.get('team', ''),
            'updated_at': item.get('updated_at', '')
        }
    
    # Handle pagination for 2025 stats
    while 'LastEvaluatedKey' in response:
        response = stats_2025_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        for item in response['Items']:
            player_name = item['player_name']
            position = item['position']
            player_id = f"{player_name}#{position}"
            week = str(item['week'])
            
            weekly_stats_2025[player_id][week] = {
                'fantasy_points': float(item['fantasy_points']),
                'opponent': item['opponent'],
                'team': item.get('team', ''),
                'updated_at': item.get('updated_at', '')
            }
    
    print(f"Loaded weekly stats for {len(weekly_stats_2025)} players from 2025")
    
    # Step 4: Merge weekly stats into player data
    print("Merging weekly stats...")
    
    # Add 2024 weekly stats
    for player_id, weeks in weekly_stats_2024.items():
        if player_id not in player_data:
            # Create new player entry if not found in projection data
            parts = player_id.split('#')
            player_data[player_id] = {
                'player_id': player_id,
                'player_name': parts[0] if len(parts) > 0 else '',
                'position': parts[1] if len(parts) > 1 else '',
                'historical_seasons': {},
                'projections': {},
                'current_season_stats': {}
            }
        
        if '2024' not in player_data[player_id]['historical_seasons']:
            player_data[player_id]['historical_seasons']['2024'] = {}
        
        player_data[player_id]['historical_seasons']['2024']['weekly_stats'] = weeks
    
    # Add 2025 weekly stats
    for player_id, weeks in weekly_stats_2025.items():
        if player_id not in player_data:
            # Create new player entry if not found in projection data
            parts = player_id.split('#')
            player_data[player_id] = {
                'player_id': player_id,
                'player_name': parts[0] if len(parts) > 0 else '',
                'position': parts[1] if len(parts) > 1 else '',
                'historical_seasons': {},
                'projections': {},
                'current_season_stats': {}
            }
        
        player_data[player_id]['current_season_stats']['2025'] = weeks
    
    # Step 5: Write consolidated data to new table
    print("Writing consolidated data to new table...")
    
    with consolidated_table.batch_writer() as batch:
        count = 0
        for player_id, data in player_data.items():
            # Convert any float objects to Decimal for DynamoDB compatibility
            clean_data = convert_floats_to_decimal(data)
            
            try:
                batch.put_item(Item=clean_data)
                count += 1
                
                if count % 100 == 0:
                    print(f"Processed {count} players...")
                    
            except Exception as e:
                print(f"Error writing player {player_id}: {e}")
                continue
    
    print(f"Successfully consolidated {count} players into new table")
    
    # Step 6: Verify data integrity
    print("Verifying data integrity...")
    
    response = consolidated_table.scan(Select='COUNT')
    final_count = response['Count']
    
    print(f"Final verification: {final_count} items in consolidated table")
    print("Data consolidation complete!")
    
    return {
        'total_players_processed': count,
        'final_table_count': final_count,
        'completion_time': datetime.now().isoformat()
    }

if __name__ == "__main__":
    try:
        result = consolidate_fantasy_football_data()
        print(f"\nConsolidation Summary:")
        print(f"- Total players processed: {result['total_players_processed']}")
        print(f"- Final table count: {result['final_table_count']}")
        print(f"- Completed at: {result['completion_time']}")
        
    except Exception as e:
        print(f"Error during consolidation: {e}")
        raise