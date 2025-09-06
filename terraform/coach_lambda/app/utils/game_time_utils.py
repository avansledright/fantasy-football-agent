import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set
import boto3
from boto3.dynamodb.conditions import Attr

# Import your NFL schedule data
try:
    from app.utils.nfl_schedule import nfl_games_and_times
except ImportError:
    # Fallback if import fails
    nfl_games_and_times = {}

# Team name mappings to standardize team abbreviations
TEAM_NAME_TO_ABBREV = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS"
}

def get_team_abbreviation(team_name: str) -> str:
    """Convert full team name to standard abbreviation."""
    return TEAM_NAME_TO_ABBREV.get(team_name, team_name.upper()[:3])

def is_game_completed(week: int, team_abbrev: str, current_time: Optional[datetime] = None) -> bool:
    """
    Determine if a team's game for a given week has been completed using actual NFL schedule.
    
    Args:
        week: NFL week number (1-18)
        team_abbrev: Team abbreviation (e.g., "DAL", "PHI")
        current_time: Current time for comparison (defaults to now)
    
    Returns:
        True if the game has been completed, False otherwise
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    
    week_key = f"week_{week}"
    if week_key not in nfl_games_and_times:
        return False
    
    # Find the game for this team in this week
    for game in nfl_games_and_times[week_key]:
        away_abbrev = get_team_abbreviation(game["away_team"])
        home_abbrev = get_team_abbreviation(game["home_team"])
        
        if team_abbrev.upper() in [away_abbrev.upper(), home_abbrev.upper()]:
            # Parse game date and time
            game_date_str = game["date"]
            game_time_str = game["time"]
            
            try:
                # Combine date and time
                game_datetime_str = f"{game_date_str} {game_time_str}"
                game_datetime = datetime.strptime(game_datetime_str, "%Y-%m-%d %H:%M")
                game_datetime = game_datetime.replace(tzinfo=timezone.utc)
                
                # Add buffer time for game completion (games last ~3 hours)
                game_end_time = game_datetime + timedelta(hours=3, minutes=30)
                
                return current_time > game_end_time
                
            except ValueError as e:
                print(f"Error parsing game time for {team_abbrev} week {week}: {e}")
                return False
    
    # If team not found in schedule, assume game hasn't happened
    return False


def get_completed_teams_for_week(week: int, current_time: Optional[datetime] = None) -> Set[str]:
    """
    Get set of team abbreviations that have completed games for a given week.
    
    Args:
        week: NFL week number
        current_time: Current time for comparison
        
    Returns:
        Set of team abbreviations that have completed their games
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    
    completed_teams = set()
    week_key = f"week_{week}"
    
    if week_key not in nfl_games_and_times:
        return completed_teams
    
    for game in nfl_games_and_times[week_key]:
        away_abbrev = get_team_abbreviation(game["away_team"])
        home_abbrev = get_team_abbreviation(game["home_team"])
        
        try:
            game_datetime_str = f"{game['date']} {game['time']}"
            game_datetime = datetime.strptime(game_datetime_str, "%Y-%m-%d %H:%M")
            game_datetime = game_datetime.replace(tzinfo=timezone.utc)
            
            # Game is complete if current time is 3+ hours after kickoff
            game_end_time = game_datetime + timedelta(hours=3, minutes=30)
            
            if current_time > game_end_time:
                completed_teams.add(away_abbrev.upper())
                completed_teams.add(home_abbrev.upper())
                
        except ValueError as e:
            print(f"Error parsing game time: {e}")
            continue
    
    return completed_teams

