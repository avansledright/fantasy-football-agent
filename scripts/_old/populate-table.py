#!/usr/bin/env python3
"""
Fantasy Football Data Loader for DynamoDB
Loads data from hvpkod/NFL-Data GitHub repository JSON files
"""

import boto3
import requests
import json
import time
import pandas as pd
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional
import argparse
from botocore.exceptions import ClientError

# Configuration
TABLE_NAME = "2025-2026-fantasy-football-player-data"
REGION = "us-west-2"

class FantasyDataLoader:
    def __init__(self, table_name: str = TABLE_NAME, region: str = REGION):
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name
        
    def clear_table(self) -> bool:
        """Delete all items from the DynamoDB table."""
        print(f"🗑️  Clearing table: {self.table_name}")
        
        try:
            # Get table info
            response = self.table.meta.client.describe_table(TableName=self.table_name)
            key_schema = response['Table']['KeySchema']
            
            # Extract key names
            key_names = [key['AttributeName'] for key in key_schema]
            print(f"📋 Table keys: {key_names}")
            
            # Scan and delete all items
            scan_kwargs = {}
            deleted_count = 0
            
            while True:
                response = self.table.scan(**scan_kwargs)
                items = response.get('Items', [])
                
                if not items:
                    break
                
                # Delete items in batches
                with self.table.batch_writer() as batch:
                    for item in items:
                        # Create delete key from item
                        delete_key = {key: item[key] for key in key_names if key in item}
                        batch.delete_item(Key=delete_key)
                        deleted_count += 1
                
                print(f"🗑️  Deleted {deleted_count} items...")
                
                # Handle pagination
                if 'LastEvaluatedKey' not in response:
                    break
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
            
            print(f"✅ Cleared {deleted_count} items from table")
            return True
            
        except Exception as e:
            print(f"❌ Error clearing table: {e}")
            return False

    def fetch_hvpkod_json_data(self, season: int = 2024) -> List[Dict]:
        """Fetch data from hvpkod NFL-Data repository JSON files."""
        print(f"📡 Fetching {season} data from hvpkod repository...")
        
        base_url = f"https://raw.githubusercontent.com/hvpkod/NFL-Data/main/NFL-data-Players/{season}"
        
        # Define position files to fetch (excluding DEF since it's not available)
        position_files = [
            "QB_season.json",
            "RB_season.json", 
            "WR_season.json",
            "TE_season.json",
            "K_season.json"
        ]
        
        all_players = []
        
        for filename in position_files:
            try:
                url = f"{base_url}/{filename}"
                position = filename.split('_')[0]  # Extract position from filename
                
                print(f"📥 Fetching {position} data from {filename}...")
                
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    position_data = response.json()
                    print(f"✅ Loaded {len(position_data)} {position} players")
                    
                    # Add position info to each player
                    for player in position_data:
                        player['source_position'] = position
                    
                    all_players.extend(position_data)
                else:
                    print(f"⚠️  Failed to fetch {filename}: status {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Error fetching {filename}: {e}")
                continue
        
        print(f"✅ Total players fetched: {len(all_players)}")
        return all_players

    def process_hvpkod_data(self, players_data: List[Dict]) -> List[Dict]:
        """Process hvpkod JSON data into DynamoDB format."""
        print(f"🔄 Processing {len(players_data)} players from hvpkod data...")
        
        processed_players = []
        
        for player in players_data:
            try:
                # Extract basic info
                player_name = player.get("PlayerName", "").strip()
                player_id = player.get("PlayerId", "")
                position = player.get("Pos", player.get("source_position", "")).upper()
                team = player.get("Team", "").upper()
                
                if not player_name or not player_id or not position:
                    continue
                
                # Skip non-fantasy positions and handle DEF
                if position not in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF', 'DST']:
                    continue
                
                # Map DST to DEF
                if position == 'DST':
                    position = 'DEF'
                
                # Safe conversion function
                def safe_float(value, default=0.0):
                    try:
                        if value is None or value == '' or value == 'null':
                            return default
                        return float(value)
                    except (ValueError, TypeError):
                        return default
                
                def safe_int(value, default=0):
                    try:
                        if value is None or value == '' or value == 'null':
                            return default
                        return int(float(value))
                    except (ValueError, TypeError):
                        return default
                
                # Calculate fantasy points (standard scoring)
                # Passing: 1 pt per 25 yards, 4 pts per TD, -2 per INT
                # Rushing/Receiving: 1 pt per 10 yards, 6 pts per TD
                # PPR: +1 per reception
                
                passing_yards = safe_float(player.get("PassingYDS", 0))
                passing_tds = safe_int(player.get("PassingTD", 0))
                passing_ints = safe_int(player.get("PassingInt", 0))
                
                rushing_yards = safe_float(player.get("RushingYDS", 0))
                rushing_tds = safe_int(player.get("RushingTD", 0))
                
                receiving_yards = safe_float(player.get("ReceivingYDS", 0))
                receiving_tds = safe_int(player.get("ReceivingTD", 0))
                receptions = safe_int(player.get("ReceivingRec", 0))
                
                fumbles = safe_int(player.get("Fum", 0))
                two_pt = safe_int(player.get("2PT", 0))
                
                # Calculate standard fantasy points
                fantasy_points_std = (
                    (passing_yards / 25) + (passing_tds * 4) - (passing_ints * 2) +
                    (rushing_yards / 10) + (rushing_tds * 6) +
                    (receiving_yards / 10) + (receiving_tds * 6) +
                    (two_pt * 2) - (fumbles * 2)
                )
                
                # Calculate PPR fantasy points
                fantasy_points_ppr = fantasy_points_std + receptions
                
                # Calculate half PPR
                fantasy_points_half_ppr = fantasy_points_std + (receptions * 0.5)
                
                # Use TotalPoints if available (might be more accurate)
                total_points_given = safe_float(player.get("TotalPoints", 0))
                if total_points_given > 0:
                    fantasy_points_ppr = total_points_given
                
                # Skip players with very low fantasy production
                if fantasy_points_ppr < 5:
                    continue
                
                # Estimate games played (not directly available, use touches/targets as proxy)
                touches = safe_int(player.get("Touches", 0))
                targets = safe_int(player.get("Targets", 0))
                
                # Rough estimation of games played based on activity
                if position == "QB":
                    games_played = min(17, max(1, passing_tds + passing_ints + int(passing_yards / 100)))
                elif position in ["RB", "WR", "TE"]:
                    games_played = min(17, max(1, int((touches + targets) / 3))) if (touches + targets) > 0 else 1
                else:  # K
                    games_played = min(17, max(1, int(fantasy_points_ppr / 8))) if fantasy_points_ppr > 0 else 1
                
                # Estimate age (not available, use reasonable defaults by position)
                age_estimates = {"QB": 28, "RB": 25, "WR": 26, "TE": 27, "K": 30}
                estimated_age = age_estimates.get(position, 26)
                
                # Create player record
                player_record = {
                    "player_id": player_id,
                    "player_display_name": player_name,
                    "position": position,
                    "team": team,
                    "age": estimated_age,  # Estimated
                    "years_exp": 3,  # Estimated (could be improved with roster data)
                    "season": 2024,
                    "games_played": games_played,
                    
                    # Fantasy points
                    "fantasy_points": Decimal(str(round(fantasy_points_std, 2))),
                    "fantasy_points_ppr": Decimal(str(round(fantasy_points_ppr, 2))),
                    "fantasy_points_half_ppr": Decimal(str(round(fantasy_points_half_ppr, 2))),
                    
                    # Passing stats
                    "passing_attempts": 0,  # Not available
                    "passing_completions": 0,  # Not available
                    "passing_yards": safe_int(passing_yards),
                    "passing_tds": passing_tds,
                    "passing_interceptions": passing_ints,
                    
                    # Rushing stats
                    "rushing_attempts": safe_int(player.get("TouchCarries", 0)),
                    "rushing_yards": safe_int(rushing_yards),
                    "rushing_tds": rushing_tds,
                    
                    # Receiving stats
                    "targets": safe_int(player.get("Targets", 0)),
                    "receptions": receptions,
                    "receiving_yards": safe_int(receiving_yards),
                    "receiving_tds": receiving_tds,
                    
                    # Other stats
                    "fumbles": fumbles,
                    "two_point_conversions": two_pt,
                    "rank": safe_int(player.get("Rank", 999)),
                    
                    # Red zone stats (bonus data)
                    "red_zone_targets": safe_int(player.get("RzTarget", 0)),
                    "red_zone_touches": safe_int(player.get("RzTouch", 0)),
                    "goal_to_go": safe_int(player.get("RzG2G", 0)),
                    
                    # Metadata
                    "data_source": "hvpkod_github",
                    "last_updated": datetime.now().isoformat(),
                    "is_rookie": False,  # Would need additional data to determine
                    "injury_status": "",
                    "depth_chart_position": 1 if safe_int(player.get("Rank", 999)) <= 50 else 2
                }
                
                processed_players.append(player_record)
                
            except Exception as e:
                print(f"⚠️  Error processing player {player.get('PlayerName', 'Unknown')}: {e}")
                continue
        
        print(f"✅ Processed {len(processed_players)} fantasy-relevant players")
        return processed_players

    def load_data_to_dynamodb(self, players: List[Dict]) -> bool:
        """Load processed player data into DynamoDB."""
        print(f"📤 Loading {len(players)} players to DynamoDB...")
        
        try:
            batch_size = 25
            loaded_count = 0
            
            for i in range(0, len(players), batch_size):
                batch = players[i:i + batch_size]
                
                with self.table.batch_writer() as writer:
                    for player in batch:
                        writer.put_item(Item=player)
                        loaded_count += 1
                
                print(f"📤 Loaded {loaded_count}/{len(players)} players...")
                time.sleep(0.1)  # Small delay to avoid throttling
            
            print(f"✅ Successfully loaded {loaded_count} players to DynamoDB")
            return True
            
        except Exception as e:
            print(f"❌ Error loading to DynamoDB: {e}")
            return False

    def validate_data(self) -> bool:
        """Validate that data was loaded correctly."""
        print("🔍 Validating loaded data...")
        
        try:
            # Get sample of data
            response = self.table.scan(Limit=10)
            items = response.get('Items', [])
            
            if not items:
                print("❌ No data found in table")
                return False
            
            print(f"✅ Found {len(items)} sample items")
            
            # Check data structure
            sample_item = items[0]
            required_fields = [
                'player_id', 'player_display_name', 'position', 
                'fantasy_points_ppr', 'games_played', 'season'
            ]
            
            missing_fields = [field for field in required_fields if field not in sample_item]
            if missing_fields:
                print(f"❌ Missing required fields: {missing_fields}")
                return False
            
            # Get all items for analysis
            response = self.table.scan()
            all_items = response.get('Items', [])
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                all_items.extend(response.get('Items', []))
            
            # Sort by PPR points
            sorted_players = sorted(
                all_items, 
                key=lambda x: float(x.get('fantasy_points_ppr', 0)), 
                reverse=True
            )
            
            print(f"\n🏆 Top 5 players by PPR points:")
            for i, player in enumerate(sorted_players[:5]):
                name = player.get('player_display_name', 'Unknown')
                position = player.get('position', '?')
                team = player.get('team', '???')
                ppr = float(player.get('fantasy_points_ppr', 0))
                games = int(player.get('games_played', 1))  # Convert to int
                ppg = ppr / max(games, 1)  # Now both are numeric types
                rank = player.get('rank', 'N/A')
                print(f"   {i+1}. {name} ({position}, {team}) - {ppr:.1f} PPR pts, {games} games ({ppg:.1f} PPG) [Rank: {rank}]")
            
            print(f"\n📊 Total players loaded: {len(all_items)}")
            
            # Position breakdown
            position_counts = {}
            position_points = {}
            for player in all_items:
                pos = player.get('position', 'Unknown')
                ppr = float(player.get('fantasy_points_ppr', 0))
                position_counts[pos] = position_counts.get(pos, 0) + 1
                position_points[pos] = position_points.get(pos, 0) + ppr
            
            print(f"📋 Position breakdown:")
            for pos in sorted(position_counts.keys()):
                count = position_counts[pos]
                avg_points = position_points[pos] / count
                print(f"   {pos}: {count} players (avg {avg_points:.1f} PPR pts)")
            
            # Show top players by position
            print(f"\n🏆 Top player by position:")
            for position in ['QB', 'RB', 'WR', 'TE', 'K']:
                pos_players = [p for p in sorted_players if p.get('position') == position]
                if pos_players:
                    top_player = pos_players[0]
                    name = top_player.get('player_display_name', 'Unknown')
                    team = top_player.get('team', '???')
                    ppr = float(top_player.get('fantasy_points_ppr', 0))
                    print(f"   {position}: {name} ({team}) - {ppr:.1f} PPR pts")
            
            return True
            
        except Exception as e:
            print(f"❌ Validation error: {e}")
            return False

    def run_full_refresh(self, season: int = 2024, clear_first: bool = True) -> bool:
        """Run complete data refresh from hvpkod repository."""
        print(f"🚀 Starting data refresh for {season} season...")
        start_time = time.time()
        
        # Step 1: Clear existing data
        if clear_first:
            if not self.clear_table():
                return False
        
        # Step 2: Fetch data from hvpkod repository
        players_data = self.fetch_hvpkod_json_data(season)
        if not players_data:
            print("❌ No data fetched from repository")
            return False
        
        # Step 3: Process data
        processed_players = self.process_hvpkod_data(players_data)
        if not processed_players:
            print("❌ No players processed successfully")
            return False
        
        # Step 4: Load to DynamoDB
        if not self.load_data_to_dynamodb(processed_players):
            return False
        
        # Step 5: Validate
        if not self.validate_data():
            return False
        
        duration = time.time() - start_time
        print(f"🎉 Data refresh completed successfully in {duration:.1f} seconds!")
        return True

def main():
    parser = argparse.ArgumentParser(description="Fantasy Football Data Loader (hvpkod)")
    parser.add_argument("--table", default=TABLE_NAME, help="DynamoDB table name")
    parser.add_argument("--region", default=REGION, help="AWS region")
    parser.add_argument("--no-clear", action="store_true", help="Don't clear table first")
    parser.add_argument("--validate-only", action="store_true", help="Only validate existing data")
    parser.add_argument("--season", type=int, default=2024, help="Season year to load")
    
    args = parser.parse_args()
    
    loader = FantasyDataLoader(args.table, args.region)
    
    if args.validate_only:
        print("🔍 Validation mode - checking existing data...")
        success = loader.validate_data()
    else:
        success = loader.run_full_refresh(args.season, clear_first=not args.no_clear)
    
    if success:
        print("✅ Operation completed successfully!")
        exit(0)
    else:
        print("❌ Operation failed!")
        exit(1)

if __name__ == "__main__":
    main()