import boto3
import json
import logging
from botocore.exceptions import ClientError
from typing import Dict, List
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize DynamoDB
dynamodb = boto3.resource('dynamodb')
table_name = os.environ.get('DYNAMODB_TABLE_NAME', 'fantasy-football-players')
table = dynamodb.Table(table_name)

def cleanup_week_2_stats():
    """
    Remove week 2 stats from current_season_stats/2025 for all players.
    Leaves all other data intact.
    """
    try:
        logger.info("Starting cleanup of week 2 stats from DynamoDB...")
        
        # Scan the entire table
        scan_kwargs = {}
        processed_count = 0
        updated_count = 0
        
        while True:
            response = table.scan(**scan_kwargs)
            items = response.get('Items', [])
            
            logger.info(f"Processing batch of {len(items)} items...")
            
            for item in items:
                try:
                    if cleanup_item_week_2_stats(item):
                        updated_count += 1
                    processed_count += 1
                    
                    if processed_count % 100 == 0:
                        logger.info(f"Processed {processed_count} items, updated {updated_count}")
                        
                except Exception as e:
                    logger.error(f"Error processing item {item.get('player_id', 'unknown')}: {e}")
                    continue
            
            # Check if there are more items to scan
            if 'LastEvaluatedKey' not in response:
                break
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        
        logger.info(f"Cleanup completed. Processed {processed_count} total items, updated {updated_count} items")
        return {
            'processed': processed_count,
            'updated': updated_count
        }
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        raise


def cleanup_item_week_2_stats(item: Dict) -> bool:
    """
    Check if item has week 2 stats and remove them.
    Returns True if item was updated, False otherwise.
    """
    try:
        player_id = item.get('player_id')
        
        # Check if item has current_season_stats
        if 'current_season_stats' not in item:
            logger.debug(f"No current_season_stats for {player_id}")
            return False
        
        current_stats = item['current_season_stats']
        
        # Check if 2025 season exists
        if '2025' not in current_stats:
            logger.debug(f"No 2025 season for {player_id}")
            return False
        
        season_2025 = current_stats['2025']
        
        # Check if week 2 exists
        if '2' not in season_2025:
            logger.debug(f"No week 2 stats for {player_id}")
            return False
        
        # Week 2 exists - remove it
        week_2_data = season_2025['2']
        logger.info(f"Removing week 2 stats for {player_id}: {week_2_data}")
        
        # Remove week 2 from the item
        del season_2025['2']
        
        # Update the item in DynamoDB
        try:
            table.put_item(Item=item)
            logger.info(f"Successfully removed week 2 stats for {player_id}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to update {player_id} in DynamoDB: {e}")
            return False
        
    except Exception as e:
        logger.error(f"Error processing item {item.get('player_id', 'unknown')}: {e}")
        return False


def dry_run_cleanup():
    """
    Perform a dry run to see what would be cleaned up without actually making changes.
    """
    try:
        logger.info("Starting DRY RUN of week 2 cleanup...")
        
        scan_kwargs = {}
        processed_count = 0
        items_with_week_2 = []
        
        while True:
            response = table.scan(**scan_kwargs)
            items = response.get('Items', [])
            
            for item in items:
                try:
                    player_id = item.get('player_id')
                    processed_count += 1
                    
                    # Check if item has week 2 stats
                    if (item.get('current_season_stats', {})
                        .get('2025', {})
                        .get('2')):
                        
                        week_2_data = item['current_season_stats']['2025']['2']
                        items_with_week_2.append({
                            'player_id': player_id,
                            'player_name': item.get('player_name'),
                            'position': item.get('position'),
                            'fantasy_points': week_2_data.get('fantasy_points'),
                            'team': week_2_data.get('team'),
                            'opponent': week_2_data.get('opponent')
                        })
                        
                except Exception as e:
                    logger.error(f"Error checking item {item.get('player_id', 'unknown')}: {e}")
                    continue
            
            if 'LastEvaluatedKey' not in response:
                break
            scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        
        logger.info(f"DRY RUN completed. Processed {processed_count} items.")
        logger.info(f"Found {len(items_with_week_2)} items with week 2 stats that would be removed:")
        
        for item in items_with_week_2[:10]:  # Show first 10
            logger.info(f"  - {item['player_id']}: {item['fantasy_points']} pts vs {item['opponent']}")
        
        if len(items_with_week_2) > 10:
            logger.info(f"  ... and {len(items_with_week_2) - 10} more items")
        
        return items_with_week_2
        
    except Exception as e:
        logger.error(f"Error during dry run: {e}")
        raise


def lambda_handler(event, context):
    """
    Lambda handler for the cleanup script.
    Set event['dry_run'] = True to perform a dry run.
    """
    try:
        is_dry_run = event.get('dry_run', False) if isinstance(event, dict) else False
        
        if is_dry_run:
            logger.info("Performing DRY RUN...")
            items_to_clean = dry_run_cleanup()
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Dry run completed successfully',
                    'items_found': len(items_to_clean),
                    'dry_run': True
                })
            }
        else:
            logger.info("Performing ACTUAL CLEANUP...")
            result = cleanup_week_2_stats()
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Cleanup completed successfully',
                    'processed': result['processed'],
                    'updated': result['updated'],
                    'dry_run': False
                })
            }
            
    except Exception as e:
        logger.error(f"Lambda handler error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


if __name__ == "__main__":
    """
    Run locally for testing
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up week 2 stats from DynamoDB')
    parser.add_argument('--dry-run', action='store_true', help='Perform dry run without making changes')
    parser.add_argument('--table-name', default='fantasy-football-players', help='DynamoDB table name')
    
    args = parser.parse_args()
    
    # Set table name if provided
    if args.table_name:
        table_name = args.table_name
        table = dynamodb.Table(table_name)
    
    if args.dry_run:
        print("Performing dry run...")
        items = dry_run_cleanup()
        print(f"\nFound {len(items)} items with week 2 stats that would be removed.")
    else:
        confirm = input("This will permanently delete week 2 stats. Are you sure? (yes/no): ")
        if confirm.lower() == 'yes':
            result = cleanup_week_2_stats()
            print(f"\nCleanup completed: {result['updated']} items updated out of {result['processed']} processed")
        else:
            print("Cleanup cancelled.")