#!/usr/bin/env python3
"""
2025 Fantasy Football Projections Data Loader - FantasyPros Only
Fetches season-long projection data from FantasyPros and populates DynamoDB
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
from bs4 import BeautifulSoup
import re
from team_names import remove_nfl_abbreviations

# Configuration
TABLE_NAME = "2025-2026-fantasy-football-player-data"
REGION = "us-west-2"

class FantasyProsProjectionLoader:
    def __init__(self, table_name: str = TABLE_NAME, region: str = REGION):
        self.dynamodb = boto3.resource('dynamodb', region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name
        self.session = requests.Session()
        
        # Set user agent to avoid blocking
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def fetch_fantasypros_season_projections(self, position: str = "all") -> List[Dict]:
        """Fetch season-long projections from FantasyPros with proper stat mapping."""
        print(f"📡 Fetching FantasyPros season projections for {position}...")
        
        projections = []
        positions = ["qb", "rb", "wr", "te", "k", "dst"] if position == "all" else [position.lower()]
        
        # Define expected headers for each position to map stats correctly
        position_stat_mappings = {
            'qb': {
                'player': 'player_name',
                'pass_att': 'pass_att',
                'pass_cmp': 'pass_cmp',
                'pass_yds': 'pass_yds',
                'pass_tds': 'pass_tds',
                'pass_int': 'pass_int',
                'rush_att': 'rush_att',
                'rush_yds': 'rush_yds',
                'rush_tds': 'rush_tds',
                'fl': 'fumbles',
                'fpts': 'fantasy_points'
            },
            'rb': {
                'player': 'player_name',
                'rush_att': 'rush_att',
                'rush_yds': 'rush_yds',
                'rush_tds': 'rush_tds',
                'rec': 'receptions',
                'rec_yds': 'rec_yds',
                'rec_tds': 'rec_tds',
                'fl': 'fumbles',
                'fpts': 'fantasy_points'
            },
            'wr': {
                'player': 'player_name',
                'rec': 'receptions',
                'rec_yds': 'rec_yds',
                'rec_tds': 'rec_tds',
                'rush_att': 'rush_att',
                'rush_yds': 'rush_yds',
                'rush_tds': 'rush_tds',
                'fl': 'fumbles',
                'fpts': 'fantasy_points'
            },
            'te': {
                'player': 'player_name',
                'rec': 'receptions',
                'rec_yds': 'rec_yds',
                'rec_tds': 'rec_tds',
                'fl': 'fumbles',
                'fpts': 'fantasy_points'
            },
            'k': {
                'player': 'player_name',
                'fg': 'field_goals',
                'fga': 'field_goal_attempts',
                'xpt': 'extra_points',
                'fpts': 'fantasy_points'
            },
            'dst': {
                'player': 'player_name',
                'sack': 'sacks',
                'int': 'interceptions',
                'fr': 'fumble_recoveries',
                'ff': 'forced_fumbles',
                'td': 'def_tds',
                'safety': 'safeties',
                'pa': 'points_allowed',
                'ya': 'yards_allowed',
                'fpts': 'fantasy_points'
            }
        }
        
        for pos in positions:
            try:
                # Use season-long projections (draft week)
                url = f"https://www.fantasypros.com/nfl/projections/{pos}.php?week=draft"
                
                print(f"🔥 Fetching {pos.upper()} season projections...")
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Find the projections table - try multiple selectors
                    table = (soup.find('table', {'id': 'data'}) or 
                            soup.find('table', class_='table') or
                            soup.find('table', class_='table-hover'))
                    
                    if not table:
                        print(f"⚠️  No projections table found for {pos}")
                        continue
                    
                    # Parse table headers
                    headers = []
                    header_row = table.find('thead')
                    if header_row:
                        header_cells = header_row.find_all(['th', 'td'])
                        for th in header_cells:
                            header_text = th.get_text(strip=True).lower()
                            # Clean up header names and map common variations
                            header_text = (header_text.replace(' ', '_')
                                         .replace('/', '_')
                                         .replace('passing_', 'pass_')
                                         .replace('rushing_', 'rush_')
                                         .replace('receiving_', 'rec_')
                                         .replace('yds', 'yds')
                                         .replace('tds', 'tds')
                                         .replace('att', 'att')
                                         .replace('cmp', 'cmp'))
                            headers.append(header_text)
                    
                    print(f"📊 Found headers for {pos}: {headers}")
                    
                    # Parse table rows
                    tbody = table.find('tbody') or table
                    rows = tbody.find_all('tr')[1:] if not table.find('tbody') else tbody.find_all('tr')
                    
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) < 2:  # Need at least player name and one stat
                            continue
                        
                        player_data = {}
                        
                        # Extract data from each cell
                        for i, cell in enumerate(cells):
                            if i < len(headers):
                                cell_text = cell.get_text(strip=True)
                                header_key = headers[i]
                                
                                # Map to standardized stat names if available
                                stat_mapping = position_stat_mappings.get(pos, {})
                                mapped_key = stat_mapping.get(header_key, header_key)
                                
                                player_data[mapped_key] = cell_text
                        
                        # Extract player name and team from first column
                        if headers and len(headers) > 0:
                            first_header = headers[0]
                            player_text = player_data.get(first_header, '') or player_data.get('player_name', '')
                            
                            if player_text:
                                player_info = self._parse_fantasypros_player(player_text)
                                
                                if player_info['name']:
                                    # Create clean projection record
                                    projection_record = {
                                        'name': player_info['name'],
                                        'team': player_info['team'],
                                        'position': pos.upper(),
                                        'source': 'fantasypros'
                                    }
                                    
                                    # Add all the parsed stats
                                    for key, value in player_data.items():
                                        if key not in [first_header, 'player_name'] and value:
                                            # Convert numeric values
                                            numeric_value = self._extract_numeric(value)
                                            if numeric_value > 0 or key == 'fantasy_points':
                                                projection_record[key] = numeric_value
                                    
                                    projections.append(projection_record)
                                    
                                    # Debug: print first few records
                                    if len(projections) <= 3:
                                        print(f"🔍 Sample {pos} projection: {projection_record}")
                
                time.sleep(2)  # Be respectful to FantasyPros
                
            except Exception as e:
                print(f"❌ Error fetching {pos} from FantasyPros: {e}")
                continue
        
        print(f"✅ Fetched {len(projections)} season projections from FantasyPros")
        return projections
    
    def _parse_fantasypros_player(self, player_text: str) -> Dict[str, str]:
        """Parse FantasyPros player format specifically."""
        player_info = {'name': '', 'team': ''}
        
        if not player_text:
            return player_info
        
        # FantasyPros typically uses format: "Player Name Team"
        # Sometimes: "Player Name (Team - POS)" or "Player Name Team POS"
        
        # Remove position indicators in parentheses
        text = re.sub(r'\s*\([^)]*\)', '', player_text).strip()
        cleaned_name = remove_nfl_abbreviations(text)
        # Look for team abbreviation at the end (2-4 capital letters)
        match = re.match(r'^(.+?)\s+([A-Z]{2,4})(?:\s+[A-Z]{1,3})?$', cleaned_name)

        if match:
            player_info['name'] = match.group(1).strip()
            player_info['team'] = match.group(2).strip()
        else:
            # If no clear team found, use the whole text as name
            player_info['name'] = cleaned_name

        return player_info

    def _extract_numeric(self, value) -> float:
        """Extract numeric value from string with improved parsing."""
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Remove commas and common non-numeric characters
            cleaned = re.sub(r'[,$%]', '', value.strip())
            
            # Handle negative values
            is_negative = cleaned.startswith('-')
            if is_negative:
                cleaned = cleaned[1:]
            
            # Extract just the numeric part (including decimals)
            numeric_match = re.search(r'(\d+\.?\d*)', cleaned)
            if numeric_match:
                try:
                    result = float(numeric_match.group(1))
                    return -result if is_negative else result
                except ValueError:
                    return 0.0
        
        return 0.0

    def calculate_projections(self, player_data: Dict) -> Dict:
        """Calculate projections from FantasyPros data."""
        position = player_data.get('position', '').upper()
        
        # Map FantasyPros stats to our standard format
        consensus = {}
        
        # Common stats for all positions
        if 'fantasy_points' in player_data:
            consensus['ppr_points'] = player_data['fantasy_points']
        
        # Position-specific stat mapping
        if position == 'QB':
            consensus.update({
                'pass_yds': player_data.get('pass_yds', 0),
                'pass_tds': player_data.get('pass_tds', 0),
                'pass_int': player_data.get('pass_int', 0),
                'rush_yds': player_data.get('rush_yds', 0),
                'rush_tds': player_data.get('rush_tds', 0),
                'fumbles': player_data.get('fumbles', 0)
            })
        
        elif position in ['RB', 'WR']:
            consensus.update({
                'rush_yds': player_data.get('rush_yds', 0),
                'rush_tds': player_data.get('rush_tds', 0),
                'receptions': player_data.get('receptions', 0),
                'rec_yds': player_data.get('rec_yds', 0),
                'rec_tds': player_data.get('rec_tds', 0),
                'fumbles': player_data.get('fumbles', 0)
            })
        
        elif position == 'TE':
            consensus.update({
                'receptions': player_data.get('receptions', 0),
                'rec_yds': player_data.get('rec_yds', 0),
                'rec_tds': player_data.get('rec_tds', 0),
                'fumbles': player_data.get('fumbles', 0)
            })
        
        elif position == 'K':
            consensus.update({
                'field_goals': player_data.get('field_goals', 0),
                'field_goal_attempts': player_data.get('field_goal_attempts', 0),
                'extra_points': player_data.get('extra_points', 0)
            })
        
        elif position == 'DST':
            consensus.update({
                'sacks': player_data.get('sacks', 0),
                'interceptions': player_data.get('interceptions', 0),
                'fumble_recoveries': player_data.get('fumble_recoveries', 0),
                'def_tds': player_data.get('def_tds', 0),
                'safeties': player_data.get('safeties', 0),
                'points_allowed': player_data.get('points_allowed', 0)
            })
        
        # Only return stats that have non-zero values
        return {k: v for k, v in consensus.items() if isinstance(v, (int, float)) and v > 0}

    def update_dynamodb_with_projections(self, projections: List[Dict]) -> bool:
        """Update DynamoDB with FantasyPros projections."""
        print(f"🔤 Updating DynamoDB with {len(projections)} player projections...")
        
        try:
            updated_count = 0
            not_found_count = 0
            error_count = 0
            
            for i, proj in enumerate(projections, 1):
                try:
                    player_name = proj.get('name', '').strip()
                    if not player_name:
                        continue
                    
                    # Try to find existing player in DynamoDB
                    existing_player = self._find_existing_player(player_name, proj.get('position', ''))
                    
                    if existing_player:
                        # Calculate projections
                        consensus = self.calculate_projections(proj)
                        
                        if consensus:
                            # Prepare update data
                            update_data = {
                                'projections_2025_ppr': Decimal(str(round(consensus.get('ppr_points', 0), 2))),
                                'projections_2025_pass_yds': int(consensus.get('pass_yds', 0)),
                                'projections_2025_pass_tds': int(consensus.get('pass_tds', 0)),
                                'projections_2025_rush_yds': int(consensus.get('rush_yds', 0)),
                                'projections_2025_rush_tds': int(consensus.get('rush_tds', 0)),
                                'projections_2025_rec_yds': int(consensus.get('rec_yds', 0)),
                                'projections_2025_rec_tds': int(consensus.get('rec_tds', 0)),
                                'projections_2025_receptions': int(consensus.get('receptions', 0)),
                                'projection_sources': 1,  # Only FantasyPros
                                'projections_last_updated': datetime.now().isoformat()
                            }
                            
                            # Only include non-zero projections
                            filtered_update = {k: v for k, v in update_data.items() 
                                             if not (isinstance(v, (int, Decimal)) and v == 0) or k in ['projection_sources', 'projections_last_updated']}
                            
                            if len(filtered_update) > 2:  # More than just meta fields
                                # Update DynamoDB
                                self.table.update_item(
                                    Key={'player_id': existing_player['player_id']},
                                    UpdateExpression='SET ' + ', '.join([f'{k} = :{k}' for k in filtered_update.keys()]),
                                    ExpressionAttributeValues={f':{k}': v for k, v in filtered_update.items()}
                                )
                                
                                updated_count += 1
                    else:
                        not_found_count += 1
                        if not_found_count <= 20:  # Log first 20 not found
                            print(f"⚠️  Player not found: {player_name} ({proj.get('position', '')})")
                    
                    # Progress update
                    if i % 100 == 0:
                        print(f"🔄 Processed {i}/{len(projections)} players...")
                        
                except Exception as e:
                    error_count += 1
                    if error_count <= 10:  # Log first 10 errors
                        print(f"❌ Error updating {proj.get('name', 'Unknown')}: {e}")
            
            print(f"✅ Successfully updated {updated_count} players")
            print(f"⚠️  {not_found_count} players not found in database")
            print(f"❌ {error_count} errors encountered")
            
            return updated_count > 0
            
        except Exception as e:
            print(f"❌ Critical error updating DynamoDB: {e}")
            return False

    def _find_existing_player(self, player_name: str, position: str = "") -> Optional[Dict]:
        """Find existing player with improved fuzzy matching."""
        try:
            # First try exact match
            response = self.table.scan(
                FilterExpression="contains(player_display_name, :name)",
                ExpressionAttributeValues={":name": player_name}
            )
            
            items = response.get('Items', [])
            
            # Filter by position if provided
            if position and items:
                position_upper = position.upper()
                items = [item for item in items if item.get('position', '').upper() == position_upper]
            
            # Look for exact matches first
            for item in items:
                if item.get('player_display_name', '').lower() == player_name.lower():
                    return item
            
            # If no exact match, return first match
            if items:
                return items[0]
            
            return None
            
        except Exception as e:
            print(f"❌ Error finding player {player_name}: {e}")
            return None

    def run_projection_update(self, position: str = "all") -> bool:
        """Run FantasyPros projection update."""
        print("🚀 Starting FantasyPros projection update...")
        start_time = time.time()
        
        try:
            # Fetch FantasyPros projections
            projections = self.fetch_fantasypros_season_projections(position)
            
            if not projections:
                print("❌ No FantasyPros projections collected")
                return False
            
            print(f"📊 Collected {len(projections)} FantasyPros projections")
            
            # Update DynamoDB
            success = self.update_dynamodb_with_projections(projections)
            
            duration = time.time() - start_time
            print(f"🎉 FantasyPros update completed in {duration:.1f} seconds!")
            
            return success
            
        except Exception as e:
            print(f"❌ Error in FantasyPros update: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description="2025 Fantasy Football Projections Loader - FantasyPros Only")
    parser.add_argument("--table", default=TABLE_NAME, help="DynamoDB table name")
    parser.add_argument("--region", default=REGION, help="AWS region")
    parser.add_argument("--position", choices=["all", "qb", "rb", "wr", "te", "k", "dst"], 
                       default="all", help="Position to fetch")
    parser.add_argument("--test", action="store_true", help="Test mode - don't update DynamoDB")
    
    args = parser.parse_args()
    
    loader = FantasyProsProjectionLoader(args.table, args.region)
    
    if args.test:
        print("🧪 Test mode - will not update DynamoDB")
        projections = loader.fetch_fantasypros_season_projections(args.position)
        
        print(f"\n📊 Sample projections for review:")
        for i, proj in enumerate(projections[:5]):  # Show first 5
            print(f"\n{i+1}. {proj.get('name', 'Unknown')} ({proj.get('position', '')}) - {proj.get('team', '')}")
            stats = {k: v for k, v in proj.items() if k not in ['name', 'position', 'team', 'source'] and v}
            for stat, value in stats.items():
                print(f"   {stat}: {value}")
    else:
        success = loader.run_projection_update(args.position)
        
        if success:
            print("✅ Projection update completed successfully!")
        else:
            print("❌ Projection update failed!")


if __name__ == "__main__":
    main()