# app/lineup.py
"""
Streamlined lineup optimization using unified player data.
"""

import json
from typing import Dict, List, Any, Optional
from strands import tool
from app.utils import fits_lineup_slot, normalize_player_name, calculate_adjusted_score
from app.player_data import load_roster_player_data, extract_2024_history, extract_2025_projections

def build_candidates(
    roster_players: List[Dict[str, Any]], 
    projections_data: Dict[str, Any],
    unified_data: Dict[str, Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Build candidate list with comprehensive scoring."""
    
    # Index projections by player name
    proj_index = {}
    for pos, players in projections_data.items():
        if isinstance(players, list):
            for player in players:
                if isinstance(player, dict):
                    name = player.get("name", "")
                    if name:
                        proj_index[normalize_player_name(name)] = player
    
    candidates = []
    
    for roster_player in roster_players:
        name = roster_player.get("name", "")
        position = roster_player.get("position", "").upper()
        
        if not name or position not in ("QB", "RB", "WR", "TE", "K", "DST"):
            continue
        
        # Get weekly projection
        norm_name = normalize_player_name(name)
        proj = proj_index.get(norm_name, {})
        weekly_proj = float(proj.get("projected", 0))
        
        # Get unified data
        player_data = unified_data.get(name, {})
        
        # Extract relevant metrics
        season_proj_total = 0
        recent_avg = 0
        
        if player_data:
            projections_2025 = extract_2025_projections(player_data)
            season_proj_total = projections_2025.get("MISC_FPTS", 0)
            
            history_2024 = extract_2024_history(player_data)
            recent_avg = history_2024.get("recent4_avg", 0)
        
        # Calculate scores
        season_proj_per_game = season_proj_total / 17 if season_proj_total > 0 else 0
        adjusted_score, confidence = calculate_adjusted_score(
            weekly_proj, season_proj_per_game, recent_avg
        )
        
        candidates.append({
            "name": name,
            "position": position,
            "team": roster_player.get("team", ""),
            "projected": weekly_proj,
            "season_total": season_proj_total,
            "recent_avg": recent_avg,
            "adjusted": adjusted_score,
            "confidence": confidence
        })
    
    return candidates

def optimize_lineup(
    lineup_slots: List[str],
    candidates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Optimize lineup using greedy selection."""
    
    chosen = []
    used_players = set()
    
    for slot in lineup_slots:
        slot = slot.upper().strip()
        
        # Find available candidates for this slot
        available = [
            c for c in candidates 
            if fits_lineup_slot(slot, c["position"]) and c["name"] not in used_players
        ]
        
        if not available:
            chosen.append({
                "slot": slot,
                "player": None,
                "error": f"No available players for {slot}"
            })
            continue
        
        # Sort by adjusted score * confidence, then adjusted score
        available.sort(key=lambda x: (x["adjusted"] * x["confidence"], x["adjusted"]), reverse=True)
        
        pick = available[0]
        used_players.add(pick["name"])
        
        chosen.append({
            "slot": slot,
            "player": pick["name"],
            "team": pick["team"],
            "position": pick["position"],
            "projected": pick["projected"],
            "adjusted": pick["adjusted"],
            "confidence": pick["confidence"]
        })
    
    # Remaining players for bench
    bench = [c for c in candidates if c["name"] not in used_players]
    bench.sort(key=lambda x: (x["adjusted"] * x["confidence"], x["adjusted"]), reverse=True)
    
    return {
        "lineup": chosen,
        "bench": bench[:10],
        "debug_info": {
            "total_candidates": len(candidates),
            "lineup_filled": len([p for p in chosen if p.get("player")]),
            "avg_confidence": round(sum(c["confidence"] for c in candidates) / len(candidates), 2) if candidates else 0
        }
    }

@tool
def choose_optimal_lineup(
    lineup_slots: List[str],
    roster: Any,
    projections: Any,
) -> Dict[str, Any]:
    """Choose optimal lineup with streamlined logic."""
    
    # Parse inputs
    if isinstance(roster, str):
        roster = json.loads(roster)
    if isinstance(projections, str):
        projections = json.loads(projections)
    
    roster_players = roster.get("players", [])
    
    # Load comprehensive data from unified table
    unified_data = load_roster_player_data(roster_players)
    
    # Build candidates with enhanced scoring
    candidates = build_candidates(roster_players, projections, unified_data)
    
    # Optimize lineup
    result = optimize_lineup(lineup_slots, candidates)
    
    return result

def optimize_lineup_direct(
    lineup_slots: List[str],
    roster_players: List[Dict[str, Any]],
    projections_data: Dict[str, Any],
    histories_data: Dict[str, Any] = None  # Not used
) -> Dict[str, Any]:
    """Direct optimization function for ultra-fast mode."""
    
    # Load unified data
    unified_data = load_roster_player_data(roster_players)
    
    # Build candidates
    candidates = build_candidates(roster_players, projections_data, unified_data)
    
    # Optimize and return
    return optimize_lineup(lineup_slots, candidates)