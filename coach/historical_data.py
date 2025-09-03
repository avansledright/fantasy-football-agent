import json
import logging
from pathlib import Path
from typing import Dict, List
from utils import names_match

logger = logging.getLogger(__name__)

class HistoricalDataManager:
    """Manages historical data from local JSON files"""
    
    def __init__(self, data_dir: str = "../scripts/historical_data"):
        self.data_dir = Path(data_dir)
        self.historical_data = {}
        
    def load_historical_data(self) -> Dict[str, Dict]:
        """Load all historical data from JSON files"""
        positions = ['qb', 'rb', 'wr', 'te']  # Defense and kickers not present
        
        for position in positions:
            file_path = self.data_dir / f"{position}.json"
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        self.historical_data[position.upper()] = data
                    logger.info(f"Loaded historical data for {position.upper()}")
                except Exception as e:
                    logger.error(f"Error loading {position}.json: {str(e)}")
            else:
                logger.warning(f"Historical data file not found: {file_path}")
        
        return self.historical_data
    
    def get_player_stats(self, player_name: str, position: str, current_week: int, opponent: str = None) -> Dict:
        """Get comprehensive player statistics including opponent-specific data"""
        position_data = self.historical_data.get(position, {})
        
        if 'players' not in position_data:
            return {}
        
        # Find player with fuzzy matching
        player_data = None
        for name, stats in position_data['players'].items():
            if names_match(player_name, name):
                player_data = stats
                break
        
        if not player_data:
            return {}
        
        # Filter games before current week
        all_games = [game for game in player_data if game['week'] < current_week]
        
        if not all_games:
            return {}
        
        # Recent games (last 3 weeks before current week)
        recent_games = [game for game in all_games if game['week'] >= current_week - 3]
        
        # Opponent-specific games (if opponent provided)
        opponent_games = []
        if opponent:
            opponent_games = [game for game in all_games if game.get('opponent', '').upper() == opponent.upper()]
        
        stats = {
            'total_games': len(all_games),
            'season_points': [game['fantasy_points'] for game in all_games],
            'recent_points': [game['fantasy_points'] for game in recent_games],
            'opponent_points': [game['fantasy_points'] for game in opponent_games],
            'opponents': [game.get('opponent', '') for game in all_games],
            'recent_opponents': [game.get('opponent', '') for game in recent_games]
        }
        
        # Calculate season averages
        if stats['season_points']:
            stats['season_average'] = sum(stats['season_points']) / len(stats['season_points'])
            stats['consistency_score'] = self._calculate_consistency_score(stats['season_points'])
        else:
            stats['season_average'] = 0.0
            stats['consistency_score'] = 0.0
        
        # Calculate recent form
        if stats['recent_points']:
            stats['recent_average'] = sum(stats['recent_points']) / len(stats['recent_points'])
        else:
            stats['recent_average'] = stats['season_average']
        
        # Calculate opponent-specific performance
        if stats['opponent_points']:
            stats['vs_opponent_avg'] = sum(stats['opponent_points']) / len(stats['opponent_points'])
            stats['vs_opponent_games'] = len(stats['opponent_points'])
        else:
            stats['vs_opponent_avg'] = 0.0
            stats['vs_opponent_games'] = 0
        
        # Trend analysis
        stats['trend'] = self._calculate_trend(stats['season_points'])
        
        return stats
    
    def _calculate_consistency_score(self, points: List[float]) -> float:
        """Calculate consistency score (lower standard deviation = higher consistency)"""
        if len(points) < 2:
            return 0.0
        
        mean_points = sum(points) / len(points)
        variance = sum((p - mean_points) ** 2 for p in points) / len(points)
        std_dev = variance ** 0.5
        
        # Convert to 0-100 scale where 100 is most consistent
        if mean_points > 0:
            coefficient_of_variation = std_dev / mean_points
            consistency = max(0, 100 - (coefficient_of_variation * 100))
        else:
            consistency = 0
        
        return consistency
    
    def _calculate_trend(self, points: List[float]) -> str:
        """Calculate recent performance trend"""
        if len(points) < 4:
            return "Insufficient data"
        
        # Compare last 4 games to previous 4 games
        recent = points[-4:]
        previous = points[-8:-4] if len(points) >= 8 else points[:-4]
        
        recent_avg = sum(recent) / len(recent)
        previous_avg = sum(previous) / len(previous)
        
        if recent_avg > previous_avg * 1.15:
            return "Trending up"
        elif recent_avg < previous_avg * 0.85:
            return "Trending down"
        else:
            return "Stable"