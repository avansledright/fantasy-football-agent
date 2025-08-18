#!/usr/bin/env python3
"""
Fantasy Football Draft CLI Tool with Full Draft Board
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
    rounds: int = 16  # Standard 16-round draft
    
    def __post_init__(self):
        if self.picks is None:
            self.picks = []
    
    def get_picking_team(self, pick_number: int = None) -> int:
        """Calculate which team is picking based on snake draft order."""
        pick_num = pick_number or self.current_pick
        round_num = ((pick_num - 1) // self.total_teams) + 1
        
        if round_num % 2 == 1:  # Odd rounds (1, 3, 5...)
            return ((pick_num - 1) % self.total_teams) + 1
        else:  # Even rounds (2, 4, 6...) - reverse order
            return self.total_teams - ((pick_num - 1) % self.total_teams)
    
    def is_your_turn(self) -> bool:
        """Check if it's your team's turn to pick."""
        return self.get_picking_team() == self.your_team_number
    
    def get_your_picks(self) -> List[DraftPick]:
        """Get all picks made by your team."""
        return [pick for pick in self.picks if pick.team_number == self.your_team_number]
    
    def get_all_drafted_player_ids(self) -> List[str]:
        """Get all player IDs that have been drafted."""
        return [pick.player.player_id for pick in self.picks if pick.player.player_id]

@dataclass
class Roster:
    qb: List[Player] = None
    rb: List[Player] = None  
    wr: List[Player] = None
    te: List[Player] = None
    def_: List[Player] = None
    k: List[Player] = None
    flex: List[Player] = None
    
    def __post_init__(self):
        if self.qb is None: self.qb = []
        if self.rb is None: self.rb = []
        if self.wr is None: self.wr = []
        if self.te is None: self.te = []
        if self.def_ is None: self.def_ = []
        if self.k is None: self.k = []
        if self.flex is None: self.flex = []

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
        self.roster_limits = {
            "QB": 2, "RB": 2, "WR": 2, "TE": 1, 
            "DEF": 1, "K": 1, "FLEX": 1
        }
    
    def save_session(self):
        """Save current draft session to file."""
        if not self.session:
            return
            
        session_data = asdict(self.session)
        with open(DRAFT_SESSION_FILE, 'w') as f:
            json.dump(session_data, f, indent=2)
        print(f"✅ Session saved to {DRAFT_SESSION_FILE}")
    
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
                rounds=board_data.get('rounds', 16)
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
        """Calculate remaining roster needs for YOUR team only."""
        if not self.session:
            return self.roster_limits.copy()
            
        needs = {}
        roster = self.session.roster
        
        needs["QB"] = max(0, self.roster_limits["QB"] - len(roster.qb))
        needs["RB"] = max(0, self.roster_limits["RB"] - len(roster.rb))
        needs["WR"] = max(0, self.roster_limits["WR"] - len(roster.wr))
        needs["TE"] = max(0, self.roster_limits["TE"] - len(roster.te))
        needs["DEF"] = max(0, self.roster_limits["DEF"] - len(roster.def_))
        needs["K"] = max(0, self.roster_limits["K"] - len(roster.k))
        needs["FLEX"] = max(0, self.roster_limits["FLEX"] - len(roster.flex))
        
        return needs
    
    def call_agent_api(self, team_needs: Dict[str, int], all_drafted_players: List[str]) -> Dict:
        """Call the AWS API Gateway endpoint with ALL drafted players."""
        payload = {
            "team_needs": team_needs,
            "already_drafted": all_drafted_players,
            "scoring_format": self.session.scoring_format if self.session else "ppr",
            "league_size": self.session.league_size if self.session else 12
        }
        
        print(f"🔍 Debug: Payload being sent: {json.dumps(payload)}")
        
        try:
            response = requests.post(API_ENDPOINT, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            print(f"🔍 Debug: API response: {json.dumps(result)}")
            return result
        except requests.exceptions.RequestException as e:
            return {"error": f"API request failed: {e}"}
    
    def start_new_draft(self, league_size: int = 12, your_pick: int = 1, scoring_format: str = "ppr"):
        """Initialize a new draft session with your draft position."""
        if your_pick < 1 or your_pick > league_size:
            print(f"❌ Invalid draft position. Must be between 1 and {league_size}")
            return
            
        self.session = DraftSession(
            roster=Roster(),
            draft_board=DraftBoard(
                total_teams=league_size,
                current_pick=1,
                your_team_number=your_pick,
                picks=[],
                rounds=16
            ),
            league_size=league_size,
            scoring_format=scoring_format
        )
        self.save_session()
        print(f"🏈 New {league_size}-team {scoring_format.upper()} draft started!")
        print(f"📍 Your draft position: #{your_pick}")
        print(f"📋 Roster format: {dict(self.roster_limits)}")
        
        # Show initial draft order info
        print(f"\n📅 Draft order preview:")
        for round_num in range(1, 4):  # Show first 3 rounds
            your_pick_in_round = self._get_your_pick_in_round(round_num)
            print(f"   Round {round_num}: Your pick #{your_pick_in_round}")
    
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
        
        if position == "QB" and len(roster.qb) < self.roster_limits["QB"]:
            roster.qb.append(player)
        elif position == "RB" and len(roster.rb) < self.roster_limits["RB"]:
            roster.rb.append(player)
        elif position == "WR" and len(roster.wr) < self.roster_limits["WR"]:
            roster.wr.append(player)
        elif position == "TE" and len(roster.te) < self.roster_limits["TE"]:
            roster.te.append(player)
        elif position == "DEF" and len(roster.def_) < self.roster_limits["DEF"]:
            roster.def_.append(player)
        elif position == "K" and len(roster.k) < self.roster_limits["K"]:
            roster.k.append(player)
        elif position in ["RB", "WR", "TE"] and len(roster.flex) < self.roster_limits["FLEX"]:
            roster.flex.append(player)
        else:
            print(f"⚠️  Could not add {player.name} to roster - {position} may be full")
    def lookup_player_id(self, player_name: str, position: str = "") -> str:
        """Look up player ID from DynamoDB if not provided."""
        try:
            import boto3
            from boto3.dynamodb.conditions import Attr
            
            dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
            table = dynamodb.Table("2025-2026-fantasy-football-player-data")
            
            # Search for player by name
            response = table.scan(
                FilterExpression=Attr('player_display_name').contains(player_name)
            )
            
            items = response.get('Items', [])
            
            # If position provided, filter by position
            if position:
                items = [item for item in items if item.get('position', '').upper() == position.upper()]
            
            if items:
                # Return the first match's player_id
                player_id = items[0].get('player_id', '')
                print(f"🔍 Found player ID: {player_id} for {player_name}")
                return player_id
            else:
                print(f"⚠️  Could not find player ID for {player_name}")
                return ""
        except Exception as e:
            print(f"⚠️  Error looking up player ID: {e}")
            return ""
    def add_draft_pick(self, player_name: str, position: str = "", player_id: str = "", team_number: int = None):
        """Add a draft pick for any team."""
        if not self.session:
            print("❌ No active draft session")
            return
        
        # If no player_id provided, try to look it up
        if not player_id:
            player_id = self.lookup_player_id(player_name, position)
            
            board = self.session.draft_board
            current_pick = board.current_pick
            
        # Determine which team is picking
        if team_number is None:
            picking_team = board.get_picking_team(current_pick)
        else:
            picking_team = team_number
        
        player = Player(
            name=player_name,
            position=position.upper() if position else "",
            player_id=player_id,  # This needs to be provided!
            team=""  # NFL team, not fantasy team
        )
        
        draft_pick = DraftPick(
            pick_number=current_pick,
            team_number=picking_team,
            player=player
        )
        
        board.picks.append(draft_pick)
        board.current_pick += 1
        
        # Debug: Show what we're storing
        print(f"🔍 Debug: Stored player_id '{player_id}' for {player_name}")
        
        # If it's your team, add to roster
        if picking_team == board.your_team_number:
            self.add_to_roster(player, position)
            print(f"✅ YOUR PICK #{current_pick}: {player_name} ({position})")
        else:
            print(f"📝 Pick #{current_pick} (Team {picking_team}): {player_name} ({position})")
        
        self.save_session()
        
        # Debug: Show all drafted player IDs
        all_drafted = board.get_all_drafted_player_ids()
        print(f"🔍 Debug: Total drafted player IDs: {len(all_drafted)} - {all_drafted}")
        
        # Show next pick info
        if board.current_pick <= board.total_teams * board.rounds:
            next_team = board.get_picking_team()
            
            if next_team == board.your_team_number:
                print(f"🎯 YOUR TURN NEXT! (Pick #{board.current_pick})")
            else:
                picks_until_your_turn = self._picks_until_your_turn()
                if picks_until_your_turn <= 3:
                    print(f"⏳ Next: Team {next_team} (Pick #{board.current_pick}) - You're up in {picks_until_your_turn} picks!")
                else:
                    print(f"⏳ Next: Team {next_team} (Pick #{board.current_pick})")
    
    def _picks_until_your_turn(self) -> int:
        """Calculate how many picks until it's your turn."""
        board = self.session.draft_board
        picks_ahead = 0
        
        for pick_num in range(board.current_pick, board.total_teams * board.rounds + 1):
            if board.get_picking_team(pick_num) == board.your_team_number:
                return picks_ahead
            picks_ahead += 1
        
        return 999  # No more picks
    
    def get_next_recommendation(self):
        """Get AI recommendation for next pick (only when it's your turn)."""
        if not self.session:
            print("❌ No active draft session. Start with: python main.py start")
            return
        
        board = self.session.draft_board
        
        # Check if it's your turn
        if not board.is_your_turn():
            next_team = board.get_picking_team()
            picks_until_turn = self._picks_until_your_turn()
            print(f"⏸️  Not your turn! Team {next_team} is picking (Pick #{board.current_pick})")
            print(f"📅 You're up in {picks_until_turn} picks")
            return
        
        team_needs = self.calculate_team_needs()
        all_drafted_players = board.get_all_drafted_player_ids()
        
        print(f"🤖 Consulting AI agent for YOUR pick #{board.current_pick}...")
        print(f"🔍 Excluding {len(all_drafted_players)} already drafted players...")
        
        result = self.call_agent_api(team_needs, all_drafted_players)
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return
            
        # Parse and display recommendation (same as before)
        try:
            if 'body' in result:
                if isinstance(result['body'], str):
                    body = json.loads(result['body'])
                else:
                    body = result['body']
                recommendation = body.get('recommendation', {})
            else:
                recommendation = result
            
            if isinstance(recommendation, dict):
                primary = recommendation.get('primary_recommendation', {})
                if primary:
                    name = primary.get('name', 'Unknown')
                    position = primary.get('position', '?')
                    team = primary.get('team', '')
                    fantasy_points = primary.get('fantasy_points', 0)
                    ppg = primary.get('points_per_game', 0)
                    age = primary.get('age', 0)
                    years_exp = primary.get('years_exp', 0)
                    rank = primary.get('rank', 999)
                    player_id = primary.get('player_id', '')
                    
                    print(f"\n🏈 RECOMMENDED PICK #{board.current_pick}: {name} ({position}) - {team}")
                    print(f"   {recommendation.get('scoring_format', 'PPR')} Points: {fantasy_points:.1f} ({ppg:.1f} PPG)")
                    print(f"   Age: {age} | Experience: {years_exp} years | Rank: {rank}")
                    print(f"   Player ID: {player_id}")
                    print(f"   Reasoning: {primary.get('reasoning', 'No reasoning provided')}")
                    
                    alternatives = recommendation.get('alternatives', [])
                    if alternatives:
                        print(f"\n📋 ALTERNATIVES:")
                        for i, alt in enumerate(alternatives[:3], 1):
                            alt_name = alt.get('name', 'Unknown')
                            alt_pos = alt.get('position', '?')
                            alt_team = alt.get('team', '')
                            alt_points = alt.get('fantasy_points', 0)
                            alt_ppg = alt.get('points_per_game', 0)
                            print(f"   {i}. {alt_name} ({alt_pos}, {alt_team}) - {alt_points:.1f} pts ({alt_ppg:.1f} PPG)")
                    
                    print(f"\n💡 To draft this player: python main.py pick --player \"{name}\" --position {position} --player-id {player_id}")
                    
                else:
                    print(f"🏈 {recommendation}")
            
        except Exception as e:
            print(f"❌ Error parsing recommendation: {e}")
            print(f"Raw response: {result}")
    
    def show_draft_board(self):
        """Display the current draft board."""
        if not self.session:
            print("❌ No active draft session")
            return
        
        board = self.session.draft_board
        print(f"\n📋 DRAFT BOARD")
        print(f"Current pick: #{board.current_pick} (Team {board.get_picking_team()})")
        print(f"Your team: #{board.your_team_number}")
        print(f"Your turn: {'🎯 YES' if board.is_your_turn() else '⏳ NO'}")
        
        if board.picks:
            # Group picks by round
            rounds = {}
            for pick in board.picks:
                round_num = ((pick.pick_number - 1) // board.total_teams) + 1
                if round_num not in rounds:
                    rounds[round_num] = []
                rounds[round_num].append(pick)
            
            for round_num in sorted(rounds.keys()):
                print(f"\n🔄 Round {round_num}:")
                round_picks = sorted(rounds[round_num], key=lambda x: x.pick_number)
                for pick in round_picks:
                    marker = "👤 YOU" if pick.team_number == board.your_team_number else f"Team {pick.team_number:2d}"
                    print(f"   #{pick.pick_number:2d} ({marker}): {pick.player.name} ({pick.player.position})")
        else:
            print("\n📝 No picks made yet")
    
    def show_status(self):
        """Display current roster and remaining needs."""
        if not self.session:
            print("❌ No active draft session")
            return
        
        board = self.session.draft_board
        print(f"\n📊 DRAFT STATUS")
        print(f"League: {self.session.league_size} teams | Format: {self.session.scoring_format.upper()}")
        print(f"Your position: #{board.your_team_number}")
        print(f"Current pick: #{board.current_pick}")
        print(f"Your turn: {'🎯 YES' if board.is_your_turn() else '⏳ NO'}")
        
        your_picks = board.get_your_picks()
        print(f"Your picks made: {len(your_picks)}")
        
        # Show roster
        print(f"\n🏈 YOUR ROSTER:")
        roster = self.session.roster
        
        positions = [
            ("QB", roster.qb, 2), ("RB", roster.rb, 2), ("WR", roster.wr, 2),
            ("TE", roster.te, 1), ("DEF", roster.def_, 1), ("K", roster.k, 1), ("FLEX", roster.flex, 1)
        ]
        
        for pos, players, limit in positions:
            filled = len(players)
            if filled == 0:
                print(f"   {pos}: Empty ({limit} needed)")
            else:
                player_names = []
                for p in players:
                    if p.team:
                        player_names.append(f"{p.name} ({p.team})")
                    else:
                        player_names.append(p.name)
                
                remaining = limit - filled
                status = f"({remaining} more needed)" if remaining > 0 else "✅ Complete"
                print(f"   {pos}: {', '.join(player_names)} {status}")
        
        needs = self.calculate_team_needs()
        total_needed = sum(needs.values())
        print(f"\nTotal spots remaining: {total_needed}")

def main():
    cli = FantasyDraftCLI()
    
    # Try to load existing session
    if cli.load_session():
        print("📁 Loaded existing draft session")
    
    parser = argparse.ArgumentParser(description="Fantasy Football Draft Assistant")
    parser.add_argument("command", choices=["start", "next", "pick", "add-pick", "board", "status", "undo", "reset"])
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
        # Make your own pick
        if not args.player:
            print("❌ --player required for pick command")
            return
        cli.add_draft_pick(args.player, args.position or "", args.player_id or "")
    elif args.command == "add-pick":
        # Add someone else's pick
        if not args.player:
            print("❌ --player required for add-pick command")
            return
        cli.add_draft_pick(args.player, args.position or "", args.player_id or "", args.team)
    elif args.command == "board":
        cli.show_draft_board()
    elif args.command == "status":
        cli.show_status()
    elif args.command == "reset":
        if os.path.exists(DRAFT_SESSION_FILE):
            os.remove(DRAFT_SESSION_FILE)
            print("🗑️  Draft session reset")
        else:
            print("❌ No session to reset")

if __name__ == "__main__":
    main()