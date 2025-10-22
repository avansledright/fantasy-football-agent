"""
DynamoDB Client for Fantasy Football Data
Handles all database operations
UPDATED for fantasy-football-players-updated table with seasons.{year}.* structure
"""

import json
import logging
import boto3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from boto3.dynamodb.conditions import Key, Attr
import os
from utils import normalize_position, convert_nfl_defense_name

logger = logging.getLogger(__name__)

class DynamoDBClient:
    """Client for interacting with DynamoDB tables"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        
        # Environment variables for table names
        self.players_table_name = os.environ.get('FANTASY_PLAYERS_TABLE', 'fantasy-football-players-updated')
        self.roster_table_name = os.environ.get('FANTASY_ROSTER_TABLE', 'fantasy-football-team-roster')
        self.chat_history_table_name = os.environ.get('CHAT_HISTORY_TABLE', 'fantasy-football-chat-history')
        
        # Table references
        self.players_table = self.dynamodb.Table(self.players_table_name)
        self.roster_table = self.dynamodb.Table(self.roster_table_name)
        self.chat_history_table = self.dynamodb.Table(self.chat_history_table_name)
        
        logger.info(f"DynamoDBClient initialized with tables: {self.players_table_name}, {self.roster_table_name}, {self.chat_history_table_name}")
        
    def _get_current_week(self, context: Optional[Dict[str, Any]] = None) -> int:
        """Helper to get current NFL week from context or default"""
        if context and 'week' in context:
            try:
                return int(context['week'])
            except (ValueError, TypeError):
                pass
        # Fallback to default week if no context or invalid week
        return 1
    
    def get_team_roster(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Get team roster information"""
        try:
            response = self.roster_table.get_item(
                Key={'team_id': team_id}
            )
            item = response.get('Item')
            if item:
                logger.info(f"Retrieved roster for team: {team_id}")
            else:
                logger.warning(f"No roster found for team: {team_id}")
            return item
        except Exception as e:
            logger.error(f"Error getting team roster for {team_id}: {str(e)}")
            return None
    
    def get_player_stats(self, player_id: str) -> Optional[Dict[str, Any]]:
        """Get player statistics and projections from unified table with NEW structure"""
        logger.info(f"Original player_id is {player_id}")
        try:
            if "D/ST" in player_id:
                logger.info(f"Found DST in player_id {player_id}")
                player_id = convert_nfl_defense_name(player_id)
            
            response = self.players_table.get_item(
                Key={'player_id': player_id}
            )
            item = response.get('Item')
            if item:
                logger.debug(f"Retrieved stats for player: {player_id}")
            return item
        except Exception as e:
            logger.error(f"Error getting player stats for {player_id}: {str(e)}")
            return None
    
    def search_players_by_name(self, player_name: str) -> List[Dict[str, Any]]:
        """Search for players by name (partial match)"""
        try:
            # Use scan with filter for name search (consider using GSI for better performance)
            response = self.players_table.scan(
                FilterExpression="contains(player_name, :name)",
                ExpressionAttributeValues={':name': player_name},
            )
            items = response.get('Items', [])
            logger.info(f"Found {len(items)} players matching name: {player_name}")
            return items
        except Exception as e:
            logger.error(f"Error searching players by name {player_name}: {str(e)}")
            return []
    
    def get_waiver_wire_players(
        self, 
        position: Optional[str] = None, 
        min_ownership: float = 0, 
        max_ownership: float = 50, 
        limit: Optional[int] = None, 
        sort_by_projection: bool = True, 
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get waiver wire players from unified table with NEW structure
        
        Uses seasons.2025.* for ownership, injury, and projections
        """
        try:
            all_items = []
            last_evaluated_key = None
            
            # Get current week for projection sorting
            current_week = self._get_current_week(context)
            season_year = "2025"  # Could be made dynamic
            
            # Base filter: ownership range AND healthy status
            base_filter = (
                Attr(f'seasons.{season_year}.percent_owned').between(min_ownership, max_ownership) &
                Attr(f'seasons.{season_year}.injury_status').eq('ACTIVE')
            )
            
            # Add position filter if specified
            if position:
                normalized_pos = normalize_position(position)
                if normalized_pos == "DST":
                    normalized_pos = "D/ST"
                base_filter = base_filter & Attr('position').eq(normalized_pos)
            
            logger.info(f"Scanning unified table for waiver players (position: {position or 'all'}, ownership: {min_ownership}-{max_ownership}%)")
            
            while True:
                scan_params = {
                    "FilterExpression": base_filter,
                    "ProjectionExpression": "player_id, player_name, #pos, seasons",
                    "ExpressionAttributeNames": {"#pos": "position"}
                }
                
                if last_evaluated_key:
                    scan_params["ExclusiveStartKey"] = last_evaluated_key
                
                response = self.players_table.scan(**scan_params)
                
                # Process items to extract relevant data from seasons structure
                batch_items = []
                for item in response.get('Items', []):
                    seasons = item.get('seasons', {})
                    season_2025 = seasons.get(season_year, {})
                    
                    # Extract data from NEW structure
                    processed_item = {
                        'player_id': item.get('player_id'),
                        'player_name': item.get('player_name'),
                        'position': item.get('position'),
                        'team': season_2025.get('team', ''),
                        'injury_status': season_2025.get('injury_status', 'UNKNOWN'),
                        'percent_owned': float(season_2025.get('percent_owned', 0)),
                        'weekly_projections': season_2025.get('weekly_projections', {})
                    }
                    
                    batch_items.append(processed_item)
                
                all_items.extend(batch_items)
                logger.info(f"Batch retrieved {len(batch_items)} items. Total so far: {len(all_items)}")
                
                # Check if we have more data to fetch
                last_evaluated_key = response.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
                
                # Optional: If limit is specified and we have enough items, break early
                if limit and not sort_by_projection and len(all_items) >= limit:
                    break
            
            logger.info(f"Total items found: {len(all_items)}")
            
            # Sort by current week projection if requested
            if sort_by_projection and all_items:
                all_items.sort(
                    key=lambda x: float(x.get('weekly_projections', {}).get(str(current_week), 0)),
                    reverse=True
                )
            
            # Apply limit if specified
            if limit:
                result = all_items[:limit]
            else:
                result = all_items
            
            logger.info(f"Returning {len(result)} waiver wire players from unified table")
            return result
            
        except Exception as e:
            logger.error(f"Error getting waiver wire players from unified table: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_all_team_rosters(self) -> List[Dict[str, Any]]:
        """Get all team rosters (for league analysis)"""
        try:
            response = self.roster_table.scan()
            items = response.get('Items', [])
            logger.info(f"Retrieved {len(items)} team rosters")
            return items
        except Exception as e:
            logger.error(f"Error getting all team rosters: {str(e)}")
            return []
    
    def store_chat_message(self, session_id: str, message: str, sender: str, context: Dict[str, Any]) -> bool:
        """Store chat message in DynamoDB"""
        try:
            timestamp = datetime.utcnow().isoformat()
            expires_at = int((datetime.utcnow() + timedelta(days=7)).timestamp())
            
            item = {
                'session_id': session_id,
                'timestamp': timestamp,
                'message': message,
                'sender': sender,
                'team_id': context.get('team_id', 'unknown'),
                'week': context.get('week', 'unknown'),
                'expires_at': expires_at
            }
            
            # Add context data if available
            if context.get('current_team'):
                item['team_context'] = json.dumps(context['current_team'])
            
            self.chat_history_table.put_item(Item=item)
            logger.debug(f"Stored {sender} message for session: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing chat message: {str(e)}")
            return False
    
    def get_chat_history(self, session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent chat history for context"""
        try:
            response = self.chat_history_table.query(
                KeyConditionExpression=Key('session_id').eq(session_id),
                ScanIndexForward=False,  # Most recent first
                Limit=limit
            )
            
            items = response.get('Items', [])
            logger.debug(f"Retrieved {len(items)} chat history items for session: {session_id}")
            return items
            
        except Exception as e:
            logger.error(f"Error retrieving chat history: {str(e)}")
            return []
    
    def get_players_by_team(self, nfl_team: str) -> List[Dict[str, Any]]:
        """Get all players from a specific NFL team using NEW structure"""
        try:
            season_year = "2025"
            # Scan for players where seasons.2025.team matches
            response = self.players_table.scan(
                FilterExpression=Attr(f'seasons.{season_year}.team').eq(nfl_team)
            )
            items = response.get('Items', [])
            logger.info(f"Found {len(items)} players for NFL team: {nfl_team}")
            return items
        except Exception as e:
            logger.error(f"Error getting players by team {nfl_team}: {str(e)}")
            return []
    
    def get_top_performers(self, position: str, season: int = 2025, week: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get top performing players by position using NEW structure"""
        try:
            season_str = str(season)
            
            # Scan for players by position
            response = self.players_table.scan(
                FilterExpression=Attr('position').eq(position)
            )
            
            players = response.get('Items', [])
            
            # Sort by fantasy points using NEW structure
            if week:
                # Sort by specific week performance from seasons.{year}.weekly_stats.{week}
                players.sort(
                    key=lambda x: float(
                        x.get('seasons', {})
                        .get(season_str, {})
                        .get('weekly_stats', {})
                        .get(str(week), {})
                        .get('fantasy_points', 0)
                    ),
                    reverse=True
                )
            else:
                # Sort by season projections from seasons.{year}.season_projections
                players.sort(
                    key=lambda x: float(
                        x.get('seasons', {})
                        .get(season_str, {})
                        .get('season_projections', {})
                        .get('MISC_FPTS', 0)
                    ),
                    reverse=True
                )
            
            top_players = players[:20]  # Return top 20
            logger.info(f"Retrieved top {len(top_players)} performers for position: {position}")
            return top_players
            
        except Exception as e:
            logger.error(f"Error getting top performers: {str(e)}")
            return []
    
    def health_check(self) -> bool:
        """Perform a health check on the database connection"""
        try:
            # Try to describe one of the tables
            self.roster_table.table_status
            logger.info("Database health check passed")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False