from typing import Dict, List, TypedDict, Literal, Any, Optional
import json
from strands import tool

Positions = Literal["QB", "RB", "WR", "TE", "K", "DST"]

class Candidate(TypedDict, total=False):
    name: str
    position: Positions
    team: str
    opp: str
    projected: float
    recent4_avg: float
    vs_opp_avg: float | None
    adjusted: float

def _adjusted_score(projected: float, recent4: float, vs_opp: float | None) -> float:
    """Calculate adjusted score with fallback logic."""
    p = projected if projected is not None and projected > 0 else 0.0
    r = recent4 if recent4 is not None and recent4 > 0 else p
    v = vs_opp if vs_opp is not None and vs_opp > 0 else r
    
    # If we have no data, return 0
    if p == 0 and r == 0 and (v is None or v == 0):
        return 0.0
    
    # Weighted blend: 70% projection, 20% vs opponent, 10% recent form
    return round(0.70 * p + 0.20 * v + 0.10 * r, 4)

def _slot_order(lineup_slots: List[str]) -> List[str]:
    return [s.upper().strip() for s in lineup_slots]

def _fits(slot: str, pos: str) -> bool:
    """Check if a position fits in a lineup slot."""
    slot = slot.upper().strip()
    pos = pos.upper().strip()
    
    if slot in ("QB", "RB", "WR", "TE", "K", "DST", "DEF"):
        return slot == pos or (slot == "DEF" and pos == "DST") or (slot == "DST" and pos == "DEF")
    if slot == "FLEX":
        return pos in ("RB", "WR", "TE")
    if slot == "OP":  # Offensive Player slot
        return pos in ("QB", "RB", "WR", "TE")
    return False

def _normalize_player_name(name: str) -> str:
    """Normalize player names for matching."""
    if not name:
        return ""
    return name.strip().lower()

def _parse_projections_data(projections_raw: Any) -> Dict[str, List[Dict[str, Any]]]:
    """Parse projections data from various formats."""
    if isinstance(projections_raw, str):
        try:
            projections_raw = json.loads(projections_raw)
        except:
            print(f"Failed to parse projections JSON: {projections_raw[:200]}...")
            return {}
    
    if isinstance(projections_raw, dict):
        return projections_raw
    
    print(f"Unexpected projections format: {type(projections_raw)}")
    return {}

def _parse_roster_data(roster_raw: Any) -> Dict[str, Any]:
    """Parse roster data from various formats."""
    if isinstance(roster_raw, str):
        try:
            roster_raw = json.loads(roster_raw)
        except:
            print(f"Failed to parse roster JSON: {roster_raw[:200]}...")
            return {"players": []}
    
    if isinstance(roster_raw, dict):
        return roster_raw
    
    print(f"Unexpected roster format: {type(roster_raw)}")
    return {"players": []}

def _parse_histories_data(histories_raw: Any) -> Dict[str, Dict[str, Any]]:
    """Parse histories data from various formats."""
    if isinstance(histories_raw, str):
        try:
            histories_raw = json.loads(histories_raw)
        except:
            print(f"Failed to parse histories JSON: {histories_raw[:200]}...")
            return {}
    
    if isinstance(histories_raw, dict):
        return histories_raw
    
    print(f"Unexpected histories format: {type(histories_raw)}")
    return {}

# @tool
# def choose_optimal_lineup(
#     lineup_slots: List[str],
#     roster: Any,
#     projections: Any,
#     histories: Any,
# ) -> Dict[str, Any]:
#     """Pick the optimal lineup given slots, roster, projections and history.

#     Args:
#       lineup_slots: e.g. ["QB","RB","RB","WR","WR","TE","FLEX","K","DST"]
#       roster: TeamRoster object or JSON string from get_team_roster
#       projections: dict or JSON string from get_weekly_projections()
#       histories: dict or JSON string mapping player name -> history dict

#     Returns:
#       dict with "lineup", "bench", and "debug_info"
#     """
    
#     # Parse all input data with robust error handling
#     roster_data = _parse_roster_data(roster)
#     projections_data = _parse_projections_data(projections)
#     histories_data = _parse_histories_data(histories)
    
#     print(f"Parsed {len(roster_data.get('players', []))} roster players")
#     print(f"Parsed {len(projections_data)} projection position groups")
#     print(f"Parsed {len(histories_data)} player histories")
    
#     # Build projection lookup by normalized name
#     proj_index: Dict[str, Dict[str, Any]] = {}
    
#     for pos, rows in projections_data.items():
#         if not isinstance(rows, list):
#             continue
#         for row in rows:
#             if not isinstance(row, dict):
#                 continue
#             name = row.get("name", "")
#             if name:
#                 # Try multiple keys for matching
#                 normalized_name = _normalize_player_name(name)
#                 position = row.get("position", pos).upper()
                
#                 # Store with multiple possible keys for matching
#                 proj_index[normalized_name] = row
#                 proj_index[f"{normalized_name}_{position}"] = row
                
#     print(f"Built projection index with {len(proj_index)} entries")
    
#     # Build candidates from roster players
#     candidates: List[Candidate] = []
    
