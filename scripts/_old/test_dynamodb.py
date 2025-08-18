#!/usr/bin/env python3
"""
Test script to debug DynamoDB connection and data structure
Run this to diagnose issues with the fantasy football data table
"""

import boto3
import json
from decimal import Decimal

def decimal_default(obj):
    """JSON serializer for Decimal objects"""
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

def test_dynamodb_connection():
    """Test basic DynamoDB connection and table structure."""
    
    print("🔍 Testing DynamoDB Connection...")
    
    try:
        # Initialize DynamoDB resource
        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
        table = dynamodb.Table("2025-2026-fantasy-football-player-data")
        
        print("✅ DynamoDB resource initialized")
        
        # Test table existence
        print(f"📊 Table name: {table.name}")
        print(f"📊 Table status: {table.table_status}")
        
        # Get table info
        table_info = table.meta.client.describe_table(TableName=table.name)
        item_count = table_info['Table'].get('ItemCount', 'Unknown')
        print(f"📊 Estimated item count: {item_count}")
        
        # Test basic scan
        print("\n🔍 Testing basic scan (limit 5)...")
        response = table.scan(Limit=5)
        items = response.get('Items', [])
        
        print(f"✅ Scan successful. Retrieved {len(items)} items")
        
        if items:
            print("\n📋 Sample item structure:")
            sample_item = items[0]
            print(json.dumps(sample_item, indent=2, default=decimal_default))
            
            print(f"\n🔑 Available fields in sample item:")
            for key in sorted(sample_item.keys()):
                value = sample_item[key]
                value_type = type(value).__name__
                print(f"   {key}: {value_type}")
        
        # Check for different seasons and season types
        print("\n🔍 Checking available seasons and season types...")
        
        # Scan more items to get a better picture
        response = table.scan(Limit=50)
        all_items = response.get('Items', [])
        
        seasons = set()
        season_types = set()
        positions = set()
        
        for item in all_items:
            if 'season' in item:
                seasons.add(int(item['season']))
            if 'season_type' in item:
                season_types.add(str(item['season_type']))
            if 'position' in item:
                positions.add(str(item['position']))
        
        print(f"📅 Seasons found: {sorted(seasons)}")
        print(f"🏈 Season types found: {sorted(season_types)}")
        print(f"🏃 Positions found: {sorted(positions)}")
        
        # Test filtered query for 2024 REG season
        print(f"\n🔍 Testing filtered scan for 2024 REG season...")
        response = table.scan(
            FilterExpression="season = :season AND season_type = :season_type",
            ExpressionAttributeValues={
                ":season": 2024,
                ":season_type": "REG"
            },
            Limit=10
        )
        
        filtered_items = response.get('Items', [])
        print(f"📊 Found {len(filtered_items)} items for 2024 REG season")
        
        if filtered_items:
            # Show sample of filtered data
            sample_filtered = filtered_items[0]
            print(f"📋 Sample 2024 REG player: {sample_filtered.get('player_display_name', 'Unknown')}")
            print(f"   Position: {sample_filtered.get('position', 'Unknown')}")
            print(f"   PPR Points: {sample_filtered.get('fantasy_points_ppr', 0)}")
            print(f"   Team: {sample_filtered.get('team', 'Unknown')}")
        
        # Test aggregation of a single player
        if all_items:
            print(f"\n🔍 Testing player aggregation...")
            test_player_id = all_items[0].get('player_id')
            if test_player_id:
                player_response = table.scan(
                    FilterExpression="player_id = :player_id",
                    ExpressionAttributeValues={
                        ":player_id": test_player_id
                    }
                )
                player_games = player_response.get('Items', [])
                print(f"📊 Player {test_player_id} has {len(player_games)} game records")
                
                if player_games:
                    total_ppr = sum(float(game.get('fantasy_points_ppr', 0)) for game in player_games)
                    print(f"   Total PPR points across all games: {total_ppr}")
        
        print(f"\n✅ All tests completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        return False

def test_player_aggregation():
    """Test the player aggregation logic specifically - FIXED VERSION."""
    print(f"\n🔍 Testing Player Aggregation Logic...")
    
    try:
        dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
        table = dynamodb.Table("2025-2026-fantasy-football-player-data")
        
        # Get ALL game records for proper aggregation
        print("📊 Getting ALL game records for aggregation...")
        
        players = []
        response = table.scan()
        players.extend(response.get("Items", []))
        
        # Handle pagination to get ALL data
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            players.extend(response.get("Items", []))
        
        print(f"📊 Working with {len(players)} total game records")
        
        # Aggregate by player_id - sum ALL games for each player
        player_stats = {}
        games_count = {}  # Track how many games each player has
        
        for game_record in players:
            player_id = game_record.get("player_id")
            if not player_id:
                continue
                
            if player_id not in player_stats:
                player_stats[player_id] = {
                    "player_id": player_id,
                    "player_display_name": game_record.get("player_display_name", "Unknown"),
                    "position": game_record.get("position", ""),
                    "team": game_record.get("team", ""),
                    "games_played": 0,
                    "fantasy_points_ppr": 0,
                }
                games_count[player_id] = []
            
            # Track this game
            week = game_record.get("week", "?")
            ppr_this_game = game_record.get("fantasy_points_ppr", 0)
            games_count[player_id].append(f"Week {week}: {ppr_this_game} pts")
            
            # Aggregate season totals
            stats = player_stats[player_id]
            stats["games_played"] += 1
            
            # Handle Decimal type from DynamoDB
            ppr_points = game_record.get("fantasy_points_ppr", 0)
            if isinstance(ppr_points, Decimal):
                ppr_points = float(ppr_points)
            stats["fantasy_points_ppr"] += float(ppr_points or 0)
        
        print(f"📊 Aggregated into {len(player_stats)} unique players")
        
        # Show distribution of games played
        games_distribution = {}
        for player in player_stats.values():
            games = player["games_played"]
            games_distribution[games] = games_distribution.get(games, 0) + 1
        
        print(f"\n📈 Games played distribution:")
        for games, count in sorted(games_distribution.items()):
            print(f"   {games} games: {count} players")
        
        # Show top players with proper context
        sorted_players = sorted(player_stats.values(), key=lambda x: x["fantasy_points_ppr"], reverse=True)
        
        print(f"\n🏆 Top 10 players by SEASON TOTAL PPR points:")
        for i, player in enumerate(sorted_players[:10]):
            ppg = player["fantasy_points_ppr"] / max(player["games_played"], 1)
            print(f"   {i+1}. {player['player_display_name']} ({player['position']}) - {player['fantasy_points_ppr']:.1f} total pts in {player['games_played']} games ({ppg:.1f} PPG)")
            
            # Show suspicious players (very few games but high total)
            if player["games_played"] <= 2 and i < 5:
                print(f"      🚨 SUSPICIOUS: Only {player['games_played']} games!")
                player_id = player["player_id"]
                for game_info in games_count.get(player_id, [])[:3]:
                    print(f"        {game_info}")
        
        # Show top players by PPG (minimum 8 games)
        qualified_players = [p for p in sorted_players if p["games_played"] >= 8]
        qualified_players.sort(key=lambda x: x["fantasy_points_ppr"] / max(x["games_played"], 1), reverse=True)
        
        print(f"\n🏆 Top 5 players by PPG (min 8 games):")
        for i, player in enumerate(qualified_players[:5]):
            ppg = player["fantasy_points_ppr"] / max(player["games_played"], 1)
            print(f"   {i+1}. {player['player_display_name']} ({player['position']}) - {ppg:.1f} PPG ({player['fantasy_points_ppr']:.1f} total pts in {player['games_played']} games)")
        
        return True
        
    except Exception as e:
        print(f"❌ Aggregation test failed: {e}")
        import traceback
        print(f"📋 Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🏈 Fantasy Football DynamoDB Diagnostic Tool\n")
    
    # Test basic connection
    connection_success = test_dynamodb_connection()
    
    if connection_success:
        # Test aggregation logic
        test_player_aggregation()
    else:
        print("\n❌ Basic connection failed - skipping aggregation test")
    
    print(f"\n🏁 Diagnostic complete!")