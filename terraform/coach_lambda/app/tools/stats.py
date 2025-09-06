import os
from typing import Dict, Any, List, Optional
import boto3
from boto3.dynamodb.conditions import Key, Attr
from strands import tool
import json

DDB = boto3.resource("dynamodb")
TABLE_STATS_2025 = os.environ.get("DDB_TABLE_STATS_2025", "fantasy_football_2025_stats")

@tool
def get_previous_week_stats(
    week: int, 
    player_names: Optional[List[str]] = None,
    position: Optional[str] = None,
    team: Optional[str] = None,
    min_points: Optional[float] = None
) -> Dict[str, Any]:
    """Get fantasy football stats from previous weeks in 2025 season.
    
    Args:
        week: Week number to get stats for (1-18). Use week-1 for "previous week"
        player_names: Optional list of specific player names to filter
        position: Optional position filter (QB, RB, WR, TE, K, DST)
        team: Optional team filter (3-letter team code)
        min_points: Optional minimum fantasy points filter
    
    Returns:
        Dict with stats data including player performances, averages, and trends
    """
    table = DDB.Table(TABLE_STATS_2025)
    
    try:
        # Build filter expression
        filter_expr = Attr("season").eq(2025) & Attr("week").eq(week)
        
        if position:
            filter_expr = filter_expr & Attr("position").eq(position.upper())
        
        if team:
            filter_expr = filter_expr & Attr("team").eq(team.upper())
            
        if min_points is not None:
            filter_expr = filter_expr & Attr("fantasy_points").gte(min_points)
        
        # If specific players requested, add OR filter for them
        if player_names:
            player_filter = None
            for player_name in player_names:
                name_filter = Attr("player_name").eq(player_name)
                if player_filter is None:
                    player_filter = name_filter
                else:
                    player_filter = player_filter | name_filter
            filter_expr = filter_expr & player_filter
        
        # Scan with filter
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ProjectionExpression": "player_name, #pos, team, fantasy_points, opponent, updated_at",
            "ExpressionAttributeNames": {"#pos": "position"},
        }
        
        items = []
        resp = table.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        
        while "LastEvaluatedKey" in resp:
            resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **scan_kwargs)
            items.extend(resp.get("Items", []))
        
        # Process and format results
        if not items:
            return {
                "week": week,
                "total_players": 0,
                "players": [],
                "summary": f"No stats found for week {week} with given filters",
                "position_breakdown": {},
                "top_performers": []
            }
        
        # Sort by fantasy points descending
        items.sort(key=lambda x: float(x.get("fantasy_points", 0)), reverse=True)
        
        # Calculate summary stats
        total_points = sum(float(item.get("fantasy_points", 0)) for item in items)
        avg_points = round(total_points / len(items), 2) if items else 0
        
        # Position breakdown
        by_position = {}
        for item in items:
            pos = item.get("position", "UNKNOWN")
            if pos not in by_position:
                by_position[pos] = {"count": 0, "total_points": 0, "players": []}
            by_position[pos]["count"] += 1
            by_position[pos]["total_points"] += float(item.get("fantasy_points", 0))
            by_position[pos]["players"].append(item.get("player_name"))
        
        # Add averages to position breakdown
        for pos in by_position:
            count = by_position[pos]["count"]
            by_position[pos]["avg_points"] = round(by_position[pos]["total_points"] / count, 2) if count > 0 else 0
        
        # Format player results
        formatted_players = []
        for item in items:
            formatted_players.append({
                "name": item.get("player_name"),
                "position": item.get("position"),
                "team": item.get("team"),
                "opponent": item.get("opponent"),
                "fantasy_points": float(item.get("fantasy_points", 0)),
                "updated_at": item.get("updated_at")
            })
        
        return {
            "week": week,
            "total_players": len(items),
            "total_points": total_points,
            "average_points": avg_points,
            "players": formatted_players,
            "position_breakdown": by_position,
            "top_performers": formatted_players[:10],  # Top 10
            "summary": f"Week {week}: {len(items)} players, avg {avg_points} points"
        }
        
    except Exception as e:
        print(f"Error fetching week {week} stats: {str(e)}")
        return {
            "week": week,
            "error": str(e),
            "total_players": 0,
            "players": [],
            "summary": f"Error retrieving week {week} stats: {str(e)}"
        }

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
    table = DDB.Table(TABLE_STATS_2025)
    
    try:
        # Get all weeks for this player in 2025
        filter_expr = Attr("player_name").eq(player_name) & Attr("season").eq(2025)
        
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ProjectionExpression": "#w, fantasy_points, opponent, team, #pos",
            "ExpressionAttributeNames": {"#w": "week", "#pos": "position"},
        }
        
        items = []
        resp = table.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        
        while "LastEvaluatedKey" in resp:
            resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **scan_kwargs)
            items.extend(resp.get("Items", []))
        
        if not items:
            return {
                "player_name": player_name,
                "error": "No stats found for this player in 2025",
                "weeks_analyzed": 0,
                "trend": "no_data"
            }
        
        # Sort by week
        items.sort(key=lambda x: int(x.get("week", 0)))
        
        # Take last N weeks
        recent_weeks = items[-weeks_back:] if len(items) >= weeks_back else items
        
        # Calculate trends
        week_scores = [float(item.get("fantasy_points", 0)) for item in recent_weeks]
        recent_avg = round(sum(week_scores) / len(week_scores), 2) if week_scores else 0
        
        # Simple trend calculation (comparing first half vs second half)
        if len(week_scores) >= 2:
            mid = len(week_scores) // 2
            first_half = sum(week_scores[:mid]) / mid if mid > 0 else 0
            second_half = sum(week_scores[mid:]) / (len(week_scores) - mid)
            
            if second_half > first_half * 1.1:
                trend = "improving"
            elif second_half < first_half * 0.9:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"
        
        # Format week-by-week breakdown (completed games only)
        weekly_breakdown = []
        for item in completed_recent:
            weekly_breakdown.append({
                "week": int(item.get("week", 0)),
                "fantasy_points": float(item.get("fantasy_points", 0)),
                "opponent": item.get("opponent"),
                "team": item.get("team")
            })
        
        # Calculate season stats from all completed games
        all_completed = filter_completed_games_only(items)
        season_avg = round(sum(float(i.get("fantasy_points", 0)) for i in all_completed) / len(all_completed), 2) if all_completed else 0
        
        return {
            "player_name": player_name,
            "position": items[0].get("position") if items else "UNKNOWN",
            "weeks_analyzed": len(completed_recent),
            "recent_average": recent_avg,
            "trend": trend,
            "weekly_breakdown": weekly_breakdown,
            "season_games": len(all_completed),
            "total_weeks_in_db": len(items),
            "season_average": season_avg,
            "note": f"Analysis based on {len(all_completed)} completed games out of {len(items)} total weeks"
        }
        
    except Exception as e:
        print(f"Error analyzing trends for {player_name}: {str(e)}")
        return {
            "player_name": player_name,
            "error": str(e),
            "weeks_analyzed": 0,
            "trend": "error"
        }

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
    table = DDB.Table(TABLE_STATS_2025)
    
    try:
        filter_expr = (Attr("season").eq(2025) & 
                      Attr("week").eq(week) & 
                      Attr("position").eq(position.upper()))
        
        scan_kwargs = {
            "FilterExpression": filter_expr,
            "ProjectionExpression": "player_name, team, fantasy_points, opponent",
        }
        
        items = []
        resp = table.scan(**scan_kwargs)
        items.extend(resp.get("Items", []))
        
        while "LastEvaluatedKey" in resp:
            resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"], **scan_kwargs)
            items.extend(resp.get("Items", []))
        
        if not items:
            return {
                "week": week,
                "position": position.upper(),
                "error": f"No {position} stats found for week {week}",
                "leaders": []
            }
        
        # Sort by fantasy points and take top performers
        items.sort(key=lambda x: float(x.get("fantasy_points", 0)), reverse=True)
        top_performers = items[:limit]
        
        # Calculate position stats
        all_scores = [float(item.get("fantasy_points", 0)) for item in items]
        position_avg = round(sum(all_scores) / len(all_scores), 2) if all_scores else 0
        
        return {
            "week": week,
            "position": position.upper(),
            "total_players": len(items),
            "position_average": position_avg,
            "leaders": [
                {
                    "rank": i + 1,
                    "player_name": item.get("player_name"),
                    "team": item.get("team"),
                    "opponent": item.get("opponent"),
                    "fantasy_points": float(item.get("fantasy_points", 0))
                }
                for i, item in enumerate(top_performers)
            ]
        }
        
    except Exception as e:
        print(f"Error getting {position} leaders for week {week}: {str(e)}")
        return {
            "week": week,
            "position": position.upper(),
            "error": str(e),
            "leaders": []
        }

