#!/usr/bin/env python3
import json
import boto3
from decimal import Decimal
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import os

# Configuration
COMBINED_DATA_DIR = Path("combined")
POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"]
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE']
AWS_REGION = os.environ['AWS_REGION']  # Change as needed

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def convert_floats_to_decimal(obj: Any) -> Any:
    """
    Recursively convert float values to Decimal for DynamoDB compatibility.
    DynamoDB doesn't support native float types.
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: convert_floats_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_floats_to_decimal(item) for item in obj]
    else:
        return obj

def clean_percentage_string(value: Any) -> Any:
    """
    Convert percentage strings like "99.3%" to Decimal values like 99.3
    """
    if isinstance(value, str) and value.endswith('%'):
        try:
            return Decimal(value[:-1])
        except:
            return value
    return value

def clean_player_data(player_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean and prepare player data for DynamoDB insertion.
    """
    cleaned = {}
    
    for key, value in player_data.items():
        if isinstance(value, dict):
            # Recursively clean nested dictionaries
            cleaned_dict = {}
            for nested_key, nested_value in value.items():
                cleaned_dict[nested_key] = clean_percentage_string(nested_value)
            cleaned[key] = convert_floats_to_decimal(cleaned_dict)
        else:
            cleaned[key] = convert_floats_to_decimal(clean_percentage_string(value))
    
    return cleaned

def create_dynamodb_item(player_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform the combined player data into the DynamoDB item format.
    """
    player_name = player_data.get("Player", "Unknown")
    position = player_data.get("POSITION", "UNK")
    
    # Create the composite primary key
    player_id = f"{player_name}#{position}"
    
    # Build the DynamoDB item
    item = {
        "player_id": player_id,
        "Player": player_name,
        "POSITION": position
    }
    
    # Add 2024 actuals if present
    if "2024_actuals" in player_data:
        item["2024_actuals"] = player_data["2024_actuals"]
    
    # Add 2025 projections if present
    if "2025_projection" in player_data:
        item["2025_projection"] = player_data["2025_projection"]
    
    # Clean the data for DynamoDB
    return clean_player_data(item)

def load_combined_data(position: str) -> Optional[list]:
    """
    Load combined data for a specific position.
    """
    file_path = COMBINED_DATA_DIR / f"{position}.json"
    
    if not file_path.exists():
        logger.warning(f"File not found: {file_path}")
        return None
    
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        logger.info(f"Loaded {len(data)} players for position {position}")
        return data
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return None

def create_dynamodb_table(dynamodb_resource, table_name: str):
    """
    Create the DynamoDB table if it doesn't exist.
    """
    try:
        # Check if table exists
        table = dynamodb_resource.Table(table_name)
        table.load()
        logger.info(f"Table {table_name} already exists")
        return table
    except dynamodb_resource.meta.client.exceptions.ResourceNotFoundException:
        logger.info(f"Creating table {table_name}")
        
        table = dynamodb_resource.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    'AttributeName': 'player_id',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'player_id',
                    'AttributeType': 'S'
                }
            ],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Wait for table to be created
        table.wait_until_exists()
        logger.info(f"Table {table_name} created successfully")
        return table

def upload_players_to_dynamodb(players_data: list, table) -> tuple[int, int]:
    """
    Upload player data to DynamoDB using batch writing for efficiency.
    Returns tuple of (successful_uploads, failed_uploads).
    """
    successful_uploads = 0
    failed_uploads = 0
    
    # Process players in batches of 25 (DynamoDB batch limit)
    batch_size = 25
    
    for i in range(0, len(players_data), batch_size):
        batch = players_data[i:i + batch_size]
        
        with table.batch_writer() as batch_writer:
            for player_data in batch:
                try:
                    item = create_dynamodb_item(player_data)
                    batch_writer.put_item(Item=item)
                    successful_uploads += 1
                    
                    if successful_uploads % 50 == 0:
                        logger.info(f"Uploaded {successful_uploads} players...")
                        
                except Exception as e:
                    logger.error(f"Error uploading player {player_data.get('Player', 'Unknown')}: {e}")
                    failed_uploads += 1
    
    return successful_uploads, failed_uploads

def main():
    """
    Main function to load all combined data and upload to DynamoDB.
    """
    logger.info("Starting DynamoDB upload process...")
    
    # Initialize DynamoDB resource
    try:
        dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
        table = create_dynamodb_table(dynamodb, DYNAMODB_TABLE_NAME)
    except Exception as e:
        logger.error(f"Error connecting to DynamoDB: {e}")
        logger.error("Make sure AWS credentials are configured and the region is correct")
        return
    
    total_successful = 0
    total_failed = 0
    
    # Process each position
    for position in POSITIONS:
        logger.info(f"Processing position: {position}")
        
        players_data = load_combined_data(position)
        if not players_data:
            logger.warning(f"No data found for position {position}")
            continue
        
        successful, failed = upload_players_to_dynamodb(players_data, table)
        total_successful += successful
        total_failed += failed
        
        logger.info(f"Position {position}: {successful} successful, {failed} failed")
    
    logger.info(f"Upload complete!")
    logger.info(f"Total successful uploads: {total_successful}")
    logger.info(f"Total failed uploads: {total_failed}")
    
    if total_failed > 0:
        logger.warning(f"There were {total_failed} failed uploads. Check the logs above for details.")

if __name__ == "__main__":
    main()