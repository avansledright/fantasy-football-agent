import json
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from decimal import Decimal
import os
import sys
from typing import Dict, List, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FantasyFootballImporter:
    def __init__(self, table_name: str, region_name: str = 'us-west-2'):
        """
        Initialize the DynamoDB importer
        
        Args:
            table_name: Name of the DynamoDB table
            region_name: AWS region name
        """
        self.table_name = table_name
        self.dynamodb = boto3.resource('dynamodb', region_name=region_name)
        self.table = self.dynamodb.Table(table_name)
        
    def create_table_if_not_exists(self):
        """
        Create DynamoDB table if it doesn't exist
        Schema:
        - Primary Key: player_season (player_name#season)
        - Sort Key: week
        - GSI: position-season-index (position as PK, season as SK)
        """
        try:
            # Check if table exists
            self.table.load()
            logger.info(f"Table {self.table_name} already exists")
            return
        except ClientError as e:
            if e.response['Error']['Code'] != 'ResourceNotFoundException':
                raise
        
        # Create table
        logger.info(f"Creating table {self.table_name}...")
        
        table = self.dynamodb.create_table(
            TableName=self.table_name,
            KeySchema=[
                {
                    'AttributeName': 'player_season',
                    'KeyType': 'HASH'  # Partition key
                },
                {
                    'AttributeName': 'week',
                    'KeyType': 'RANGE'  # Sort key
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'player_season',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'week',
                    'AttributeType': 'N'
                },
                {
                    'AttributeName': 'position',
                    'AttributeType': 'S'
                },
                {
                    'AttributeName': 'season',
                    'AttributeType': 'N'
                }
            ],
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'position-season-index',
                    'KeySchema': [
                        {
                            'AttributeName': 'position',
                            'KeyType': 'HASH'
                        },
                        {
                            'AttributeName': 'season',
                            'KeyType': 'RANGE'
                        }
                    ],
                    'Projection': {
                        'ProjectionType': 'ALL'
                    },
                    'ProvisionedThroughput': {
                        'ReadCapacityUnits': 5,
                        'WriteCapacityUnits': 5
                    }
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 10,
                'WriteCapacityUnits': 10
            }
        )
        
        # Wait for table to be created
        table.wait_until_exists()
        logger.info(f"Table {self.table_name} created successfully")
    
    def convert_floats_to_decimal(self, obj: Any) -> Any:
        """Convert float values to Decimal for DynamoDB compatibility"""
        if isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, dict):
            return {k: self.convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_floats_to_decimal(v) for v in obj]
        return obj
    
    def process_json_file(self, file_path: str) -> List[Dict]:
        """
        Process a single JSON file and return list of items for DynamoDB
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            List of items formatted for DynamoDB
        """
        logger.info(f"Processing file: {file_path}")
        
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        position = data['position']
        season = data['season']
        players = data['players']
        
        items = []
        
        for player_name, weeks_data in players.items():
            for week_data in weeks_data:
                item = {
                    'player_season': f"{player_name}#{season}",
                    'week': week_data['week'],
                    'player_name': player_name,
                    'position': position,
                    'season': season,
                    'opponent': week_data['opponent'],
                    'fantasy_points': week_data['fantasy_points']
                }
                
                # Convert floats to Decimal
                item = self.convert_floats_to_decimal(item)
                items.append(item)
        
        logger.info(f"Processed {len(items)} records from {file_path}")
        return items
    
    def batch_write_items(self, items: List[Dict]):
        """
        Write items to DynamoDB in batches of 25 (DynamoDB limit)
        
        Args:
            items: List of items to write
        """
        batch_size = 25
        total_items = len(items)
        successful_writes = 0
        
        for i in range(0, total_items, batch_size):
            batch = items[i:i + batch_size]
            
            try:
                with self.table.batch_writer() as batch_writer:
                    for item in batch:
                        batch_writer.put_item(Item=item)
                
                successful_writes += len(batch)
                logger.info(f"Successfully wrote batch {i//batch_size + 1} "
                           f"({len(batch)} items). Total: {successful_writes}/{total_items}")
                
            except ClientError as e:
                logger.error(f"Error writing batch {i//batch_size + 1}: {e}")
                raise
    
    def import_file(self, file_path: str):
        """
        Import a single JSON file into DynamoDB
        
        Args:
            file_path: Path to the JSON file
        """
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return False
        
        try:
            items = self.process_json_file(file_path)
            if items:
                self.batch_write_items(items)
                logger.info(f"Successfully imported {len(items)} records from {file_path}")
                return True
            else:
                logger.warning(f"No items found in {file_path}")
                return False
                
        except Exception as e:
            logger.error(f"Error importing {file_path}: {e}")
            return False
    
    def import_multiple_files(self, file_paths: List[str]):
        """
        Import multiple JSON files into DynamoDB
        
        Args:
            file_paths: List of file paths to import
        """
        total_success = 0
        total_files = len(file_paths)
        
        for file_path in file_paths:
            if self.import_file(file_path):
                total_success += 1
        
        logger.info(f"Import completed: {total_success}/{total_files} files imported successfully")


def main():
    """Main function to run the import process"""
    # Configuration
    TABLE_NAME = "fantasy-football-2024-stats"  # Change this to your desired table name
    REGION_NAME = "us-west-2"  # Change this to your AWS region
    
    # List of files to import (modify as needed)
    FILES_TO_IMPORT = [
        "historical_data/qb.json",
        "historical_data/rb.json", 
        "historical_data/wr.json",
        "historical_data/te.json"
    ]
    
    try:
        # Initialize importer
        importer = FantasyFootballImporter(TABLE_NAME, REGION_NAME)
        
        # Create table if it doesn't exist
        importer.create_table_if_not_exists()
        
        # Filter files that actually exist
        existing_files = [f for f in FILES_TO_IMPORT if os.path.exists(f)]
        
        if not existing_files:
            logger.error("No JSON files found. Please ensure the files exist in the current directory.")
            sys.exit(1)
        
        logger.info(f"Found {len(existing_files)} files to import: {existing_files}")
        
        # Import all files
        importer.import_multiple_files(existing_files)
        
        logger.info("Import process completed!")
        
    except BotoCoreError as e:
        logger.error(f"AWS configuration error: {e}")
        logger.error("Please ensure AWS credentials are configured properly")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()