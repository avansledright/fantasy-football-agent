# app/utils.py
"""
Consolidated utility functions for the fantasy football agent.
"""

import re
from typing import Literal

Positions = Literal["QB", "RB", "WR", "TE", "K", "DST"]



def normalize_player_name(name: str) -> str:
    """Normalize player names for consistent matching."""
    if not name:
        return ""
    
    # Remove common suffixes and normalize spacing
    name = re.sub(r"\s+Jr\.?$", "", name)
    name = re.sub(r"\s+Sr\.?$", "", name)
    name = name.replace("'", "'").replace(".", "").strip().lower()
    return re.sub(r"\s+", "_", name)

def normalize_position(position: str) -> str:
    """Normalize position abbreviations."""
    pos = position.upper().strip()
    if pos in ("DEF", "D/ST"):
        return "DST"
    return pos

def fits_lineup_slot(slot: str, position: str) -> bool:
    """Check if a position can fill a lineup slot."""
    slot = slot.upper().strip()
    pos = normalize_position(position)
    
    # Direct position matches
    if slot == pos:
        return True
    
    # Flex positions
    if slot == "FLEX":
        return pos in ("RB", "WR", "TE")
    
    # Offensive player slot  
    if slot == "OP":
        return pos in ("QB", "RB", "WR", "TE")
    
    return False

def get_injury_multiplier(injury_status: str) -> float:
    """Get scoring multiplier based on injury status."""
    injury_multipliers = {
        'Healthy': 1.0,      # No reduction
        'Questionable': 0.85, # 15% reduction
        'Doubtful': 0.5,     # 50% reduction  
        'Out': 0.1,          # 90% reduction (nearly unplayable)
        'IR': 0.05,          # 95% reduction (essentially bench-only)
        'PUP': 0.05,         # 95% reduction
        'Suspended': 0.1     # 90% reduction
    }
    return injury_multipliers.get(injury_status, 1.0)

def calculate_adjusted_score(
    weekly_proj: float,
    season_proj_per_game: float,
    recent_avg: float,
    injury_status: str = "Healthy",
    vs_opp_avg: float = None
) -> tuple[float, float]:
    """Calculate adjusted fantasy score with confidence metric and injury adjustment.
    
    Args:
        weekly_proj: Weekly projection
        season_proj_per_game: Season projection divided by games
        recent_avg: Recent games average
        injury_status: Player's current injury status
        vs_opp_avg: vs opponent average (optional)
    
    Returns:
        Tuple of (adjusted_score, confidence_score)
    """
    # Use fallbacks for missing data
    w = weekly_proj if weekly_proj > 0 else 0.0
    s = season_proj_per_game if season_proj_per_game > 0 else w
    r = recent_avg if recent_avg > 0 else s
    v = vs_opp_avg if vs_opp_avg and vs_opp_avg > 0 else r
    
    # If no data available
    if w == 0 and s == 0 and r == 0:
        return 0.0, 0.0
    
    # Weighted calculation: 60% weekly, 20% season consistency, 15% vs opp, 5% recent
    base_adjusted = (0.60 * w + 0.20 * s + 0.15 * v + 0.05 * r)
    
    # Apply injury multiplier
    injury_multiplier = get_injury_multiplier(injury_status)
    adjusted = base_adjusted * injury_multiplier
    
    # Calculate confidence based on data availability and injury status
    confidence = 0.0
    if w > 0: confidence += 0.5
    if s > 0: confidence += 0.3  
    if r > 0: confidence += 0.1
    if v and v > 0: confidence += 0.1
    
    # Reduce confidence for injured players
    if injury_status != "Healthy":
        confidence *= 0.7  # 30% confidence reduction for any injury
    
    return round(adjusted, 2), min(round(confidence, 2), 1.0)

def generate_player_id_candidates(player_name: str) -> list[str]:
    """Generate possible player IDs from a player name."""
    base_id = normalize_player_name(player_name)
    
    # Handle DST special case
    if "DST" in player_name or "D/ST" in player_name:
        team_abbrev = player_name.split()[0].lower()
        return [f"{team_abbrev}_dst", team_abbrev]
    
    # Current format (underscore + lowercase position)
    candidates = [
        f"{base_id}_qb",
        f"{base_id}_rb", 
        f"{base_id}_wr",
        f"{base_id}_te",
        f"{base_id}_k",
        base_id
    ]
    
    # ADD: DynamoDB format (proper case + # + uppercase position)
    proper_name = player_name.replace("'", "'").strip()
    candidates.extend([
        f"{proper_name}#QB",
        f"{proper_name}#RB",
        f"{proper_name}#WR", 
        f"{proper_name}#TE",
        f"{proper_name}#K",
        f"{proper_name}#DST"
    ])
    
    return candidates