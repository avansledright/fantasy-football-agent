#!/usr/bin/env python3
"""
Fantasy Football Draft CLI Tool with Interactive Snake Draft
Usage: python main.py [command] [options]
"""

import json
import os
import sys
import argparse
import requests
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Configuration
API_ENDPOINT = "https://pabzmwn3l5.execute-api.us-west-2.amazonaws.com/demo/agent"
DRAFT_SESSION_FILE = "draft_session.json"

@dataclass
class Player:
    name: str
    position: str
    team: str = ""
    player_id: str = ""
    fantasy_points: float = 0.0
    age: int = 0
    years_exp: int = 0
    points_per_game: float = 0.0
    rank: int = 999

@dataclass
class DraftPick:
    pick_number: int
    team_number: int
    player: Player
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

@dataclass
class DraftBoard:
    total_teams: int
    current_pick: int
    your_team_number: int
    picks: List[DraftPick] = None
    rounds: int = 17  # Updated to 17 rounds
    
    def __post_init__(self):
        if self.picks is None:
            self.picks = []
    
    def get_picking_team(self, pick_number: int = None) -> int:
        """Calculate which team is picking based on snake draft order."""
        pick_num = pick_number or self.current_pick
        round_num = ((pick_num - 1) // self.total_teams) + 1
        
        if round_num % 2 == 1:  # Odd rounds (1, 3, 5...) - normal order
            return ((pick_num - 1) % self.total_teams) + 1
        else:  # Even rounds (2, 4, 6...) - reverse order (snake)
            return self.total_teams - ((pick_num - 1) % self.total_teams)
    
    def get_round_and_position(self, pick_number: int = None) -> tuple:
        """Get round number and position within round."""
        pick_num = pick_number or self.current_pick
        round_num = ((pick_num - 1) // self.total_teams) + 1
        position_in_round = ((pick_num - 1) % self.total_teams) + 1
        return round_num, position_in_round
    
    def is_your_turn(self) -> bool:
        """Check if it's your team's turn to pick."""
        return self.get_picking_team() == self.your_team_number
    
    def get_your_picks(self) -> List[DraftPick]:
        """Get all picks made by your team."""
        return [pick for pick in self.picks if pick.team_number == self.your_team_number]
    
    def get_all_drafted_player_ids(self) -> List[str]:
        """Get all player IDs that have been drafted."""
        return [pick.player.player_id for pick in self.picks if pick.player.player_id]
    
    def is_draft_complete(self) -> bool:
        """Check if draft is complete."""
        return self.current_pick > (self.total_teams * self.rounds)

@dataclass
class Roster:
    qb: List[Player] = None
    rb: List[Player] = None  
    wr: List[Player] = None
    te: List[Player] = None
    def_: List[Player] = None
    k: List[Player] = None
    flex: List[Player] = None
    bench: List[Player] = None  # Added bench for extra picks
    
    def __post_init__(self):
        if self.qb is None: self.qb = []
        if self.rb is None: self.rb = []
        if self.wr is None: self.wr = []
        if self.te is None: self.te = []
        if self.def_ is None: self.def_ = []
        if self.k is None: self.k = []
        if self.flex is None: self.flex = []
        if self.bench is None: self.bench = []

@dataclass 
class DraftSession:
    roster: Roster
    draft_board: DraftBoard
    league_size: int = 12
    scoring_format: str = "ppr"
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

class FantasyDraftCLI:
    def __init__(self):
        self.session: Optional[DraftSession] = None
        self.player_cache: List[Dict] = []
        # Updated roster limits for full 17-round draft
        self.starter_limits = {
            "QB": 1, "RB": 2, "WR": 2, "TE": 1, 
            "DEF": 1, "K": 1, "FLEX": 1
        }
        self.roster_limits = {
            "QB": 3, "RB": 6, "WR": 6, "TE": 3, 
            "DEF": 2, "K": 2, "FLEX": 1, "BENCH": 6  # Total = 17 + starting lineup
        }
    def load_player_cache(self):
        """Load all players into memory at start of draft."""
        if self.player_cache:  # Already loaded
            return True
            
        print("🔄 Loading player database...")
        
        try:
            import boto3
            from boto3.dynamodb.conditions import Attr
            
            dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
            table = dynamodb.Table("2025-2026-fantasy-football-player-data")
            
            players = []
            
            # Scan entire table with pagination
            response = table.scan(
                FilterExpression=Attr('fantasy_points_ppr').gt(5)  # Only fantasy-relevant players
            )
            players.extend(response.get("Items", []))
            
            # Handle pagination
            while "LastEvaluatedKey" in response:
                response = table.scan(
                    FilterExpression=Attr('fantasy_points_ppr').gt(5),
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                players.extend(response.get("Items", []))
            
            self.player_cache = players
            print(f"✅ Loaded {len(self.player_cache)} players into memory")
            return True
            
        except Exception as e:
            print(f"❌ Error loading player cache: {e}")
            return False
    def save_session(self):
        """Save current draft session to file."""
        if not self.session:
            return
            
        session_data = asdict(self.session)
        with open(DRAFT_SESSION_FILE, 'w') as f:
            json.dump(session_data, f, indent=2)
        print(f"✅ Session saved")
    
    def load_session(self) -> bool:
        """Load draft session from file."""
        if not os.path.exists(DRAFT_SESSION_FILE):
            return False
            
        try:
            with open(DRAFT_SESSION_FILE, 'r') as f:
                session_data = json.load(f)
            
            # Reconstruct objects
            roster_data = session_data['roster']
            roster = Roster(**{k: [Player(**p) for p in v] for k, v in roster_data.items()})
            
            board_data = session_data['draft_board']
            picks = [DraftPick(
                pick_number=p['pick_number'],
                team_number=p['team_number'],
                player=Player(**p['player']),
                timestamp=p.get('timestamp', '')
            ) for p in board_data.get('picks', [])]
            
            draft_board = DraftBoard(
                total_teams=board_data['total_teams'],
                current_pick=board_data['current_pick'],
                your_team_number=board_data['your_team_number'],
                picks=picks,
                rounds=board_data.get('rounds', 17)
            )
            
            self.session = DraftSession(
                roster=roster,
                draft_board=draft_board,
                league_size=session_data.get('league_size', 12),
                scoring_format=session_data.get('scoring_format', 'ppr'),
                created_at=session_data.get('created_at', '')
            )
            return True
        except Exception as e:
            print(f"❌ Error loading session: {e}")
            return False
    
    def calculate_team_needs(self) -> Dict[str, int]:
        """Calculate remaining roster needs for starting lineup."""
        if not self.session:
            return self.starter_limits.copy()
            
        needs = {}
        roster = self.session.roster
        
        needs["QB"] = max(0, self.starter_limits["QB"] - len(roster.qb))
        needs["RB"] = max(0, self.starter_limits["RB"] - len(roster.rb))
        needs["WR"] = max(0, self.starter_limits["WR"] - len(roster.wr))
        needs["TE"] = max(0, self.starter_limits["TE"] - len(roster.te))
        needs["DEF"] = max(0, self.starter_limits["DEF"] - len(roster.def_))
        needs["K"] = max(0, self.starter_limits["K"] - len(roster.k))
        needs["FLEX"] = max(0, self.starter_limits["FLEX"] - len(roster.flex))
        
        return needs
    
    def call_agent_api(self, team_needs: Dict[str, int], all_drafted_players: List[str]) -> Dict:
        """Call the AWS API Gateway endpoint with ALL drafted players."""
        payload = {
            "team_needs": team_needs,
            "already_drafted": all_drafted_players,
            "scoring_format": self.session.scoring_format if self.session else "ppr",
            "league_size": self.session.league_size if self.session else 12
        }
        
        try:
            response = requests.post(API_ENDPOINT, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            return result
        except requests.exceptions.RequestException as e:
            return {"error": f"API request failed: {e}"}
    
    def start_new_draft(self, league_size: int = 12, your_pick: int = 1, scoring_format: str = "ppr"):
        """Initialize a new draft session with your draft position."""
        if your_pick < 1 or your_pick > league_size:
            print(f"❌ Invalid draft position. Must be between 1 and {league_size}")
            return
        
        # Load player cache first
        if not self.load_player_cache():
            print("❌ Failed to load player database")
            return
            
        self.session = DraftSession(
            roster=Roster(),
            draft_board=DraftBoard(
                total_teams=league_size,
                current_pick=1,
                your_team_number=your_pick,
                picks=[],
                rounds=17
            ),
            league_size=league_size,
            scoring_format=scoring_format
        )
        self.save_session()
        print(f"🏈 New {league_size}-team {scoring_format.upper()} snake draft started!")
        print(f"📍 Your draft position: #{your_pick}")
        print(f"📋 17-round draft format")
        
        # Show your picks in each round
        print(f"\n📅 Your picks in snake draft:")
        for round_num in range(1, 6):
            your_pick_in_round = self._get_your_pick_in_round(round_num)
            print(f"   Round {round_num}: Pick #{your_pick_in_round}")
        print("   ...")
    
    def _get_your_pick_in_round(self, round_num: int) -> int:
        """Calculate your pick number in a specific round."""
        if round_num % 2 == 1:  # Odd rounds
            return ((round_num - 1) * self.session.draft_board.total_teams) + self.session.draft_board.your_team_number
        else:  # Even rounds (snake)
            return ((round_num - 1) * self.session.draft_board.total_teams) + (self.session.draft_board.total_teams - self.session.draft_board.your_team_number + 1)
    
    def add_to_roster(self, player: Player, position: str):
        """Add a player to your roster in the appropriate position."""
        roster = self.session.roster
        position = position.upper()
        
        # Try to add to starting lineup first, then bench
        added = False
        
        if position == "QB" and len(roster.qb) < self.roster_limits["QB"]:
            roster.qb.append(player)
            added = True
        elif position == "RB" and len(roster.rb) < self.roster_limits["RB"]:
            roster.rb.append(player)
            added = True
        elif position == "WR" and len(roster.wr) < self.roster_limits["WR"]:
            roster.wr.append(player)
            added = True
        elif position == "TE" and len(roster.te) < self.roster_limits["TE"]:
            roster.te.append(player)
            added = True
        elif position == "DEF" and len(roster.def_) < self.roster_limits["DEF"]:
            roster.def_.append(player)
            added = True
        elif position == "K" and len(roster.k) < self.roster_limits["K"]:
            roster.k.append(player)
            added = True
        elif position in ["RB", "WR", "TE"] and len(roster.flex) < self.roster_limits["FLEX"]:
            roster.flex.append(player)
            added = True
        elif len(roster.bench) < self.roster_limits["BENCH"]:
            roster.bench.append(player)
            added = True
            print(f"📝 Added {player.name} to BENCH")
        
        if not added:
            print(f"⚠️  Roster full - could not add {player.name}")
    
    def add_draft_pick(self, player_name: str, position: str = "", player_id: str = "", team_number: int = None):
        """Add a draft pick for any team."""
        if not self.session:
            print("❌ No active draft session")
            return False
        
        board = self.session.draft_board
        
        if board.is_draft_complete():
            print("🏁 Draft is complete!")
            return False
        
        current_pick = board.current_pick
        round_num, pick_in_round = board.get_round_and_position(current_pick)
        
        # Determine which team is picking
        if team_number is None:
            picking_team = board.get_picking_team(current_pick)
        else:
            picking_team = team_number
        
        player = Player(
            name=player_name,
            position=position.upper() if position else "",
            player_id=player_id,
            team=""
        )
        
        draft_pick = DraftPick(
            pick_number=current_pick,
            team_number=picking_team,
            player=player
        )
        
        board.picks.append(draft_pick)
        board.current_pick += 1
        
        # If it's your team, add to roster
        if picking_team == board.your_team_number:
            self.add_to_roster(player, position)
            print(f"✅ YOUR PICK #{current_pick} (Round {round_num}.{pick_in_round}): {player_name} ({position})")
        else:
            print(f"📝 Pick #{current_pick} (Round {round_num}.{pick_in_round}, Team {picking_team}): {player_name} ({position})")
        
        self.save_session()
        return True
    
    def draft_defense(self, team_name: str = "", team_number: int = None):
        """Draft a defense without API lookup."""
        if not self.session:
            print("❌ No active draft session")
            return False
        
        board = self.session.draft_board
        
        if not team_name:
            team_name = "Defense"
        
        # Determine which team is picking
        if team_number is None:
            picking_team = board.get_picking_team()
            if not board.is_your_turn():
                print("❌ Not your turn to pick!")
                return False
        else:
            picking_team = team_number
        
        current_pick = board.current_pick
        round_num, pick_in_round = board.get_round_and_position(current_pick)
        
        player = Player(
            name=f"{team_name} Defense",
            position="DEF",
            player_id=f"def_{team_name.lower()}_{current_pick}",
            team=team_name
        )
        
        draft_pick = DraftPick(
            pick_number=current_pick,
            team_number=picking_team,
            player=player
        )
        
        board.picks.append(draft_pick)
        board.current_pick += 1
        
        # If it's your team, add to roster
        if picking_team == board.your_team_number:
            self.add_to_roster(player, "DEF")
            print(f"✅ YOUR PICK #{current_pick} (Round {round_num}.{pick_in_round}): {team_name} Defense")
        else:
            print(f"📝 Pick #{current_pick} (Round {round_num}.{pick_in_round}, Team {picking_team}): {team_name} Defense")
        
        self.save_session()
        return True
    
    def get_next_recommendation(self):
        """Get AI recommendation for next pick (only when it's your turn)."""
        if not self.session:
            print("❌ No active draft session")
            return
        
        board = self.session.draft_board
        
        if board.is_draft_complete():
            print("🏁 Draft is complete!")
            return
        
        # Check if it's your turn
        if not board.is_your_turn():
            next_team = board.get_picking_team()
            print(f"⏸️  Not your turn! Team {next_team} is picking")
            return
        
        team_needs = self.calculate_team_needs()
        all_drafted_players = board.get_all_drafted_player_ids()
        
        current_pick = board.current_pick
        round_num, pick_in_round = board.get_round_and_position(current_pick)
        
        print(f"🤖 Getting recommendation for YOUR pick #{current_pick} (Round {round_num}.{pick_in_round})...")
        print(f"🔍 Excluding {len(all_drafted_players)} already drafted players...")
        
        result = self.call_agent_api(team_needs, all_drafted_players)
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return
            
        # Parse and display recommendation with better formatting
        try:
            # Extract the recommendation text
            recommendation_text = ""
            
            if 'body' in result:
                if isinstance(result['body'], str):
                    body = json.loads(result['body'])
                else:
                    body = result['body']
                recommendation_content = body.get('recommendation', '')
            else:
                recommendation_content = result.get('recommendation', '')
            
            # Handle different response formats
            if isinstance(recommendation_content, str):
                recommendation_text = recommendation_content
            elif isinstance(recommendation_content, dict):
                # If it's structured data, format it nicely
                primary = recommendation_content.get('primary_recommendation', {})
                if primary:
                    name = primary.get('name', 'Unknown')
                    position = primary.get('position', '?')
                    team = primary.get('team', '')
                    fantasy_points = primary.get('fantasy_points', 0)
                    ppg = primary.get('points_per_game', 0)
                    reasoning = primary.get('reasoning', 'No reasoning provided')
                    
                    recommendation_text = f"🏈 RECOMMENDED: {name} ({position}) - {team}\n"
                    recommendation_text += f"📊 {fantasy_points:.1f} PPR points ({ppg:.1f} PPG)\n"
                    recommendation_text += f"💭 {reasoning}\n"
                    
                    alternatives = recommendation_content.get('alternatives', [])
                    if alternatives:
                        recommendation_text += f"\n📋 ALTERNATIVES:\n"
                        for i, alt in enumerate(alternatives[:3], 1):
                            recommendation_text += f"   {i}. {alt.get('name')} ({alt.get('position')}, {alt.get('team')}) - {alt.get('fantasy_points', 0):.1f} pts\n"
                else:
                    recommendation_text = str(recommendation_content)
            
            # Clean up and format the text
            if recommendation_text:
                # Remove excessive newlines and clean up formatting
                lines = recommendation_text.split('\n')
                cleaned_lines = []
                
                for line in lines:
                    line = line.strip()
                    if line:
                        # Remove markdown formatting that doesn't display well
                        line = line.replace('**', '')
                        line = line.replace('*', '')
                        cleaned_lines.append(line)
                
                print(f"\n" + "="*60)
                print(f"🤖 AI RECOMMENDATION:")
                print("="*60)
                
                for line in cleaned_lines:
                    if line.startswith(('1.', '2.', '3.', '4.', '5.')):
                        print(f"   {line}")
                    elif line.startswith('-'):
                        print(f"   {line}")
                    else:
                        print(line)
                
                print("="*60)
            else:
                print(f"❌ No recommendation received")
            
        except Exception as e:
            print(f"❌ Error parsing recommendation: {e}")
            print(f"Debug - Raw result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
    def lookup_player_id(self, player_name: str, position: str = "") -> str:
        """Look up player ID from DynamoDB with better matching."""
        try:
            import boto3
            from boto3.dynamodb.conditions import Attr, Key
            
            dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
            table = dynamodb.Table("2025-2026-fantasy-football-player-data")
            
            # Try multiple search strategies
            search_variations = [
                player_name,  # Exact name
                player_name.title(),  # Title case
                player_name.upper(),  # Upper case
                player_name.lower(),  # Lower case
            ]
            
            # Also try splitting names and searching parts
            name_parts = player_name.split()
            if len(name_parts) >= 2:
                # Try "First Last" combinations
                search_variations.extend([
                    f"{name_parts[0]} {name_parts[-1]}",  # First and last only
                    name_parts[-1],  # Last name only
                    name_parts[0],   # First name only
                ])
            
            for search_term in search_variations:
                try:
                    # Search by contains (case insensitive approach)
                    response = table.scan(
                        FilterExpression=Attr('player_display_name').contains(search_term)
                    )
                    
                    items = response.get('Items', [])
                    
                    # If position provided, filter by position
                    if position and items:
                        items = [item for item in items if item.get('position', '').upper() == position.upper()]
                    
                    if items:
                        # Found match - prefer exact matches
                        for item in items:
                            item_name = item.get('player_display_name', '').lower()
                            if search_term.lower() in item_name:
                                player_id = item.get('player_id', '')
                                print(f"🔍 Found: {item.get('player_display_name')} (ID: {player_id})")
                                return player_id
                except Exception as search_error:
                    print(f"🔍 Search error for '{search_term}': {search_error}")
                    continue
            
            # If no matches found, try a broader scan
            print(f"🔍 Broad search for: {player_name}")
            response = table.scan(Limit=50)  # Get first 50 players
            items = response.get('Items', [])
            
            # Manual fuzzy matching
            player_lower = player_name.lower()
            for item in items:
                item_name = item.get('player_display_name', '').lower()
                if any(part in item_name for part in player_lower.split()):
                    if not position or item.get('position', '').upper() == position.upper():
                        player_id = item.get('player_id', '')
                        print(f"🔍 Fuzzy match: {item.get('player_display_name')} (ID: {player_id})")
                        return player_id
            
            print(f"❌ No match found for: {player_name} ({position})")
            return ""
            
        except Exception as e:
            print(f"❌ Lookup error: {e}")
            return ""
    def lookup_player_full(self, player_name: str) -> dict:
        """Look up complete player info from memory cache with fuzzy matching."""
        if not self.player_cache:
            if not self.load_player_cache():
                return None
        
        # Clean the input name
        clean_name = player_name.strip().title()
        
        # Try different search strategies
        search_strategies = [
            clean_name,                    # "Josh Allen"
            clean_name.upper(),           # "JOSH ALLEN"  
            clean_name.lower(),           # "josh allen"
        ]
        
        # Add partial name searches
        name_parts = clean_name.split()
        if len(name_parts) >= 2:
            search_strategies.append(name_parts[-1])  # "Allen"
            search_strategies.append(f"{name_parts[0]} {name_parts[-1]}")  # "Josh Allen"
            if len(name_parts) >= 3:
                # Handle names like "D.K. Metcalf" or "A.J. Brown"
                search_strategies.append(f"{name_parts[0]} {name_parts[-1]}")
        
        all_matches = []
        
        for search_term in search_strategies:
            search_lower = search_term.lower()
            
            for player in self.player_cache:
                player_name_full = player.get('player_display_name', '').lower()
                
                # Skip if already found this player
                if any(match['player_id'] == player.get('player_id') for match in all_matches):
                    continue
                
                score = 0
                
                # Exact match gets highest score
                if player_name_full == search_lower:
                    score = 100
                # Name starts with search term
                elif player_name_full.startswith(search_lower):
                    score = 90
                # Name contains search term
                elif search_lower in player_name_full:
                    score = 80
                # Any word in player name matches search term
                elif any(word == search_lower for word in player_name_full.split()):
                    score = 75
                # Search term contains part of name (for partial searches)
                elif any(part in search_lower for part in player_name_full.split() if len(part) > 2):
                    score = 60
                
                if score > 0:
                    all_matches.append({
                        'score': score,
                        'player_id': player.get('player_id', ''),
                        'name': player.get('player_display_name', ''),
                        'position': player.get('position', ''),
                        'team': player.get('team', ''),
                        'fantasy_points': float(player.get('fantasy_points_ppr', 0))
                    })
        
        if not all_matches:
            return None
        
        # Sort by score (best matches first), then by fantasy points
        all_matches.sort(key=lambda x: (x['score'], x['fantasy_points']), reverse=True)
        
        # Return the best match if it's good enough
        best_match = all_matches[0]
        if best_match['score'] >= 60:
            return best_match
        
        return None
    def interactive_draft(self):
        """Start interactive draft mode."""
        if not self.session:
            print("❌ No active draft session. Start with: python main.py start")
            return
        
        # Make sure player cache is loaded
        if not self.player_cache:
            if not self.load_player_cache():
                print("❌ Failed to load player database")
                return
        
        board = self.session.draft_board
        print(f"\n🎯 INTERACTIVE DRAFT MODE")
        print("Commands: 'next' (get recommendation), 'def [team]' (draft defense), 'quit' (exit)")
        print("Or just enter player name (position and ID will be auto-detected)")
        print("=" * 60)
        
        while not board.is_draft_complete():
            current_pick = board.current_pick
            round_num, pick_in_round = board.get_round_and_position(current_pick)
            picking_team = board.get_picking_team()
            
            if board.is_your_turn():
                prompt = f"🎯 YOUR TURN - Pick #{current_pick} (Round {round_num}.{pick_in_round}): "
            else:
                prompt = f"⏳ Team {picking_team} Pick #{current_pick} (Round {round_num}.{pick_in_round}): "
            
            try:
                user_input = input(prompt).strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == 'quit':
                    print("👋 Exiting interactive mode")
                    break
                elif user_input.lower() == 'next':
                    if board.is_your_turn():
                        self.get_next_recommendation()
                    else:
                        print("❌ Not your turn!")
                    continue
                elif user_input.lower().startswith('def'):
                    # Draft defense
                    parts = user_input.split()
                    team_name = parts[1] if len(parts) > 1 else "Unknown"
                    
                    if board.is_your_turn():
                        if self.draft_defense(team_name):
                            continue
                    else:
                        if self.draft_defense(team_name, picking_team):
                            continue
                    continue
                
                # Player name only - auto-detect everything
                player_name = user_input.strip()
                
                print(f"🔍 Looking up: {player_name}")
                player_data = self.lookup_player_full(player_name)
                
                if player_data:
                    position = player_data['position']
                    player_id = player_data['player_id']
                    full_name = player_data['name']
                    
                    print(f"✅ Found: {full_name} ({position}) - ID: {player_id}")
                    
                    # Add the pick
                    team_num = None if board.is_your_turn() else picking_team
                    if self.add_draft_pick(full_name, position, player_id, team_num):
                        continue
                    else:
                        print("❌ Failed to add pick")
                else:
                    print(f"❌ Could not find player: {player_name}")
                    response = input("Continue anyway? Enter position (QB/RB/WR/TE/K/DEF) or 'n' to skip: ").strip()
                    if response.lower() == 'n':
                        continue
                    elif response.upper() in ['QB', 'RB', 'WR', 'TE', 'K', 'DEF']:
                        # Manual entry with position
                        position = response.upper()
                        player_id = f"manual_{player_name.lower().replace(' ', '_')}_{position}_{board.current_pick}"
                        
                        team_num = None if board.is_your_turn() else picking_team
                        if self.add_draft_pick(player_name, position, player_id, team_num):
                            continue
                        else:
                            print("❌ Failed to add pick")
                    else:
                        print("❌ Invalid position")
                        continue
                    
            except KeyboardInterrupt:
                print("\n👋 Exiting interactive mode")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        if board.is_draft_complete():
            print("🏁 Draft completed!")
            self.show_final_roster()
    
    def show_draft_board(self):
        """Display the current draft board."""
        if not self.session:
            print("❌ No active draft session")
            return
        
        board = self.session.draft_board
        current_pick = board.current_pick
        round_num, pick_in_round = board.get_round_and_position(current_pick)
        
        print(f"\n📋 SNAKE DRAFT BOARD")
        print(f"Current: Pick #{current_pick} (Round {round_num}.{pick_in_round}) - Team {board.get_picking_team()}")
        print(f"Your team: #{board.your_team_number}")
        print(f"Your turn: {'🎯 YES' if board.is_your_turn() else '⏳ NO'}")
        
        if board.picks:
            # Show recent picks
            recent_picks = board.picks[-10:] if len(board.picks) > 10 else board.picks
            print(f"\n📝 Recent picks:")
            for pick in recent_picks:
                r, p = board.get_round_and_position(pick.pick_number)
                marker = "👤" if pick.team_number == board.your_team_number else f"T{pick.team_number}"
                print(f"   #{pick.pick_number:2d} (R{r}.{p}, {marker}): {pick.player.name} ({pick.player.position})")
        
        # Show upcoming picks for your team
        upcoming = []
        for pick_num in range(current_pick, min(current_pick + 50, board.total_teams * board.rounds + 1)):
            if board.get_picking_team(pick_num) == board.your_team_number:
                r, p = board.get_round_and_position(pick_num)
                upcoming.append(f"#{pick_num} (R{r}.{p})")
                if len(upcoming) >= 3:
                    break
        
        if upcoming:
            print(f"\n📅 Your next picks: {', '.join(upcoming)}")
    
    def show_status(self):
        """Display current roster and remaining needs."""
        if not self.session:
            print("❌ No active draft session")
            return
        
        board = self.session.draft_board
        print(f"\n📊 DRAFT STATUS")
        print(f"League: {self.session.league_size} teams | Format: {self.session.scoring_format.upper()}")
        print(f"Your position: #{board.your_team_number}")
        
        your_picks = board.get_your_picks()
        print(f"Your picks: {len(your_picks)}/17")
        
        # Show roster
        print(f"\n🏈 YOUR ROSTER:")
        roster = self.session.roster
        
        positions = [
            ("QB", roster.qb, self.roster_limits["QB"]), 
            ("RB", roster.rb, self.roster_limits["RB"]), 
            ("WR", roster.wr, self.roster_limits["WR"]),
            ("TE", roster.te, self.roster_limits["TE"]), 
            ("DEF", roster.def_, self.roster_limits["DEF"]), 
            ("K", roster.k, self.roster_limits["K"]), 
            ("FLEX", roster.flex, self.roster_limits["FLEX"]),
            ("BENCH", roster.bench, self.roster_limits["BENCH"])
        ]
        
        for pos, players, limit in positions:
            filled = len(players)
            if filled == 0:
                print(f"   {pos}: Empty (0/{limit})")
            else:
                player_names = [p.name for p in players]
                print(f"   {pos}: {', '.join(player_names)} ({filled}/{limit})")
    
    def show_final_roster(self):
        """Show final roster summary."""
        print(f"\n🏆 FINAL ROSTER SUMMARY")
        self.show_status()
        
        # Show draft summary
        your_picks = self.session.draft_board.get_your_picks()
        print(f"\n📋 YOUR DRAFT PICKS:")
        for pick in your_picks:
            r, p = self.session.draft_board.get_round_and_position(pick.pick_number)
            print(f"   R{r}.{p:2d} (#{pick.pick_number:2d}): {pick.player.name} ({pick.player.position})")

def main():
    cli = FantasyDraftCLI()
    
    # Try to load existing session
    if cli.load_session():
        print("📁 Loaded existing draft session")
    
    parser = argparse.ArgumentParser(description="Fantasy Football Snake Draft Assistant")
    parser.add_argument("command", choices=["start", "next", "pick", "add-pick", "def", "board", "status", "interactive", "reset"], nargs='?', default="interactive")
    parser.add_argument("--player", help="Player name")
    parser.add_argument("--position", help="Player position")
    parser.add_argument("--player-id", help="Player ID")
    parser.add_argument("--team", type=int, help="Team number (for add-pick)")
    parser.add_argument("--league-size", type=int, default=12, help="League size")
    parser.add_argument("--your-pick", type=int, default=1, help="Your draft position")
    parser.add_argument("--scoring", choices=["ppr", "half_ppr", "standard"], default="ppr", help="Scoring format")
    
    args = parser.parse_args()
    
    if args.command == "start":
        cli.start_new_draft(args.league_size, args.your_pick, args.scoring)
    elif args.command == "next":
        cli.get_next_recommendation()
    elif args.command == "pick":
        if not args.player:
            print("❌ --player required for pick command")
            return
        cli.add_draft_pick(args.player, args.position or "", args.player_id or "")
    elif args.command == "add-pick":
        if not args.player:
            print("❌ --player required for add-pick command")
            return
        cli.add_draft_pick(args.player, args.position or "", args.player_id or "", args.team)
    elif args.command == "def":
        team_name = args.player or "Unknown"
        cli.draft_defense(team_name, args.team)
    elif args.command == "board":
        cli.show_draft_board()
    elif args.command == "status":
        cli.show_status()
    elif args.command == "interactive":
        cli.interactive_draft()
    elif args.command == "reset":
        if os.path.exists(DRAFT_SESSION_FILE):
            os.remove(DRAFT_SESSION_FILE)
            print("🗑️  Draft session reset")
        else:
            print("❌ No session to reset")

if __name__ == "__main__":
    main()