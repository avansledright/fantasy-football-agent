from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class Player:
    """Represents a fantasy football player"""
    player_id: str
    name: str
    position: str
    team: str
    opponent: str = ""
    is_playing: bool = True
    bye_week: bool = False
    injury_status: str = "Healthy"
    
    # Projection data
    projected_points: float = 0.0
    
    # Historical data
    season_average: float = 0.0
    last_3_weeks_avg: float = 0.0
    consistency_score: float = 0.0
    trend: str = "Unknown"
    matchup_rating: str = "Average"
    past_performance: Dict = None
    
    # Opponent history
    vs_opponent_avg: float = 0.0
    vs_opponent_games: int = 0

@dataclass
class LineupRecommendation:
    """Represents the recommended starting lineup"""
    qb: Player
    rb1: Player
    rb2: Player
    wr1: Player
    wr2: Player
    te: Player
    flex: Player
    op: Player
    defense: Player
    kicker: Player
    rationale: str