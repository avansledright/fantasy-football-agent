"""
Fantasy Football Tools with Strands SDK Integration
Implements specific fantasy football analysis tools
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from strands import tool

logger = logging.getLogger(__name__)

class FantasyFootballTools:
    """Fantasy football analysis tools"""
    
    def __init__(self, db_client):
        self.db = db_client
        self.current_context = {}

    def update_context(self, context: Dict[str, Any]):
        """Update the current context for week-aware operations"""
        self.current_context = context
    def get_team_roster(self, team_id: str) -> Dict[str, Any]:
        """Get detailed team roster information"""
        try:
            roster_data = self.db.get_team_roster(team_id)
            
            if not roster_data:
                return {"error": f"Team {team_id} not found"}
            
            # Enhance roster data with player stats
            enhanced_players = []
            
            for player in roster_data.get('players', []):
                player_stats = self.db.get_player_stats(player['player_id'])
                
                enhanced_player = {
                    **player,
                    'stats': player_stats.get('current_season_stats', {}) if player_stats else {},
                    'projections': player_stats.get('projections', {}) if player_stats else {}
                }
                
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
        """Get comprehensive player statistics"""
        try:
            # Search for player by name
            players = self.db.search_players_by_name(player_name)
            
            if not players:
                return {"error": f"Player {player_name} not found"}
            
            # Get the best match (exact name match preferred)
            player = None
            for p in players:
                if p['player_name'].lower() == player_name.lower():
                    player = p
                    break
            
            if not player:
                player = players[0]  # Use first match if no exact match
            
            # Extract relevant stats
            current_stats = player.get('current_season_stats', {}).get(str(season), {})
            historical_stats = player.get('historical_seasons', {})
            projections = player.get('projections', {}).get(str(season), {})
            
            return {
                "player_info": {
                    "name": player['player_name'],
                    "position": player['position'],
                    "player_id": player['player_id']
                },
                "current_season_stats": current_stats,
                "historical_seasons": historical_stats,
                "projections": projections,
                "recent_performance": self._get_recent_performance(current_stats),
                "season_outlook": self._analyze_season_outlook(projections, historical_stats)
            }
            
        except Exception as e:
            logger.error(f"Error getting player stats: {str(e)}")
            return {"error": "Failed to retrieve player statistics"}
    
    def get_waiver_recommendations(self, position: str = None, team_id: str = None) -> List[Dict[str, Any]]:
        """Get waiver wire pickup recommendations"""
        try:
            # Get team needs if team_id provided
            team_needs = []
            if team_id:
                roster_data = self.get_team_roster(team_id)
                team_needs = self._analyze_team_needs(roster_data)
            
            # Get available players
            waiver_players = self.db.get_waiver_wire_players(
                position=position,
                min_ownership=0,
                max_ownership=50,
                context=self.current_context
            )
            
            # Enhance with projections and recommendations
            recommendations = []
            
            for player in waiver_players:
                logger.info(f"Player_name == {player['player_name']}")
                player_stats = self.get_player_stats(player['player_name'])
                
                if player_stats and not player_stats.get('error'):
                    recommendation = {
                        "player_name": player['player_name'],
                        "position": player['position'],
                        "team": player['team'],
                        "ownership_percentage": player['percent_owned'],
                        "injury_status": player.get('injury_status', 'UNKNOWN'),
                        "weekly_projections": player.get('weekly_projections', {}),
                        "season_projection": player_stats.get('projections', {}).get('MISC_FPTS', 0),
                        "recommendation_score": self._calculate_recommendation_score(player, player_stats, team_needs)
                    }
                    
                    recommendations.append(recommendation)
            
            # Sort by recommendation score
            recommendations.sort(key=lambda x: x['recommendation_score'], reverse=True)
            
            return recommendations[:15]  # Return top 15 recommendations
            
        except Exception as e:
            logger.error(f"Error getting waiver recommendations: {str(e)}")
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
                        "name": player1_stats['player_info']['name'],
                        "position": player1_stats['player_info']['position']
                    },
                    "player2": {
                        "name": player2_stats['player_info']['name'],
                        "position": player2_stats['player_info']['position']
                    }
                },
                "week_projection": {
                    "player1": self._get_week_projection(player1_stats, current_week),
                    "player2": self._get_week_projection(player2_stats, current_week)
                },
                "season_performance": {
                    "player1": self._get_season_average(player1_stats),
                    "player2": self._get_season_average(player2_stats)
                },
                "recent_trends": {
                    "player1": self._get_recent_trend(player1_stats),
                    "player2": self._get_recent_trend(player2_stats)
                },
                "recommendation": self._generate_start_sit_recommendation(player1_stats, player2_stats, current_week)
            }
            
            return comparison
            
        except Exception as e:
            logger.error(f"Error comparing players: {str(e)}")
            return {"error": "Failed to compare players"}
    
    def get_matchup_analysis(self, team_id: str, week: int = None) -> Dict[str, Any]:
        """Get matchup analysis for team players"""
        try:
            roster_data = self.get_team_roster(team_id)
            
            if roster_data.get('error'):
                return roster_data
            
            current_week = week or self._get_current_week()
            
            matchup_analysis = {
                "week": current_week,
                "team_id": team_id,
                "player_matchups": [],
                "overall_outlook": {}
            }
            
            good_matchups = 0
            total_starters = 0
            
            for player in roster_data['players']:
                if player['status'] == 'starter':
                    total_starters += 1
                    player_analysis = self._analyze_player_matchup(player, current_week)
                    matchup_analysis["player_matchups"].append(player_analysis)
                    
                    if player_analysis.get('matchup_rating', 0) >= 7:
                        good_matchups += 1
            
            matchup_analysis["overall_outlook"] = {
                "favorable_matchups": good_matchups,
                "total_starters": total_starters,
                "outlook_rating": (good_matchups / total_starters) * 10 if total_starters > 0 else 0
            }
            
            return matchup_analysis
            
        except Exception as e:
            logger.error(f"Error getting matchup analysis: {str(e)}")
            return {"error": "Failed to analyze matchups"}
    
    def optimize_lineup(self, team_id: str, week: int = None) -> Dict[str, Any]:
        """Get optimal lineup recommendations"""
        try:
            roster_data = self.get_team_roster(team_id)
            
            if roster_data.get('error'):
                return roster_data
            
            current_week = week or self._get_current_week()
            
            # Analyze all available players
            player_projections = []
            
            for player in roster_data['players']:
                if player['injury_status'] not in ['INJURY_RESERVE', 'OUT']:
                    projection = self._get_detailed_projection(player, current_week)
                    player_projections.append(projection)
            
            # Optimize lineup based on projections
            optimal_lineup = self._create_optimal_lineup(player_projections)
            current_lineup = self._get_current_lineup(roster_data['players'])
            
            return {
                "week": current_week,
                "team_id": team_id,
                "current_lineup": current_lineup,
                "optimal_lineup": optimal_lineup,
                "projected_improvement": optimal_lineup['total_points'] - current_lineup['total_points'],
                "recommendations": self._generate_lineup_recommendations(current_lineup, optimal_lineup)
            }
            
        except Exception as e:
            logger.error(f"Error optimizing lineup: {str(e)}")
            return {"error": "Failed to optimize lineup"}
    
    def get_injury_report(self, team_id: str = None) -> List[Dict[str, Any]]:
        """Get injury status for team players or all players"""
        try:
            if team_id:
                roster_data = self.get_team_roster(team_id)
                if roster_data.get('error'):
                    return [roster_data]
                
                injured_players = []
                for player in roster_data['players']:
                    if player['injury_status'] not in ['Healthy', 'ACTIVE']:
                        injured_players.append({
                            "name": player['name'],
                            "position": player['position'],
                            "team": player['team'],
                            "injury_status": player['injury_status'],
                            "roster_slot": player['slot'],
                            "impact_level": self._assess_injury_impact(player)
                        })
                
                return injured_players
            else:
                # Get league-wide injury report (top impactful injuries)
                return self._get_league_injury_report()
                
        except Exception as e:
            logger.error(f"Error getting injury report: {str(e)}")
            return [{"error": "Failed to get injury report"}]
    
    # Helper methods
    
    def _get_roster_counts(self, players: List[Dict]) -> Dict[str, int]:
        """Get roster position counts"""
        counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "K": 0, "DST": 0}
        
        for player in players:
            position = player.get('position', '')
            if position in counts:
                counts[position] += 1
        
        return counts
    
    def _get_recent_performance(self, current_stats: Dict) -> Dict[str, Any]:
        """Analyze recent performance trends"""
        weeks = list(current_stats.keys())
        if len(weeks) < 2:
            return {"trend": "insufficient_data"}
        
        recent_weeks = sorted(weeks, key=int)[-3:]  # Last 3 weeks
        recent_points = []
        
        for week in recent_weeks:
            week_data = current_stats.get(week, {})
            points = float(week_data.get('fantasy_points', 0))  # Convert to float
            recent_points.append(points)
        
        if len(recent_points) >= 2:
            trend = "improving" if recent_points[-1] > recent_points[0] else "declining"
        else:
            trend = "stable"
        
        return {
            "trend": trend,
            "recent_average": sum(recent_points) / len(recent_points) if recent_points else 0,
            "last_three_weeks": recent_points
        }
    
    def _analyze_season_outlook(self, projections: Dict, historical: Dict) -> Dict[str, Any]:
        """Analyze player's season outlook"""
        projected_points = float(projections.get('MISC_FPTS', 0))  # Convert to float
        
        # Compare to last year if available
        last_year_points = 0
        if '2024' in historical:
            last_year_points = float(historical['2024'].get('season_totals', {}).get('MISC_FPTS', 0))  # Convert to float
        
        outlook = "unknown"
        if projected_points > last_year_points * 1.1:
            outlook = "improving"
        elif projected_points < last_year_points * 0.9:
            outlook = "declining"
        else:
            outlook = "stable"
        
        return {
            "outlook": outlook,
            "projected_points": projected_points,
            "last_year_points": last_year_points
        }
    
    def _analyze_team_needs(self, roster_data: Dict) -> List[str]:
        """Analyze team positional needs"""
        if roster_data.get('error'):
            return []
        
        needs = []
        position_depth = {"QB": 0, "RB": 0, "WR": 0, "TE": 0}
        
        for player in roster_data.get('players', []):
            pos = player.get('position', '')
            if pos in position_depth and player.get('injury_status') != 'INJURY_RESERVE':
                position_depth[pos] += 1
        
        # Identify needs based on depth
        if position_depth['RB'] < 4:
            needs.append('RB')
        if position_depth['WR'] < 5:
            needs.append('WR')
        if position_depth['TE'] < 2:
            needs.append('TE')
        if position_depth['QB'] < 2:
            needs.append('QB')
        
        return needs
    
    def _calculate_recommendation_score(self, waiver_player: Dict, player_stats: Dict, team_needs: List[str]) -> float:
        """Calculate recommendation score for waiver player"""
        score = 0
        
        # Base score from projections
        projected_points = float(player_stats.get('projections', {}).get('MISC_FPTS', 0))  # Convert to float
        score += projected_points / 20  # Normalize
        
        # Bonus for team needs
        if waiver_player['position'] in team_needs:
            score += 2
        
        # Penalty for high ownership
        ownership_penalty = float(waiver_player['percent_owned']) / 10  # Convert to float
        score -= ownership_penalty
        
        # Injury status consideration
        if waiver_player.get('injury_status') in ['QUESTIONABLE', 'DOUBTFUL']:
            score -= 1
        elif waiver_player.get('injury_status') == 'OUT':
            score -= 3
        
        return max(0, score)
    
    def _get_current_week(self) -> int:
        """Get current NFL week from context"""
        if self.current_context and 'week' in self.current_context:
            try:
                return int(self.current_context['week'])
            except (ValueError, TypeError):
                pass
        return 1  # Fallback
    
    def _get_week_projection(self, player_stats: Dict, week: int) -> float:
        """Get player projection for specific week"""
        projections = player_stats.get('projections', {})
        weekly_proj = projections.get('weekly', {}).get(str(week))
        
        if weekly_proj:
            return float(weekly_proj.get('fantasy_points', 0))  # Convert to float
        
        # Fallback to season average
        season_proj = float(projections.get('MISC_FPTS', 0))  # Convert to float
        return season_proj / 17 if season_proj > 0 else 0
    
    def _get_season_average(self, player_stats: Dict) -> float:
        """Get player's season average fantasy points"""
        current_stats = player_stats.get('current_season_stats', {})
        
        if not current_stats:
            return 0
        
        total_points = sum(float(week.get('fantasy_points', 0)) for week in current_stats.values())  # Convert to float
        games_played = len(current_stats)
        
        return total_points / games_played if games_played > 0 else 0
    
    def _get_recent_trend(self, player_stats: Dict) -> str:
        """Get player's recent performance trend"""
        current_stats = player_stats.get('current_season_stats', {})
        
        if len(current_stats) < 2:
            return "insufficient_data"
        
        weeks = sorted(current_stats.keys(), key=int)
        recent_weeks = weeks[-2:]
        
        if len(recent_weeks) == 2:
            week1_points = float(current_stats[recent_weeks[0]].get('fantasy_points', 0))  # Convert to float
            week2_points = float(current_stats[recent_weeks[1]].get('fantasy_points', 0))  # Convert to float
            
            if week2_points > week1_points * 1.1:
                return "trending_up"
            elif week2_points < week1_points * 0.9:
                return "trending_down"
            else:
                return "stable"
        
        return "stable"
    
    def _generate_start_sit_recommendation(self, player1_stats: Dict, player2_stats: Dict, week: int) -> Dict[str, Any]:
        """Generate start/sit recommendation between two players"""
        player1_proj = float(self._get_week_projection(player1_stats, week))  # Convert to float
        player2_proj = float(self._get_week_projection(player2_stats, week))  # Convert to float
        
        if player1_proj > player2_proj:
            recommended_player = player1_stats['player_info']['name']
            confidence = min(((player1_proj - player2_proj) / max(player1_proj, 1)) * 100, 95)
        else:
            recommended_player = player2_stats['player_info']['name']
            confidence = min(((player2_proj - player1_proj) / max(player2_proj, 1)) * 100, 95)
        
        return {
            "recommended_player": recommended_player,
            "confidence_level": round(confidence, 1),
            "reasoning": f"Based on Week {week} projections and recent performance trends"
        }
    
    def _analyze_player_matchup(self, player: Dict, week: int) -> Dict[str, Any]:
        """Analyze individual player matchup"""
        # This would typically involve opponent analysis, but simplified for now
        return {
            "player_name": player['name'],
            "position": player['position'],
            "opponent": "TBD",  # Would need schedule data
            "matchup_rating": 7,  # Simplified rating 1-10
            "key_factors": ["Opponent strength", "Recent performance", "Weather conditions"]
        }
    
    def _get_detailed_projection(self, player: Dict, week: int) -> Dict[str, Any]:
        """Get detailed projection for a player"""
        player_stats = self.db.get_player_stats(player['player_id'])
        
        if not player_stats:
            return {
                "player": player,
                "projected_points": 0,
                "confidence": 0
            }
        
        projected_points = self._get_week_projection(player_stats, week)
        
        return {
            "player": player,
            "projected_points": projected_points,
            "confidence": 85,  # Simplified confidence score
            "position": player['position'],
            "eligible_slots": self._get_eligible_slots(player['position'])
        }
    
    def _get_eligible_slots(self, position: str) -> List[str]:
        """Get eligible roster slots for position"""
        slot_mapping = {
            "QB": ["QB", "OP"],
            "RB": ["RB1", "RB2", "FLEX", "OP"],
            "WR": ["WR1", "WR2", "FLEX", "OP"],
            "TE": ["TE", "FLEX", "OP"],
            "K": ["K"],
            "DST": ["DST"]
        }
        return slot_mapping.get(position, [])
    
    def _create_optimal_lineup(self, player_projections: List[Dict]) -> Dict[str, Any]:
        """Create optimal lineup from available players"""
        # Simplified lineup optimization
        lineup_slots = {
            "QB": 1, "RB1": 1, "RB2": 1, "WR1": 1, "WR2": 1, 
            "TE": 1, "FLEX": 1, "K": 1, "DST": 1, "OP": 1
        }
        
        optimal_lineup = {}
        used_players = set()
        total_points = 0
        
        # Sort players by projected points
        sorted_players = sorted(player_projections, key=lambda x: x['projected_points'], reverse=True)
        
        # Fill required positions first
        for slot in ["QB", "RB1", "RB2", "WR1", "WR2", "TE", "K", "DST"]:
            for player_proj in sorted_players:
                player = player_proj['player']
                if (player['player_id'] not in used_players and 
                    slot in player_proj['eligible_slots']):
                    optimal_lineup[slot] = player
                    used_players.add(player['player_id'])
                    total_points += player_proj['projected_points']
                    break
        
        # Fill FLEX and OP positions
        flex_eligible = ["RB", "WR", "TE"]
        for slot in ["FLEX", "OP"]:
            for player_proj in sorted_players:
                player = player_proj['player']
                if (player['player_id'] not in used_players and 
                    (player['position'] in flex_eligible or slot == "OP")):
                    optimal_lineup[slot] = player
                    used_players.add(player['player_id'])
                    total_points += player_proj['projected_points']
                    break
        
        return {
            "lineup": optimal_lineup,
            "total_points": round(total_points, 2)
        }
    
    def _get_current_lineup(self, players: List[Dict]) -> Dict[str, Any]:
        """Get current starting lineup"""
        current_lineup = {}
        total_points = 0
        
        for player in players:
            if player['status'] == 'starter':
                slot = player['slot']
                current_lineup[slot] = player
                
                # Get projected points for current player
                player_stats = self.db.get_player_stats(player['player_id'])
                if player_stats:
                    projected_points = self._get_week_projection(player_stats, self._get_current_week())
                    total_points += projected_points
        
        return {
            "lineup": current_lineup,
            "total_points": round(total_points, 2)
        }
    
    def _generate_lineup_recommendations(self, current: Dict, optimal: Dict) -> List[str]:
        """Generate lineup change recommendations"""
        recommendations = []
        
        current_players = {slot: player['name'] for slot, player in current['lineup'].items()}
        optimal_players = {slot: player['name'] for slot, player in optimal['lineup'].items()}
        
        for slot in current_players:
            if slot in optimal_players and current_players[slot] != optimal_players[slot]:
                recommendations.append(
                    f"Consider starting {optimal_players[slot]} over {current_players[slot]} at {slot}"
                )
        
        return recommendations
    
    def _assess_injury_impact(self, player: Dict) -> str:
        """Assess the fantasy impact of a player's injury"""
        position = player['position']
        slot = player['slot']
        
        if slot in ['QB', 'RB1', 'RB2', 'WR1', 'WR2', 'TE']:
            return "HIGH"
        elif slot in ['FLEX', 'OP']:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _get_league_injury_report(self) -> List[Dict[str, Any]]:
        """Get league-wide injury report for high-impact players"""
        # This would scan all players for injuries
        # Simplified implementation
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
    """Analyze a player's performance and statistics for the season"""
    if fantasy_tools_instance is None:
        return {"error": "Fantasy tools not initialized"}
    return fantasy_tools_instance.get_player_stats(player_name, season)

@tool
def compare_roster_players(player1: str, player2: str, week: int = None) -> Dict[str, Any]:
    """Compare two players for start/sit decisions"""
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
def analyze_waiver_opportunities_with_projections(position: str = None, team_id: str = None, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Get waiver wire recommendations with detailed projections"""
    if fantasy_tools_instance is None:
        return [{"error": "Fantasy tools not initialized"}]
    
    # Update context if provided
    if context:
        fantasy_tools_instance.update_context(context)
    
    return fantasy_tools_instance.get_waiver_recommendations(position, team_id)
@tool
def get_position_waiver_targets(position: str, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Get top waiver wire targets for a specific position"""
    if fantasy_tools_instance is None:
        return [{"error": "Fantasy tools not initialized"}]
    
    # Update context if provided
    if context:
        fantasy_tools_instance.update_context(context)
    
    return fantasy_tools_instance.get_waiver_recommendations(position=position)