#     for player in roster_data.get("players", []):
#         name = player.get("name", "")
#         if not name:
#             continue
            
#         pos = player.get("position", "").upper()
#         if pos not in ("QB", "RB", "WR", "TE", "K", "DST", "DEF"):
#             print(f"Skipping {name} - unsupported position: {pos}")
#             continue
        
#         # Normalize DST/DEF
#         if pos == "DEF":
#             pos = "DST"
        
#         # Look up projection
#         normalized_name = _normalize_player_name(name)
#         proj = (proj_index.get(normalized_name) or 
#                 proj_index.get(f"{normalized_name}_{pos}") or
#                 {})
        
#         projected = 0.0
#         if proj:
#             # Try multiple projection field names
#             projected = (proj.get("projected") or 
#                         proj.get("projection") or 
#                         proj.get("points") or 
#                         proj.get("fantasy_points") or 0.0)
#             try:
#                 projected = float(projected)
#             except (ValueError, TypeError):
#                 projected = 0.0
        
#         team = proj.get("team", player.get("team", ""))
#         opp = proj.get("opp", proj.get("opponent", ""))
        
#         # Get history data
#         hist = histories_data.get(name, {})
#         recent4 = hist.get("recent4_avg", 0.0)
#         vs_opp = hist.get("vs_opp_avg", None)
        
#         # Calculate adjusted score
#         adj = _adjusted_score(projected, recent4, vs_opp)
        
#         candidate = Candidate(
#             name=name,
#             position=pos,
#             team=team,
#             opp=opp,
#             projected=projected,
#             recent4_avg=recent4,
#             vs_opp_avg=vs_opp,
#             adjusted=adj
#         )
#         candidates.append(candidate)
        
#         if projected > 0:
#             print(f"Added candidate: {name} ({pos}) - Proj: {projected}, Adj: {adj}")
    
#     print(f"Built {len(candidates)} candidates")
    
#     if not candidates:
#         return {
#             "lineup": [{"slot": slot, "player": None, "error": "No valid candidates"} 
#                       for slot in _slot_order(lineup_slots)],
#             "bench": [],
#             "debug_info": {
#                 "error": "No valid candidates found",
#                 "roster_players": len(roster_data.get("players", [])),
#                 "projections_available": len(proj_index),
#                 "histories_available": len(histories_data)
#             }
#         }
    
#     # Greedy lineup selection
#     chosen: List[Dict[str, Any]] = []
#     used_names: set[str] = set()
    
#     for slot in _slot_order(lineup_slots):
#         # Find candidates that fit this slot and aren't used
#         fitting = [c for c in candidates 
#                   if _fits(slot, c["position"]) and c["name"] not in used_names]
        
#         if not fitting:
#             chosen.append({
#                 "slot": slot,
#                 "player": None,
#                 "error": f"No available players for {slot}"
#             })
#             continue
        
#         # Sort by adjusted score, then projected score
#         fitting.sort(key=lambda x: (x["adjusted"], x["projected"]), reverse=True)
#         pick = fitting[0]
#         used_names.add(pick["name"])
        
#         chosen.append({
#             "slot": slot,
#             "player": pick["name"],
#             "team": pick["team"],
#             "position": pick["position"],
#             "projected": pick["projected"],
#             "adjusted": pick["adjusted"],
#             "opp": pick["opp"],
#         })
        
#         print(f"Selected for {slot}: {pick['name']} (adj: {pick['adjusted']})")
    
#     # Build bench (remaining players, sorted by adjusted score)
#     bench = [c for c in candidates if c["name"] not in used_names]
#     bench.sort(key=lambda x: (x["adjusted"], x["projected"]), reverse=True)
    
#     result = {
#         "lineup": chosen,
#         "bench": bench[:15],  # Top 15 bench players
#         "debug_info": {
#             "total_candidates": len(candidates),
#             "lineup_filled": len([p for p in chosen if p.get("player")]),
#             "bench_size": len(bench),
#             "projection_matches": len([c for c in candidates if c["projected"] > 0])
#         }
#     }
    
#     # Apply team corrections to final result
#     return validate_team_data(result)

