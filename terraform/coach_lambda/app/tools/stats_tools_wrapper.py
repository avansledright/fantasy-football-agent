# app/tools/stats_tools_wrapper.py
"""
Wrapper functions that provide context-aware stats tools with current week information.
"""

from typing import Dict, Any, List, Optional
from functools import partial
from strands import tool
from app.tools.stats import (
    get_previous_week_stats as _get_previous_week_stats,
    get_player_recent_trends as _get_player_recent_trends,
    get_position_leaders_by_week as _get_position_leaders_by_week,
    get_week_schedule_and_completion_status as _get_week_schedule_and_completion_status
)

def create_context_aware_stats_tools(current_week: int):
    """
    Create stats tools that are aware of the current week context.
    
    Args:
        current_week: The current NFL week being analyzed
        
    Returns:
        Tuple of context-aware tool functions
    """
    
    @tool
    def get_previous_week_stats(
        week: int, 
        player_names: Optional[List[str]] = None,
        position: Optional[str] = None,
        team: Optional[str] = None,
        min_points: Optional[float] = None,
        completed_games_only: bool = True
    ) -> Dict[str, Any]:
        """Get fantasy football stats from previous weeks in 2025 season.
        
        Args:
            week: Week number to get stats for (1-18). Use week-1 for "previous week"
            player_names: Optional list of specific player names to filter
            position: Optional position filter (QB, RB, WR, TE, K, DST)
            team: Optional team filter (3-letter team code)
            min_points: Optional minimum fantasy points filter
            completed_games_only: Filter out games that haven't been played yet
        
        Returns:
            Dict with stats data including player performances, averages, and trends
        """
        return _get_previous_week_stats(
            week=week,
            player_names=player_names,
            position=position,
            team=team,
            min_points=min_points,
            completed_games_only=completed_games_only,
            current_week=current_week
        )
    
    @tool
    def get_player_recent_trends(
        player_name: str,
        weeks_back: int = 4
    ) -> Dict[str, Any]:
        """Get recent performance trends for a specific player.
        
        Args:
            player_name: Full player name to analyze
            weeks_back: Number of previous weeks to analyze (default 4)
        
        Returns:
            Dict with trend analysis including week-by-week performance and averages
        """
        return _get_player_recent_trends(player_name, weeks_back)
    
    @tool
    def get_position_leaders_by_week(
        week: int,
        position: str,
        limit: int = 10
    ) -> Dict[str, Any]:
        """Get top performers at a position for a specific week.
        
        Args:
            week: Week number (1-18)
            position: Position to analyze (QB, RB, WR, TE, K, DST)
            limit: Number of top players to return (default 10)
        
        Returns:
            Dict with top performers and position analysis
        """
        return _get_position_leaders_by_week(week, position, limit)
    
    @tool
    def get_week_schedule_and_completion_status(week: int) -> Dict[str, Any]:
        """Get NFL game schedule for a week with completion status for each game.
        
        Args:
            week: NFL week number (1-18)
        
        Returns:
            Dict with game schedule and completion status information
        """
        return _get_week_schedule_and_completion_status(week)
    
    @tool
    def get_optimal_analysis_week() -> Dict[str, Any]:
        """Get the optimal week to analyze for recent performance data.
        
        Returns:
            Dict with recommended analysis parameters based on current week
        """
        if current_week <= 1:
            return {
                "recommended_week": None,
                "analysis": "No previous weeks available for analysis",
                "suggestion": "Focus on projections and 2024 historical data"
            }
        
        prev_week = current_week - 1
        return {
            "current_week": current_week,
            "recommended_week": prev_week,
            "analysis": f"Week {prev_week} is the most recent completed week",
            "suggestion": f"Use get_previous_week_stats(week={prev_week}) for latest performance data"
        }
    
    return (
        get_previous_week_stats,
        get_player_recent_trends,
        get_position_leaders_by_week,
        get_week_schedule_and_completion_status,
        get_optimal_analysis_week
    )