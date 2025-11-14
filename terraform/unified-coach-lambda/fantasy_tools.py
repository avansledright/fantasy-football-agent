"""
Fantasy Football Tools with Strands SDK Integration
Implements specific fantasy football analysis tools
UPDATED for fantasy-football-players-updated table with seasons.{year}.* structure
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from strands import tool
from utils import convert_nfl_defense_name

logger = logging.getLogger(__name__)

class FantasyFootballTools:
    """Fantasy football analysis tools"""
    
    def __init__(self, db_client):
        self.db = db_client
        self.current_context = {}
        self.season_year = "2025"  # Current season

    def update_context(self, context: Dict[str, Any]):
        """Update the current context for week-aware operations"""
        self.current_context = context
    
    def _get_weekly_projection(self, player_stats: Dict, current_week: int = None) -> float:
        """Extract weekly projection from player stats using NEW structure
        
        NEW: seasons.{year}.weekly_projections.{week}
        """
        # Extract from NEW structure
        seasons = player_stats.get('seasons', {})
        season_data = seasons.get(self.season_year, {})
        weekly_projections = season_data.get('weekly_projections', {})
        
        logger.info(f"Weekly projections: {weekly_projections}")
        
        # If current_week is specified, try to get that week's projection
        if current_week and str(current_week) in weekly_projections:
            proj_value = weekly_projections[str(current_week)]
            # Handle both direct numbers and objects with fantasy_points
            if isinstance(proj_value, dict):
                return float(proj_value.get('fantasy_points', 0))
            else:
                return float(proj_value)
        
        # Otherwise, get the most recent week's projection
        available_weeks = [int(week) for week in weekly_projections.keys() if str(week).isdigit()]
        if available_weeks:
            latest_week = max(available_weeks)
            proj_value = weekly_projections[str(latest_week)]
            if isinstance(proj_value, dict):
                return float(proj_value.get('fantasy_points', 0))
            else:
                return float(proj_value)
        
        # Final fallback to season average
        season_projections = season_data.get('season_projections', {})
        season_total = float(season_projections.get('MISC_FPTS', 0))
        if season_total > 0:
            return round(season_total / 17, 1)  # Average per game
        
        return 0.0
    
    def get_team_roster(self, team_id: str) -> Dict[str, Any]:
        """Get detailed team roster information"""
        try:
            roster_data = self.db.get_team_roster(team_id)

            if not roster_data:
                return {"error": f"Team {team_id} not found"}

            # Batch load all player stats at once instead of individual lookups
            player_ids = [player['player_id'] for player in roster_data.get('players', [])]
            all_player_stats = self.db.batch_get_player_stats(player_ids)

            # Enhance roster data with player stats
            enhanced_players = []

            for player in roster_data.get('players', []):
                player_stats = all_player_stats.get(player['player_id'])

                if player_stats:
                    # Extract from NEW structure
                    seasons = player_stats.get('seasons', {})
                    season_2025 = seasons.get(self.season_year, {})

                    enhanced_player = {
                        **player,
                        'stats': season_2025.get('weekly_stats', {}),
                        'projections': season_2025.get('season_projections', {}),
                        'injury_status': season_2025.get('injury_status', 'UNKNOWN')
                    }
                else:
                    enhanced_player = player

                enhanced_players.append(enhanced_player)

            return {
                "team_info": {
                    "team_id": roster_data['team_id'],
                    "team_name": roster_data.get('team_name', ''),
                    "owner": roster_data.get('owner', ''),
                    "league_name": roster_data.get('league_name', ''),
                    "last_updated": roster_data.get('last_updated', '')
                },
                "players": enhanced_players,
                "roster_counts": self._get_roster_counts(enhanced_players)
            }

        except Exception as e:
            logger.error(f"Error getting team roster: {str(e)}")
            return {"error": "Failed to retrieve team roster"}
    
    def get_player_stats(self, player_name: str, season: int = 2025) -> Dict[str, Any]:
        """Get comprehensive player statistics using NEW structure"""
        try:
            # Search for player by name
            if "DST" in player_name:
                logger.info(f"Found defense: {player_name}")
                player_name = player_name.replace("#DST", "")

            # Normalize name format (handles "LastName, FirstName" -> "FirstName LastName")
            normalized_name = self.db._normalize_player_name(player_name)

            players = self.db.search_players_by_name(player_name)

            if not players:
                return {"error": f"Player {player_name} not found"}

            # Get the best match (exact name match preferred, using normalized name)
            player = None
            for p in players:
                if p['player_name'].lower() == normalized_name.lower():
                    player = p
                    break

            if not player:
                player = players[0]  # Use first match if no exact match
            
            # Extract relevant stats from NEW structure
            seasons = player.get('seasons', {})
            season_str = str(season)
            season_data = seasons.get(season_str, {})
            
            # Get 2024 historical data for context
            season_2024 = seasons.get('2024', {})
            
            current_stats = season_data.get('weekly_stats', {})
            season_projections = season_data.get('season_projections', {})
            weekly_projections = season_data.get('weekly_projections', {})
            
            return {
                "player_info": {
                    "name": player['player_name'],
                    "position": player['position'],
                    "player_id": player['player_id']
                },
                "current_season_stats": current_stats,
                "historical_seasons": {'2024': season_2024},  # Include 2024 for context
                "projections": season_projections,
                "weekly_projections": weekly_projections,
                "injury_status": season_data.get('injury_status', 'UNKNOWN'),
                "percent_owned": season_data.get('percent_owned', 0),
                "recent_performance": self._get_recent_performance(current_stats),
                "season_outlook": self._analyze_season_outlook(season_projections, {'2024': season_2024})
            }
            
        except Exception as e:
            logger.error(f"Error getting player stats: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": "Failed to retrieve player statistics"}
    
    def get_waiver_recommendations(self, position: str = None, team_id: str = None) -> List[Dict[str, Any]]:
        """Get waiver wire pickup recommendations"""
        try:
            current_week = self._get_current_week()
            
            # Get team needs if team_id provided
            team_needs = []
            if team_id:
                roster_data = self.get_team_roster(team_id)
                team_needs = self._analyze_team_needs(roster_data)
            
            # Get available players from unified table
            waiver_players = self.db.get_waiver_wire_players(
                position=position,
                min_ownership=0,
                max_ownership=80,
                context=self.current_context
            )
            
            # Enhance with projections and recommendations
            recommendations = []
            
            for player in waiver_players:
                logger.info(f"Processing waiver player: {player['player_name']}")
                
                if player['position'] == "D/ST":
                    player_lookup_name = convert_nfl_defense_name(player['player_name'])
                    logger.info(f"Defense converted: {player['player_name']} → {player_lookup_name}")
                else:
                    player_lookup_name = player['player_name']
                
                player_stats = self.get_player_stats(player_lookup_name)
                
                if player_stats and not player_stats.get('error'):
                    recommendation = {
                        "player_name": player['player_name'],
                        "position": player['position'],
                        "team": player['team'],
                        "ownership_percentage": player['percent_owned'],
                        "injury_status": player.get('injury_status', 'UNKNOWN'),
                        "weekly_projections": player.get('weekly_projections', {}),
                        "season_projection": self._get_weekly_projection(player_stats, current_week),
                        "recommendation_score": self._calculate_recommendation_score(
                            player, player_stats, team_needs, current_week
                        )
                    }
                    
                    recommendations.append(recommendation)
            
            # Sort by recommendation score
            recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
            logger.info(f"Returning {len(recommendations[:15])} waiver recommendations")
            return recommendations[:15]  # Return top 15 recommendations
            
        except Exception as e:
            logger.error(f"Error getting waiver recommendations: {str(e)}")
            import traceback
            traceback.print_exc()
            return [{"error": "Failed to get waiver recommendations"}]
    
    def compare_players(self, player1: str, player2: str, week: int = None) -> Dict[str, Any]:
        """Compare two players for start/sit decisions"""
        try:
            player1_stats = self.get_player_stats(player1)
            player2_stats = self.get_player_stats(player2)
            
            if player1_stats.get('error') or player2_stats.get('error'):
                return {"error": "One or both players not found"}
            
            current_week = week or self._get_current_week()
            
            comparison = {
                "players": {
                    "player1": {
                        "name": player1,
                        "position": player1_stats['player_info']['position'],
                        "projected_points": self._get_weekly_projection(player1_stats, current_week),
                        "recent_performance": player1_stats['recent_performance'],
                        "injury_status": player1_stats.get('injury_status', 'UNKNOWN')
                    },
                    "player2": {
                        "name": player2,
                        "position": player2_stats['player_info']['position'],
                        "projected_points": self._get_weekly_projection(player2_stats, current_week),
                        "recent_performance": player2_stats['recent_performance'],
                        "injury_status": player2_stats.get('injury_status', 'UNKNOWN')
                    }
                },
                "recommendation": None,
                "reasoning": []
            }
            
            # Determine recommendation
            p1_proj = comparison['players']['player1']['projected_points']
            p2_proj = comparison['players']['player2']['projected_points']
            
            if p1_proj > p2_proj:
                comparison['recommendation'] = player1
                comparison['reasoning'].append(f"{player1} has higher projected points ({p1_proj} vs {p2_proj})")
            else:
                comparison['recommendation'] = player2
                comparison['reasoning'].append(f"{player2} has higher projected points ({p2_proj} vs {p1_proj})")
            
            # Consider injury status
            if comparison['players']['player1']['injury_status'] not in ['ACTIVE', 'UNKNOWN']:
                comparison['reasoning'].append(f"{player1} has injury concerns: {comparison['players']['player1']['injury_status']}")
            
            if comparison['players']['player2']['injury_status'] not in ['ACTIVE', 'UNKNOWN']:
                comparison['reasoning'].append(f"{player2} has injury concerns: {comparison['players']['player2']['injury_status']}")
            
            return comparison
            
        except Exception as e:
            logger.error(f"Error comparing players: {str(e)}")
            return {"error": "Failed to compare players"}
    
    def get_injury_report(self, team_id: str = None) -> List[Dict[str, Any]]:
        """Get injury report for team or league"""
        try:
            if team_id:
                return self._get_team_injury_report(team_id)
            else:
                return self._get_league_injury_report()
        except Exception as e:
            logger.error(f"Error getting injury report: {str(e)}")
            return [{"error": "Failed to get injury report"}]
    
    def _get_team_injury_report(self, team_id: str) -> List[Dict[str, Any]]:
        """Get injury report for specific team"""
        roster_data = self.get_team_roster(team_id)
        
        if roster_data.get('error'):
            return [roster_data]
        
        injuries = []
        
        for player in roster_data['players']:
            injury_status = player.get('injury_status', 'UNKNOWN')
            
            if injury_status not in ['ACTIVE', 'UNKNOWN']:
                injuries.append({
                    "player": player['name'],
                    "position": player['position'],
                    "injury_status": injury_status,
                    "slot": player.get('slot', 'N/A'),
                    "impact": self._assess_injury_impact(player)
                })
        
        if not injuries:
            return [{"message": f"No injury concerns for team {team_id}"}]
        
        return injuries
    
    # Helper methods
    def _get_current_week(self) -> int:
        """Get current NFL week from context"""
        return int(self.current_context.get('week', 1))
    
    def _get_roster_counts(self, players: List[Dict]) -> Dict[str, int]:
        """Count players by position"""
        counts = {}
        for player in players:
            pos = player['position']
            counts[pos] = counts.get(pos, 0) + 1
        return counts
    
    def _get_recent_performance(self, weekly_stats: Dict) -> Dict[str, Any]:
        """Calculate recent performance metrics from weekly_stats"""
        if not weekly_stats:
            return {"average_points": 0, "games_played": 0, "trend": "N/A"}
        
        # Get last 4 weeks
        weeks = sorted([int(w) for w in weekly_stats.keys() if str(w).isdigit()])[-4:]
        
        if not weeks:
            return {"average_points": 0, "games_played": 0, "trend": "N/A"}
        
        points = [float(weekly_stats[str(w)].get('fantasy_points', 0)) for w in weeks]
        avg_points = round(sum(points) / len(points), 2)
        
        # Simple trend analysis
        if len(points) >= 2:
            if points[-1] > points[-2]:
                trend = "UP"
            elif points[-1] < points[-2]:
                trend = "DOWN"
            else:
                trend = "STABLE"
        else:
            trend = "N/A"
        
        return {
            "average_points": avg_points,
            "games_played": len(weeks),
            "trend": trend,
            "recent_scores": points
        }
    
    def _analyze_season_outlook(self, projections: Dict, historical: Dict) -> str:
        """Analyze season outlook based on projections and history"""
        if not projections:
            return "Limited projection data available"
        
        season_projection = projections.get('MISC_FPTS', 0)
        
        if season_projection > 250:
            return "Elite fantasy performer - Top-tier weekly starter"
        elif season_projection > 180:
            return "Strong fantasy asset - Reliable weekly option"
        elif season_projection > 120:
            return "Solid contributor - Matchup-dependent starter"
        elif season_projection > 60:
            return "Depth piece - Useful for bye weeks and injuries"
        else:
            return "Limited fantasy value - Deep league option only"
    
    def _analyze_team_needs(self, roster_data: Dict) -> List[str]:
        """Analyze team positional needs"""
        if roster_data.get('error'):
            return []
        
        needs = []
        roster_counts = roster_data.get('roster_counts', {})
        
        # Check positional depth
        if roster_counts.get('RB', 0) < 3:
            needs.append('RB')
        if roster_counts.get('WR', 0) < 4:
            needs.append('WR')
        if roster_counts.get('QB', 0) < 2:
            needs.append('QB')
        if roster_counts.get('TE', 0) < 2:
            needs.append('TE')
        
        return needs
    
    def _calculate_recommendation_score(
        self, 
        player: Dict, 
        player_stats: Dict, 
        team_needs: List[str], 
        current_week: int
    ) -> float:
        """Calculate recommendation score for waiver player"""
        score = 0.0
        
        # Base score from projection
        projection = self._get_weekly_projection(player_stats, current_week)
        score += projection * 2  # Weight projections heavily
        
        # Ownership bonus (lower ownership = higher score)
        ownership = player.get('percent_owned', 50)
        if ownership < 25:
            score += 20
        elif ownership < 50:
            score += 10
        
        # Position need bonus
        if player['position'] in team_needs:
            score += 15
        
        # Injury penalty
        injury_status = player.get('injury_status', 'ACTIVE')
        if injury_status not in ['ACTIVE', 'UNKNOWN']:
            score -= 30
        
        return round(score, 2)
    
    def _assess_injury_impact(self, player: Dict) -> str:
        """Assess the fantasy impact of a player's injury"""
        position = player['position']
        slot = player.get('slot', '')
        
        if slot in ['QB', 'RB1', 'RB2', 'WR1', 'WR2', 'TE']:
            return "HIGH"
        elif slot in ['FLEX', 'OP']:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _get_league_injury_report(self) -> List[Dict[str, Any]]:
        """Get league-wide injury report for high-impact players"""
        return [
            {
                "message": "League-wide injury report not implemented yet",
                "suggestion": "Provide a specific team_id for team injury report"
            }
        ]