# Create the core optimization logic as a separate function
def _choose_optimal_lineup_core(
    lineup_slots: List[str],
    roster: Any,
    projections: Any,
    histories: Any,
) -> Dict[str, Any]:
    """Core lineup optimization logic (shared by tool and direct versions)."""
    
    # Parse all input data with robust error handling
    roster_data = _parse_roster_data(roster)
    projections_data = _parse_projections_data(projections)
    histories_data = _parse_histories_data(histories)
    
    print(f"Parsed {len(roster_data.get('players', []))} roster players")
    print(f"Parsed {len(projections_data)} projection position groups")
    print(f"Parsed {len(histories_data)} player histories")
    
    # Build projection lookup by normalized name
    proj_index: Dict[str, Dict[str, Any]] = {}
    
    for pos, rows in projections_data.items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = row.get("name", "")
            if name:
                # Try multiple keys for matching
                normalized_name = _normalize_player_name(name)
                position = row.get("position", pos).upper()
                
                # Store with multiple possible keys for matching
                proj_index[normalized_name] = row
                proj_index[f"{normalized_name}_{position}"] = row
                
    print(f"Built projection index with {len(proj_index)} entries")
    
    # Build candidates from roster players
    candidates: List[Candidate] = []
    
    for player in roster_data.get("players", []):
        name = player.get("name", "")
        if not name:
            continue
            
        pos = player.get("position", "").upper()
        if pos not in ("QB", "RB", "WR", "TE", "K", "DST", "DEF"):
            print(f"Skipping {name} - unsupported position: {pos}")
            continue
        
        # Normalize DST/DEF
        if pos == "DEF":
            pos = "DST"
        
        # Look up projection
        normalized_name = _normalize_player_name(name)
        proj = (proj_index.get(normalized_name) or 
                proj_index.get(f"{normalized_name}_{pos}") or
                {})
        
        projected = 0.0
        if proj:
            # Try multiple projection field names
            projected = (proj.get("projected") or 
                        proj.get("projection") or 
                        proj.get("points") or 
                        proj.get("fantasy_points") or 0.0)
            try:
                projected = float(projected)
            except (ValueError, TypeError):
                projected = 0.0
        
        team = proj.get("team", player.get("team", ""))
        opp = proj.get("opp", proj.get("opponent", ""))
        
        # Get history data
        hist = histories_data.get(name, {})
        recent4 = hist.get("recent4_avg", 0.0)
        vs_opp = hist.get("vs_opp_avg", None)
        
        # Calculate adjusted score
        adj = _adjusted_score(projected, recent4, vs_opp)
        
        candidate = Candidate(
            name=name,
            position=pos,
            team=team,
            opp=opp,
            projected=projected,
            recent4_avg=recent4,
            vs_opp_avg=vs_opp,
            adjusted=adj
        )
        candidates.append(candidate)
        
        if projected > 0:
            print(f"Added candidate: {name} ({pos}) - Proj: {projected}, Adj: {adj}")
    
    print(f"Built {len(candidates)} candidates")
    
    if not candidates:
        return {
            "lineup": [{"slot": slot, "player": None, "error": "No valid candidates"} 
                      for slot in _slot_order(lineup_slots)],
            "bench": [],
            "debug_info": {
                "error": "No valid candidates found",
                "roster_players": len(roster_data.get("players", [])),
                "projections_available": len(proj_index),
                "histories_available": len(histories_data)
            }
        }
    
    # Greedy lineup selection
    chosen: List[Dict[str, Any]] = []
    used_names: set[str] = set()
    
    for slot in _slot_order(lineup_slots):
        # Find candidates that fit this slot and aren't used
        fitting = [c for c in candidates 
                  if _fits(slot, c["position"]) and c["name"] not in used_names]
        
        if not fitting:
            chosen.append({
                "slot": slot,
                "player": None,
                "error": f"No available players for {slot}"
            })
            continue
        
        # Sort by adjusted score, then projected score
        fitting.sort(key=lambda x: (x["adjusted"], x["projected"]), reverse=True)
        pick = fitting[0]
        used_names.add(pick["name"])
        
        chosen.append({
            "slot": slot,
            "player": pick["name"],
            "team": pick["team"],
            "position": pick["position"],
            "projected": pick["projected"],
            "adjusted": pick["adjusted"],
            "opp": pick["opp"],
        })
        
        print(f"Selected for {slot}: {pick['name']} (adj: {pick['adjusted']})")
    
    # Build bench (remaining players, sorted by adjusted score)
    bench = [c for c in candidates if c["name"] not in used_names]
    bench.sort(key=lambda x: (x["adjusted"], x["projected"]), reverse=True)
    
    return {
        "lineup": chosen,
        "bench": bench[:15],  # Top 15 bench players
        "debug_info": {
            "total_candidates": len(candidates),
            "lineup_filled": len([p for p in chosen if p.get("player")]),
            "bench_size": len(bench),
            "projection_matches": len([c for c in candidates if c["projected"] > 0])
        }
    }

# Update the tool to use the core function
@tool
def choose_optimal_lineup(
    lineup_slots: List[str],
    roster: Any,
    projections: Any,
    histories: Any,
) -> Dict[str, Any]:
    """Pick the optimal lineup given slots, roster, projections and history.

    Args:
      lineup_slots: e.g. ["QB","RB","RB","WR","WR","TE","FLEX","K","DST"]
      roster: TeamRoster object or JSON string from get_team_roster
      projections: dict or JSON string from get_weekly_projections()
      histories: dict or JSON string mapping player name -> history dict

    Returns:
      dict with "lineup", "bench", and "debug_info"
    """
    return _choose_optimal_lineup_core(lineup_slots, roster, projections, histories)

# Direct optimization function (no tool decorator)
def optimize_lineup_direct(
    lineup_slots: List[str],
    roster_players: List[Dict[str, Any]],
    projections_data: Dict[str, List[Dict[str, Any]]],
    histories_data: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Direct optimization function that can be called from runtime without tool overhead."""
    
    return _choose_optimal_lineup_core(
        lineup_slots=lineup_slots,
        roster={"players": roster_players},
        projections=projections_data,
        histories=histories_data
    )