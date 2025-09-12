"""
DynamoDB Client for Fantasy Football Data
Handles all database operations
"""

import json
import logging
import boto3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from boto3.dynamodb.conditions import Key, Attr
import os
from utils import normalize_position

logger = logging.getLogger(__name__)

class DynamoDBClient:
    """Client for interacting with DynamoDB tables"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        
        # Environment variables for table names
        self.players_table_name = os.environ.get('FANTASY_PLAYERS_TABLE', 'fantasy-football-players')
        self.roster_table_name = os.environ.get('FANTASY_ROSTER_TABLE', 'fantasy-football-team-roster')
        self.waiver_table_name = os.environ.get('FANTASY_WAIVER_TABLE', 'fantasy-football-agent-2025-waiver-table')
        self.chat_history_table_name = os.environ.get('CHAT_HISTORY_TABLE', 'fantasy-football-chat-history')
        
        # Table references
        self.players_table = self.dynamodb.Table(self.players_table_name)
        self.roster_table = self.dynamodb.Table(self.roster_table_name)
        self.waiver_table = self.dynamodb.Table(self.waiver_table_name)
        self.chat_history_table = self.dynamodb.Table(self.chat_history_table_name)
        
        logger.info(f"DynamoDBClient initialized with tables: {self.players_table_name}, {self.roster_table_name}, {self.waiver_table_name}, {self.chat_history_table_name}")
        
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
        """Get player statistics and projections"""
        try:
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
    
    def get_waiver_wire_players(self, position: Optional[str] = None, min_ownership: float = 0, max_ownership: float = 50, 
                          limit: int = 500, sort_by_projection: bool = True, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Get waiver wire players with optional position filter - ultra optimized"""
        try:
            if position:

                # FAST PATH: Use GSI query when position is specified
                normalized_pos = normalize_position(position)
                logger.info(f"Using GSI query for position: {normalized_pos}")
                
                response = self.waiver_table.query(
                    IndexName='position-index',
                    KeyConditionExpression=Key('position').eq(normalized_pos),
                    FilterExpression=Attr('percent_owned').between(min_ownership, max_ownership),
                    ProjectionExpression="player_season, player_name, #pos, team, injury_status, percent_owned, weekly_projections",
                    ExpressionAttributeNames={"#pos": "position"},
                    Limit=limit * 2  # Get more than needed for better sorting
                )
            else:
                # SLOWER PATH: Scan when no position specified
                logger.info("Using table scan (no position filter)")
                response = self.waiver_table.scan(
                    FilterExpression=Attr("percent_owned").between(min_ownership, max_ownership),
                    ProjectionExpression="player_season, player_name, #pos, team, injury_status, percent_owned, weekly_projections",
                    ExpressionAttributeNames={"#pos": "position"},
                    Limit=limit * 2
                )
            
            items = response.get('Items', [])
            
            # Sort by current week projection if requested (client-side optimization)
            if sort_by_projection and items:
                current_week = self._get_current_week(context)
                items.sort(
                    key=lambda x: x.get('weekly_projections', {}).get(str(current_week), 0),
                    reverse=True
                )
            
            # Return only the requested limit
            result = items[:limit]
            logger.info(f"Found {len(result)} waiver wire players (position: {position or 'all'}, ownership: {min_ownership}-{max_ownership}%)")
            return result
        
        except Exception as e:
            logger.error(f"Error getting waiver wire players: {str(e)}")
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
        """Get all players from a specific NFL team"""
        try:
            # This would require a GSI on the players table by team
            # For now, use scan (consider optimizing with proper indexing)
            response = self.players_table.scan(
                FilterExpression="contains(player_id, :team)",
                ExpressionAttributeValues={':team': nfl_team}
            )
            items = response.get('Items', [])
            logger.info(f"Found {len(items)} players for NFL team: {nfl_team}")
            return items
        except Exception as e:
            logger.error(f"Error getting players by team {nfl_team}: {str(e)}")
            return []
    
    def get_top_performers(self, position: str, season: int = 2025, week: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get top performing players by position"""
        try:
            # Scan for players by position and sort by fantasy points
            response = self.players_table.scan(
                FilterExpression="position = :pos",
                ExpressionAttributeValues={':pos': position}
            )
            
            players = response.get('Items', [])
            
            # Sort by fantasy points (current season)
            if week:
                # Sort by specific week performance
                players.sort(
                    key=lambda x: x.get('current_season_stats', {}).get(str(season), {}).get(str(week), {}).get('fantasy_points', 0),
                    reverse=True
                )
            else:
                # Sort by season average or projections
                players.sort(
                    key=lambda x: x.get('projections', {}).get(str(season), {}).get('MISC_FPTS', 0),
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