#!/usr/bin/env python3
"""
NFL Fantasy Football Historical Stats Scraper - CLEAN VERSION
Gets ONLY: player name, week, opponent, fantasy points
"""

import nfl_data_py as nfl
import json
import pandas as pd
import logging
import os
from datetime import datetime
from typing import Dict
import warnings

warnings.filterwarnings('ignore', category=FutureWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NFLFantasyDataCollector:
    def __init__(self):
        self.season_year = 2024
        self.position_groups = {
            'QB': ['QB'], 'RB': ['RB', 'FB'], 'WR': ['WR'], 
            'TE': ['TE'], 'K': ['K'], 'DST': ['DST']
        }
        os.makedirs('historical_data', exist_ok=True)
        
    def get_schedule_data(self) -> pd.DataFrame:
        logger.info("Getting schedule data...")
        schedule_df = nfl.import_schedules([self.season_year])
        
        schedule_expanded = []
        for i in range(len(schedule_df)):
            row = schedule_df.iloc[i]
            if row['season'] == 2024 and 1 <= row['week'] <= 18:
                schedule_expanded.extend([
                    {'season': 2024, 'week': row['week'], 'team': row['home_team'], 'opponent': row['away_team']},
                    {'season': 2024, 'week': row['week'], 'team': row['away_team'], 'opponent': row['home_team']}
                ])
        
        return pd.DataFrame(schedule_expanded)
    
    def get_weekly_stats(self) -> pd.DataFrame:
        logger.info("Getting weekly stats...")
        weekly_stats = nfl.import_weekly_data([self.season_year])
        return weekly_stats[(weekly_stats['week'] >= 1) & (weekly_stats['week'] <= 18)].copy()
    
    def calculate_fantasy_points(self, row: pd.Series) -> float:
        points = 0.0
        points += row.get('passing_yards', 0) * 0.04
        points += row.get('passing_tds', 0) * 4
        points += row.get('interceptions', 0) * -2
        points += row.get('rushing_yards', 0) * 0.1
        points += row.get('rushing_tds', 0) * 6
        points += row.get('receiving_yards', 0) * 0.1
        points += row.get('receiving_tds', 0) * 6
        points += row.get('fumbles_lost', 0) * -2
        return round(points, 1)
    
    def process_data(self):
        schedule = self.get_schedule_data()
        weekly_stats = self.get_weekly_stats()
        
        merged = weekly_stats.merge(
            schedule, 
            left_on=['season', 'week', 'recent_team'],
            right_on=['season', 'week', 'team'],
            how='left'
        )
        
        merged['fantasy_points'] = merged.apply(self.calculate_fantasy_points, axis=1)
        
        all_profiles = {}
        
        for pos_name, positions in self.position_groups.items():
            pos_data = merged[merged['position'].isin(positions)]
            
            position_profiles = {}
            for player_name, player_games in pos_data.groupby('player_display_name'):
                if len(player_games) >= 2:
                    games = []
                    for _, game in player_games.iterrows():
                        games.append({
                            'week': int(game['week']),
                            'opponent': str(game.get('opponent', 'Unknown')),
                            'fantasy_points': float(game['fantasy_points'])
                        })
                    position_profiles[player_name] = sorted(games, key=lambda x: x['week'])
            
            if position_profiles:
                all_profiles[pos_name.lower()] = position_profiles
                logger.info(f"Processed {len(position_profiles)} {pos_name} players")
        
        return all_profiles
    
    def save_files(self, profiles: Dict):
        for position, players in profiles.items():
            data = {
                'position': position.upper(),
                'season': 2024,
                'players': players
            }
            
            filename = f'historical_data/{position}.json'
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(players)} {position.upper()} players")


def main():
    collector = NFLFantasyDataCollector()
    profiles = collector.process_data()
    collector.save_files(profiles)
    logger.info("Done!")


if __name__ == "__main__":
    main()