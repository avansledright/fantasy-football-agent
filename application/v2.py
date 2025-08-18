#!/usr/bin/env python3
"""
Fantasy Football Draft CLI Tool with Interactive Snake Draft
Updated to the new DynamoDB schema (per-player 2024_actuals + 2025_projection)
- Preserves all original functionality: session save/load, interactive mode,
  board/status views, add-pick/def commands, snake logic, etc.
- Normalizes DEF -> DST to match allowed positions [QB, RB, WR, TE, K, DST].
- Player lookups now read name/position from top-level keys (Player, POSITION)
  and fantasy points from 2025_projection (fallback 2024_actuals).
- Correctly separates your roster from global draft picks.
"""

import json
import os
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
    rounds: int = 17  # 17 rounds
    
    def __post_init__(self):
        if self.picks is None:
            self.picks = []
    
    def get_picking_team(self, pick_number: int = None) -> int:
        pick_num = pick_number or self.current_pick
        round_num = ((pick_num - 1) // self.total_teams) + 1
        if round_num % 2 == 1:
            return ((pick_num - 1) % self.total_teams) + 1
        else:
            return self.total_teams - ((pick_num - 1) % self.total_teams)
    
    def get_round_and_position(self, pick_number: int = None) -> tuple:
        pick_num = pick_number or self.current_pick
        round_num = ((pick_num - 1) // self.total_teams) + 1
        position_in_round = ((pick_num - 1) % self.total_teams) + 1
        return round_num, position_in_round
    
    def is_your_turn(self) -> bool:
        return self.get_picking_team() == self.your_team_number
    
    def get_your_picks(self) -> List[DraftPick]:
        return [pick for pick in self.picks if pick.team_number == self.your_team_number]
    
    def get_all_drafted_player_ids(self) -> List[str]:
        return [pick.player.player_id for pick in self.picks if pick.player.player_id]
    
    def is_draft_complete(self) -> bool:
        return self.current_pick > (self.total_teams * self.rounds)

@dataclass
class Roster:
    qb: List[Player] = None
    rb: List[Player] = None  
    wr: List[Player] = None
    te: List[Player] = None
    dst: List[Player] = None
    k: List[Player] = None
    flex: List[Player] = None
    bench: List[Player] = None  
    
    def __post_init__(self):
        if self.qb is None: self.qb = []
        if self.rb is None: self.rb = []
        if self.wr is None: self.wr = []
        if self.te is None: self.te = []
        if self.dst is None: self.dst = []
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
        self.starter_limits = {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "DST": 1, "K": 1, "FLEX": 1}
        self.roster_limits  = {"QB": 3, "RB": 6, "WR": 6, "TE": 3, "DST": 2, "K": 2, "FLEX": 1, "BENCH": 6}

    @staticmethod
    def normalize_position(pos: str) -> str:
        pos = (pos or "").upper()
        if pos in {"DEF", "D/ST", "D-ST", "D\u0026ST"}:
            return "DST"
        return pos

    @staticmethod
    def _float(v, default=0.0) -> float:
        try:
            if v is None: return float(default)
            if isinstance(v, (int, float)): return float(v)
            if isinstance(v, str):
                return float(v.replace('%','').strip())
            return float(default)
        except Exception:
            return float(default)

    def summarize_item(self, item: Dict) -> Dict:
        proj = item.get("2025_projection") or {}
        actual = item.get("2024_actuals") or {}
        name = item.get("Player") or proj.get("Player") or actual.get("Player") or item.get("player_id", "")
        position = self.normalize_position(item.get("POSITION", ""))
        player_id = item.get("player_id", "")
        proj_pts = self._float(proj.get("MISC_FPTS", proj.get("FPTS", 0)))
        actual_pts = self._float(actual.get("MISC_FPTS", actual.get("FPTS", 0)))
        ppg = self._float(proj.get("MISC_FPTS/G", actual.get("MISC_FPTS/G", 0)))
        rank = int(actual.get("Rank", 999)) if str(actual.get("Rank", "")).isdigit() else 999
        return {
            "player_id": player_id,
            "name": name,
            "position": position,
            "proj_points": proj_pts,
            "last_year_points": actual_pts,
            "fantasy_points": proj_pts if proj_pts else actual_pts,
            "points_per_game": ppg,
            "rank": rank
        }

    def save_session(self):
        if not self.session:
            return
        session_data = asdict(self.session)
        with open(DRAFT_SESSION_FILE, 'w') as f:
            json.dump(session_data, f, indent=2)
        print("✅ Session saved")

    def load_session(self) -> bool:
        if not os.path.exists(DRAFT_SESSION_FILE):
            return False
        try:
            with open(DRAFT_SESSION_FILE, 'r') as f:
                session_data = json.load(f)
            roster_data = session_data['roster']
            if 'def_' in roster_data and 'dst' not in roster_data:
                roster_data['dst'] = roster_data.pop('def_')
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

    def load_player_cache(self):
        if self.player_cache:
            return True
        print("🔄 Loading player database...")
        try:
            import boto3
            from boto3.dynamodb.conditions import Attr
            dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
            table = dynamodb.Table("2025-2026-fantasy-football-player-data")

            players: List[Dict] = []
            response = table.scan(
                FilterExpression=Attr('Player').exists() & Attr('POSITION').exists()
            )
            players.extend(response.get("Items", []))
            while "LastEvaluatedKey" in response:
                response = table.scan(
                    FilterExpression=Attr('Player').exists() & Attr('POSITION').exists(),
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                players.extend(response.get("Items", []))
            self.player_cache = players
            print(f"✅ Loaded {len(self.player_cache)} players into memory")
            return True
        except Exception as e:
            print(f"❌ Error loading player cache: {e}")
            return False

    def lookup_player_full(self, player_name: str) -> Optional[dict]:
        if not self.player_cache and not self.load_player_cache():
            return None
        target = player_name.strip().lower()
        if not target:
            return None
        matches = []
        for item in self.player_cache:
            name = (item.get('Player') or '').lower()
            if not name:
                continue
            score = 0
            if name == target:
                score = 100
            elif name.startswith(target):
                score = 90
            elif target in name:
                score = 80
            else:
                tset = set(target.split())
                nset = set(name.split())
                if tset & nset:
                    score = 70
            if score:
                summary = self.summarize_item(item)
                summary['score'] = score
                matches.append(summary)
        if not matches:
            return None
        matches.sort(key=lambda x: (x['score'], x.get('proj_points', 0.0), x.get('last_year_points', 0.0)), reverse=True)
        best = matches[0]
        return {
            'score': best['score'],
            'player_id': best['player_id'],
            'name': best['name'],
            'position': best['position'],
            'team': '',
            'fantasy_points': float(best.get('proj_points') or best.get('last_year_points') or 0.0)
        }

    def lookup_player_id(self, player_name: str, position: str = "") -> str:
        try:
            import boto3
            from boto3.dynamodb.conditions import Attr
            dynamodb = boto3.resource("dynamodb", region_name="us-west-2")
            table = dynamodb.Table("2025-2026-fantasy-football-player-data")

            search_terms = [player_name, player_name.title(), player_name.upper(), player_name.lower()]
            for term in search_terms:
                resp = table.scan(
                    FilterExpression=Attr('Player').contains(term)
                )
                items = resp.get('Items', [])
                if position:
                    pos_norm = self.normalize_position(position)
                    items = [it for it in items if self.normalize_position(it.get('POSITION', '')) == pos_norm]
                if items:
                    pid = items[0].get('player_id', '')
                    if pid:
                        print(f"🔍 Found: {items[0].get('Player')} (ID: {pid})")
                        return pid
            print(f"❌ No match found for: {player_name} ({position})")
            return ""
        except Exception as e:
            print(f"❌ Lookup error: {e}")
            return ""

    def calculate_team_needs(self) -> Dict[str, int]:
        if not self.session:
            return self.starter_limits.copy()
        needs = {}
        r = self.session.roster
        needs["QB"]  = max(0, self.starter_limits["QB"]  - len(r.qb))
        needs["RB"]  = max(0, self.starter_limits["RB"]  - len(r.rb))
        needs["WR"]  = max(0, self.starter_limits["WR"]  - len(r.wr))
        needs["TE"]  = max(0, self.starter_limits["TE"]  - len(r.te))
        needs["DST"] = max(0, self.starter_limits["DST"] - len(r.dst))
        needs["K"]   = max(0, self.starter_limits["K"]   - len(r.k))
        needs["FLEX"] = max(0, self.starter_limits["FLEX"] - len(r.flex))
        return needs

    def call_agent_api(self, team_needs: Dict[str, int], all_drafted_players: List[str]) -> Dict:
        your_roster = {
            "QB": [p.name for p in self.session.roster.qb],
            "RB": [p.name for p in self.session.roster.rb],
            "WR": [p.name for p in self.session.roster.wr],
            "TE": [p.name for p in self.session.roster.te],
            "DST": [p.name for p in self.session.roster.dst],
            "K": [p.name for p in self.session.roster.k],
            "FLEX": [p.name for p in self.session.roster.flex],
            "BENCH": [p.name for p in self.session.roster.bench],
        }

        payload = {
            "team_needs": team_needs,
            "your_roster": your_roster,
            "already_drafted": all_drafted_players,
            "scoring_format": self.session.scoring_format if self.session else "ppr",
            "league_size": self.session.league_size if self.session else 12
        }
        print(f"Payload: {payload}")
        try:
            response = requests.post(API_ENDPOINT, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": f"API request failed: {e}"}

    # Draft logic and UI methods unchanged except fixed roster detection
    def start_new_draft(self, league_size: int = 12, your_pick: int = 1, scoring_format: str = "ppr"):
        if your_pick < 1 or your_pick > league_size:
            print(f"❌ Invalid draft position. Must be between 1 and {league_size}")
            return
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
        print("\n📅 Your upcoming early picks:")
        for round_num in range(1, 6):
            your_pick_in_round = self._get_your_pick_in_round(round_num)
            print(f"   Round {round_num}: Pick #{your_pick_in_round}")
        print("   ...")

    def _get_your_pick_in_round(self, round_num: int) -> int:
        if round_num % 2 == 1:
            return ((round_num - 1) * self.session.draft_board.total_teams) + self.session.draft_board.your_team_number
        else:
            return ((round_num - 1) * self.session.draft_board.total_teams) + (self.session.draft_board.total_teams - self.session.draft_board.your_team_number + 1)

    def add_to_roster(self, player: Player, position: str):
        r = self.session.roster
        pos = self.normalize_position(position)
        added = False
        if pos == "QB" and len(r.qb) < self.roster_limits["QB"]:
            r.qb.append(player); added = True
        elif pos == "RB" and len(r.rb) < self.roster_limits["RB"]:
            r.rb.append(player); added = True
        elif pos == "WR" and len(r.wr) < self.roster_limits["WR"]:
            r.wr.append(player); added = True
        elif pos == "TE" and len(r.te) < self.roster_limits["TE"]:
            r.te.append(player); added = True
        elif pos == "DST" and len(r.dst) < self.roster_limits["DST"]:
            r.dst.append(player); added = True
        elif pos == "K" and len(r.k) < self.roster_limits["K"]:
            r.k.append(player); added = True
        elif pos in ["RB", "WR", "TE"] and len(r.flex) < self.roster_limits["FLEX"]:
            r.flex.append(player); added = True
        elif len(r.bench) < self.roster_limits["BENCH"]:
            r.bench.append(player); added = True
            print(f"📝 Added {player.name} to BENCH")
        if not added:
            print(f"⚠️  Roster full - could not add {player.name}")

    def add_draft_pick(self, player_name: str, position: str = "", player_id: str = "", team_number: int = None):
        if not self.session:
            print("❌ No active draft session")
            return False
        board = self.session.draft_board
        if board.is_draft_complete():
            print("🏁 Draft is complete!")
            return False
        current_pick = board.current_pick
        round_num, pick_in_round = board.get_round_and_position(current_pick)
        picking_team = board.get_picking_team(current_pick) if team_number is None else team_number

        player = Player(
            name=player_name,
            position=self.normalize_position(position) if position else "",
            player_id=player_id,
            team=""
        )
        draft_pick = DraftPick(pick_number=current_pick, team_number=picking_team, player=player)
        board.picks.append(draft_pick)
        board.current_pick += 1

        if picking_team == board.your_team_number:
            self.add_to_roster(player, player.position or position)
            print(f"✅ YOUR PICK #{current_pick} (Round {round_num}.{pick_in_round}): {player_name} ({player.position or position})")
        else:
            print(f"📝 Pick #{current_pick} (Round {round_num}.{pick_in_round}, Team {picking_team}): {player_name} ({player.position or position})")
        self.save_session()
        return True

    def draft_dst(self, team_name: str = "", team_number: int = None):
        if not self.session:
            print("❌ No active draft session")
            return False
        board = self.session.draft_board
        if not team_name:
            team_name = "DST"
        picking_team = board.get_picking_team() if team_number is None else team_number
        if team_number is None and not board.is_your_turn():
            print("❌ Not your turn to pick!")
            return False
        current_pick = board.current_pick
        round_num, pick_in_round = board.get_round_and_position(current_pick)
        player = Player(
            name=f"{team_name} DST",
            position="DST",
            player_id=f"dst_{team_name.lower()}_{current_pick}",
            team=team_name
        )
        draft_pick = DraftPick(pick_number=current_pick, team_number=picking_team, player=player)
        board.picks.append(draft_pick)
        board.current_pick += 1
        if picking_team == board.your_team_number:
            self.add_to_roster(player, "DST")
            print(f"✅ YOUR PICK #{current_pick} (Round {round_num}.{pick_in_round}): {team_name} DST")
        else:
            print(f"📝 Pick #{current_pick} (Round {round_num}.{pick_in_round}, Team {picking_team}): {team_name} DST")
        self.save_session()
        return True

    # ------------------------------
    # Agent + UI
    # ------------------------------
    def get_next_recommendation(self):
        if not self.session:
            print("❌ No active draft session")
            return
        board = self.session.draft_board
        if board.is_draft_complete():
            print("🏁 Draft is complete!")
            return
        if not board.is_your_turn():
            next_team = board.get_picking_team()
            print(f"⏸️  Not your turn! Team {next_team} is picking")
            return
        team_needs = self.calculate_team_needs()
        all_drafted_players = board.get_all_drafted_player_ids()
        print(f"All drafted players = {all_drafted_players}")
        current_pick = board.current_pick
        round_num, pick_in_round = board.get_round_and_position(current_pick)
        print(f"🤖 Getting recommendation for YOUR pick #{current_pick} (Round {round_num}.{pick_in_round})...")
        print(f"🔍 Excluding {len(all_drafted_players)} already drafted players...")    
        result = self.call_agent_api(team_needs, all_drafted_players)
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return
        try:
            recommendation_text = ""
            if 'body' in result:
                body = json.loads(result['body']) if isinstance(result['body'], str) else result['body']
                recommendation_content = body.get('recommendation', '')
            else:
                recommendation_content = result.get('recommendation', '')
            if isinstance(recommendation_content, str):
                recommendation_text = recommendation_content
            elif isinstance(recommendation_content, dict):
                primary = recommendation_content.get('primary_recommendation', {})
                if primary:
                    name = primary.get('name', 'Unknown')
                    position = self.normalize_position(primary.get('position', '?'))
                    team = primary.get('team', '')
                    fantasy_points = float(primary.get('fantasy_points', 0) or 0)
                    ppg = float(primary.get('points_per_game', 0) or 0)
                    reasoning = primary.get('reasoning', 'No reasoning provided')
                    recommendation_text = (f"🏈 RECOMMENDED: {name} ({position}) - {team}\n"
                                           f"📊 {fantasy_points:.1f} PPR points ({ppg:.1f} PPG)\n"
                                           f"💭 {reasoning}\n")
                    alternatives = recommendation_content.get('alternatives', [])
                    if alternatives:
                        recommendation_text += f"\n📋 ALTERNATIVES:\n"
                        for i, alt in enumerate(alternatives[:3], 1):
                            recommendation_text += (f"   {i}. {alt.get('name')} ({self.normalize_position(alt.get('position',''))}, {alt.get('team','')})"
                                                    f" - {float(alt.get('fantasy_points',0) or 0):.1f} pts\n")
                else:
                    recommendation_text = str(recommendation_content)
            if recommendation_text:
                lines = [ln.strip().replace('**','').replace('*','') for ln in recommendation_text.split('\n') if ln.strip()]
                print("\n" + "="*60)
                print("🤖 AI RECOMMENDATION:")
                print("="*60)
                for line in lines:
                    if line.startswith(tuple(str(i)+'.' for i in range(1,10))) or line.startswith('-'):
                        print(f"   {line}")
                    else:
                        print(line)
                print("="*60)
            else:
                print("❌ No recommendation received")
        except Exception as e:
            print(f"❌ Error parsing recommendation: {e}")
            print(f"Debug - Raw result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")

    # ------------------------------
    # UI helpers
    # ------------------------------
    def interactive_draft(self):
        if not self.session:
            print("❌ No active draft session. Start with: python v2.py start")
            return
        if not self.player_cache and not self.load_player_cache():
            print("❌ Failed to load player database")
            return
        board = self.session.draft_board
        print(f"\n🎯 INTERACTIVE DRAFT MODE")
        print("Commands: 'next' (get recommendation), 'def [team]' (draft DST), 'quit' (exit)")
        print("Or just enter player name (position and ID will be auto-detected)")
        print("=" * 60)
        while not board.is_draft_complete():
            current_pick = board.current_pick
            round_num, pick_in_round = board.get_round_and_position(current_pick)
            picking_team = board.get_picking_team()
            prompt = (f"🎯 YOUR TURN - Pick #{current_pick} (Round {round_num}.{pick_in_round}): "
                      if board.is_your_turn() else
                      f"⏳ Team {picking_team} Pick #{current_pick} (Round {round_num}.{pick_in_round}): ")
            try:
                user_input = input(prompt).strip()
                if not user_input:
                    continue
                low = user_input.lower()
                if low == 'quit':
                    print("👋 Exiting interactive mode"); break
                if low == 'next':
                    if board.is_your_turn(): self.get_next_recommendation()
                    else: print("❌ Not your turn!")
                    continue
                if low.startswith('def') or low.startswith('dst'):
                    parts = user_input.split()
                    team_name = parts[1] if len(parts) > 1 else "Unknown"
                    if board.is_your_turn():
                        if self.draft_dst(team_name):
                            continue
                    else:
                        if self.draft_dst(team_name, picking_team):
                            continue
                    continue
                # Otherwise treat as player name
                player_name = user_input.strip()
                print(f"🔍 Looking up: {player_name}")
                player_data = self.lookup_player_full(player_name)
                if player_data:
                    position = self.normalize_position(player_data['position'])
                    player_id = player_data['player_id']
                    full_name = player_data['name']
                    print(f"✅ Found: {full_name} ({position}) - ID: {player_id}")
                    team_num = None if board.is_your_turn() else picking_team
                    if self.add_draft_pick(full_name, position, player_id, team_num):
                        continue
                    else:
                        print("❌ Failed to add pick")
                else:
                    print(f"❌ Could not find player: {player_name}")
                    response = input("Continue anyway? Enter position (QB/RB/WR/TE/K/DST) or 'n' to skip: ").strip()
                    if response.lower() == 'n':
                        continue
                    pos = self.normalize_position(response.upper())
                    if pos in ['QB','RB','WR','TE','K','DST']:
                        player_id = f"manual_{player_name.lower().replace(' ', '_')}_{pos}_{board.current_pick}"
                        team_num = None if board.is_your_turn() else picking_team
                        if self.add_draft_pick(player_name, pos, player_id, team_num):
                            continue
                        else:
                            print("❌ Failed to add pick")
                    else:
                        print("❌ Invalid position"); continue
            except KeyboardInterrupt:
                print("\n👋 Exiting interactive mode"); break
            except Exception as e:
                print(f"❌ Error: {e}")
        if board.is_draft_complete():
            print("🏁 Draft completed!")
            self.show_final_roster()

    def show_draft_board(self):
        if not self.session:
            print("❌ No active draft session"); return
        board = self.session.draft_board
        current_pick = board.current_pick
        round_num, pick_in_round = board.get_round_and_position(current_pick)
        print(f"\n📋 SNAKE DRAFT BOARD")
        print(f"Current: Pick #{current_pick} (Round {round_num}.{pick_in_round}) - Team {board.get_picking_team()}")
        print(f"Your team: #{board.your_team_number}")
        print(f"Your turn: {'🎯 YES' if board.is_your_turn() else '⏳ NO'}")
        if board.picks:
            recent = board.picks[-10:] if len(board.picks) > 10 else board.picks
            print(f"\n📝 Recent picks:")
            for pick in recent:
                r, p = board.get_round_and_position(pick.pick_number)
                marker = "👤" if pick.team_number == board.your_team_number else f"T{pick.team_number}"
                print(f"   #{pick.pick_number:2d} (R{r}.{p}, {marker}): {pick.player.name} ({pick.player.position})")
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
        if not self.session:
            print("❌ No active draft session"); return
        board = self.session.draft_board
        print(f"\n📊 DRAFT STATUS")
        print(f"League: {self.session.league_size} teams | Format: {self.session.scoring_format.upper()}")
        print(f"Your position: #{board.your_team_number}")
        your_picks = board.get_your_picks()
        print(f"Your picks: {len(your_picks)}/17")
        print(f"\n🏈 YOUR ROSTER:")
        r = self.session.roster
        positions = [
            ("QB", r.qb, self.roster_limits["QB"]),
            ("RB", r.rb, self.roster_limits["RB"]),
            ("WR", r.wr, self.roster_limits["WR"]),
            ("TE", r.te, self.roster_limits["TE"]),
            ("DST", r.dst, self.roster_limits["DST"]),
            ("K", r.k, self.roster_limits["K"]),
            ("FLEX", r.flex, self.roster_limits["FLEX"]),
            ("BENCH", r.bench, self.roster_limits["BENCH"]),
        ]
        for pos, players, limit in positions:
            filled = len(players)
            if filled == 0:
                print(f"   {pos}: Empty (0/{limit})")
            else:
                names = ", ".join(p.name for p in players)
                print(f"   {pos}: {names} ({filled}/{limit})")

    def show_final_roster(self):
        print(f"\n🏆 FINAL ROSTER SUMMARY")
        self.show_status()
        your_picks = self.session.draft_board.get_your_picks()
        print(f"\n📋 YOUR DRAFT PICKS:")
        for pick in your_picks:
            r, p = self.session.draft_board.get_round_and_position(pick.pick_number)
            print(f"   R{r}.{p:2d} (#{pick.pick_number:2d}): {pick.player.name} ({pick.player.position})")

# Entrypoint

def main():
    cli = FantasyDraftCLI()
    cli.load_session()
    parser = argparse.ArgumentParser(description="Fantasy Football Snake Draft Assistant")
    parser.add_argument("command", choices=["start","next","pick","add-pick","def","board","status","interactive","reset"], nargs='?', default="interactive")
    parser.add_argument("--player", help="Player name")
    parser.add_argument("--position", help="Player position")
    parser.add_argument("--player-id", help="Player ID")
    parser.add_argument("--team", type=int, help="Team number")
    parser.add_argument("--league-size", type=int, default=8)
    parser.add_argument("--your-pick", type=int, default=3)
    parser.add_argument("--scoring", choices=["ppr","half_ppr","standard"], default="ppr")
    args = parser.parse_args()

    if args.command == "start":
        cli.start_new_draft(args.league_size, args.your_pick, args.scoring)
    elif args.command == "next":
        cli.get_next_recommendation()
    elif args.command == "pick":
        cli.add_draft_pick(args.player, args.position or "", args.player_id or "")
    elif args.command == "add-pick":
        cli.add_draft_pick(args.player, args.position or "", args.player_id or "", args.team)
    elif args.command == "def":
        cli.draft_defense(args.player or "Unknown", args.team)
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

if __name__ == "__main__":
    main()