@tool
def get_week_schedule_and_completion_status(week: int) -> Dict[str, Any]:
    """Get NFL game schedule for a week with completion status for each game.
    
    Args:
        week: NFL week number (1-18)
    
    Returns:
        Dict with game schedule and completion status information
    """
    try:
        schedule = get_week_game_schedule(week)
        completed_teams = get_completed_teams_for_week(week)
        
        if not schedule:
            return {
                "week": week,
                "error": f"No schedule data available for week {week}",
                "games": [],
                "completion_summary": {}
            }
        
        # Categorize games by status
        completed_games = [g for g in schedule if g["is_completed"]]
        in_progress_games = [g for g in schedule if g["is_in_progress"]]
        upcoming_games = [g for g in schedule if g["status"] == "upcoming"]
        
        # Calculate completion stats
        total_games = len(schedule)
        completed_count = len(completed_games)
        completion_percentage = round((completed_count / total_games) * 100, 1) if total_games > 0 else 0
        
        return {
            "week": week,
            "total_games": total_games,
            "completed_games": completed_count,
            "in_progress_games": len(in_progress_games),
            "upcoming_games": len(upcoming_games),
            "completion_percentage": completion_percentage,
            "completed_teams": list(completed_teams),
            "games": schedule,
            "completion_summary": {
                "completed": [f"{g['away_team']} @ {g['home_team']}" for g in completed_games],
                "in_progress": [f"{g['away_team']} @ {g['home_team']}" for g in in_progress_games],
                "upcoming": [f"{g['away_team']} @ {g['home_team']}" for g in upcoming_games]
            },
            "analysis_note": f"Week {week}: {completed_count}/{total_games} games completed ({completion_percentage}%). Safe to analyze stats for completed teams only."
        }
        
    except Exception as e:
        return {
            "week": week,
            "error": f"Error getting schedule for week {week}: {str(e)}",
            "games": [],
            "completion_summary": {}
        }