# Global instance for use in tools
fantasy_tools_instance = None

def initialize_fantasy_tools(db_client):
    """Initialize the global fantasy tools instance"""
    global fantasy_tools_instance
    fantasy_tools_instance = FantasyFootballTools(db_client)
    return fantasy_tools_instance

# Strands SDK Tools - These will be used by the Agent

@tool
def analyze_player_performance(player_name: str, season: int = 2025) -> Dict[str, Any]:
    """Analyze a player's performance and statistics for the season using unified table data"""
    if fantasy_tools_instance is None:
        return {"error": "Fantasy tools not initialized"}
    return fantasy_tools_instance.get_player_stats(player_name, season)

@tool
def compare_roster_players(player1: str, player2: str, week: int = None) -> Dict[str, Any]:
    """Compare two players for start/sit decisions using unified table data"""
    if fantasy_tools_instance is None:
        return {"error": "Fantasy tools not initialized"}
    return fantasy_tools_instance.compare_players(player1, player2, week)

@tool
def analyze_injury_impact(team_id: str = None) -> List[Dict[str, Any]]:
    """Get injury report and impact analysis for team players"""
    if fantasy_tools_instance is None:
        return [{"error": "Fantasy tools not initialized"}]
    return fantasy_tools_instance.get_injury_report(team_id)

@tool
def analyze_waiver_opportunities_with_projections(
    position: str = None, 
    team_id: str = None, 
    context: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """Get waiver wire recommendations with detailed projections from unified table"""
    if fantasy_tools_instance is None:
        return [{"error": "Fantasy tools not initialized"}]
    
    # Update context if provided
    if context:
        fantasy_tools_instance.update_context(context)
    
    return fantasy_tools_instance.get_waiver_recommendations(position, team_id)

@tool
def get_position_waiver_targets(position: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Get top waiver wire targets for a specific position from unified table"""
    if fantasy_tools_instance is None:
        return [{"error": "Fantasy tools not initialized"}]
    
    # Update context if provided
    if context:
        fantasy_tools_instance.update_context(context)
    
    return fantasy_tools_instance.get_waiver_recommendations(position=position)