def filter_completed_games_only(stats_items: List[Dict], current_time: Optional[datetime] = None) -> List[Dict]:
    """
    Filter stats to only include games that have been completed using NFL schedule.
    
    Args:
        stats_items: List of stat items from DynamoDB
        current_time: Current time for comparison (defaults to now)
    
    Returns:
        Filtered list containing only completed games
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    
    filtered_items = []
    
    for item in stats_items:
        week = item.get("week", 0)
        team = item.get("team", "").upper()
        fantasy_points = float(item.get("fantasy_points", 0))
        
        # Method 1: If the item has a game_status field, use it
        if "game_status" in item:
            if item["game_status"] in ["completed", "final"]:
                filtered_items.append(item)
            continue
        
        # Method 2: Use actual NFL schedule to check completion
        if is_game_completed(week, team, current_time):
            filtered_items.append(item)
            continue
            
        # Method 3: If points > 0 and game is scheduled, likely completed
        # (handles edge case where game finished but not in our completion logic)
        if fantasy_points > 0:
            filtered_items.append(item)
            continue
    
    return filtered_items

def get_safe_player_average(player_stats: List[Dict], weeks_back: int = 4) -> float:
    """
    Calculate a player's average that excludes unplayed games using NFL schedule.
    
    Args:
        player_stats: List of player stat entries
        weeks_back: Number of recent weeks to consider
    
    Returns:
        Average fantasy points from completed games only
    """
    if not player_stats:
        return 0.0
    
    # Filter to completed games only using NFL schedule
    completed_games = filter_completed_games_only(player_stats)
    
    if not completed_games:
        return 0.0
    
    # Sort by week and take most recent
    completed_games.sort(key=lambda x: x.get("week", 0), reverse=True)
    recent_games = completed_games[:weeks_back]
    
    if not recent_games:
        return 0.0
    
    total_points = sum(float(game.get("fantasy_points", 0)) for game in recent_games)
    return round(total_points / len(recent_games), 2)

def add_game_completion_context(stats_result: Dict, current_week: Optional[int] = None) -> Dict:
    """
    Add context about game completion to stats results using NFL schedule.
    
    Args:
        stats_result: Result dict from stats tools
        current_week: Current NFL week (passed from Lambda parameter)
    
    Returns:
        Enhanced result with game completion information
    """
    query_week = stats_result.get('week', 0)
    
    # If current_week not provided, try to determine it from schedule (fallback)
    if current_week is None:
        current_week = get_current_nfl_week_from_schedule()
    
    # Get completion info for the queried week
    completed_teams = get_completed_teams_for_week(query_week)
    
    # Add current week context
    stats_result["current_nfl_week"] = current_week
    stats_result["completed_teams_count"] = len(completed_teams)
    stats_result["completed_teams"] = list(completed_teams)
    
    if query_week < current_week:
        completion_status = "all games completed"
    elif query_week == current_week:
        total_teams = 32
        completion_status = f"{len(completed_teams)}/{total_teams} teams completed games"
    else:
        completion_status = "games not yet played"
    
    stats_result["analysis_note"] = (
        f"Week {query_week} analysis based on NFL schedule. Current week: {current_week}. "
        f"Status: {completion_status}. Only including completed games in statistics."
    )
    
    return stats_result

def get_week_game_schedule(week: int) -> List[Dict]:
    """
    Get the game schedule for a specific week.
    
    Args:
        week: NFL week number
        
    Returns:
        List of game dictionaries with timing and completion info
    """
    current_time = datetime.now(timezone.utc)
    week_key = f"week_{week}"
    
    if week_key not in nfl_games_and_times:
        return []
    
    schedule = []
    for game in nfl_games_and_times[week_key]:
        away_abbrev = get_team_abbreviation(game["away_team"])
        home_abbrev = get_team_abbreviation(game["home_team"])
        
        try:
            game_datetime_str = f"{game['date']} {game['time']}"
            game_datetime = datetime.strptime(game_datetime_str, "%Y-%m-%d %H:%M")
            game_datetime = game_datetime.replace(tzinfo=timezone.utc)
            game_end_time = game_datetime + timedelta(hours=3, minutes=30)
            
            is_completed = current_time > game_end_time
            is_in_progress = game_datetime <= current_time <= game_end_time
            
            schedule.append({
                "away_team": away_abbrev,
                "home_team": home_abbrev,
                "away_team_full": game["away_team"],
                "home_team_full": game["home_team"],
                "date": game["date"],
                "time": game["time"],
                "network": game.get("network", ""),
                "location": game.get("location", ""),
                "kickoff_time": game_datetime.isoformat(),
                "estimated_end_time": game_end_time.isoformat(),
                "is_completed": is_completed,
                "is_in_progress": is_in_progress,
                "status": "completed" if is_completed else ("in_progress" if is_in_progress else "upcoming")
            })
            
        except ValueError as e:
            print(f"Error parsing game time: {e}")
            continue
    
    return schedule