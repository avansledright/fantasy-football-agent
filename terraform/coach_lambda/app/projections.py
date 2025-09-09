# app/projections.py
"""
Simplified external projections API calls.
"""

import re
import time
from typing import Dict, List, Any
import requests
from bs4 import BeautifulSoup
from strands import tool

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FantasyAgent/1.0; +https://example.com/agent)"
}

FP_BASE = "https://www.fantasypros.com/nfl/projections"
FP_PATHS = {
    "QB": "qb.php",
    "RB": "rb.php", 
    "WR": "wr.php",
    "TE": "te.php",
    "K": "k.php",
    "DST": "dst.php",
}

def _fetch_position_projections(position: str, week: int) -> List[Dict[str, Any]]:
    """Fetch projections for a single position."""
    url = f"{FP_BASE}/{FP_PATHS[position]}?week={week}"
    
    # Retry logic
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                break
            time.sleep(1 + attempt)
        except requests.RequestException:
            if attempt == 2:
                return []
            time.sleep(1 + attempt)
    else:
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    # Find headers
    thead = table.find("thead")
    headers = [th.get_text(strip=True) for th in thead.find_all("th")] if thead else []
    
    # Find FPTS column
    fpts_col = None
    for i, header in enumerate(headers):
        if "FPTS" in header:
            fpts_col = i
            break
    
    if fpts_col is None:
        return []

    rows = []
    tbody = table.find("tbody")
    if not tbody:
        return rows

    for tr in tbody.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if len(tds) <= fpts_col:
            continue
            
        # Parse player name and team
        player_cell = tds[0]
        player_text = player_cell.get_text(" ", strip=True)
        
        # Extract name and team from "(TEAM)" pattern
        match = re.match(r"(.+?)\s+\(([A-Z]{2,3})\)", player_text)
        if match:
            name, team = match.group(1), match.group(2)
        else:
            name = re.sub(r"\s*\([^)]+\)$", "", player_text).strip()
            team = ""
        
        # Get opponent
        opp = ""
        if len(headers) > 1 and "Opp" in headers:
            opp_col = headers.index("Opp")
            if len(tds) > opp_col:
                opp = tds[opp_col].get_text(strip=True).lstrip("@")
        
        # Get projected points
        projected = 0.0
        try:
            proj_text = tds[fpts_col].get_text(strip=True)
            projected = float(proj_text)
        except (ValueError, IndexError):
            projected = 0.0
        
        rows.append({
            "name": name,
            "team": team,
            "opp": opp,
            "position": position,
            "projected": projected
        })
    
    return rows

@tool
def get_roster_projections(week: int, roster_players: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch projections only for roster players to reduce API calls."""
    
    # Group roster players by position
    roster_by_position = {}
    for player in roster_players:
        pos = player.get("position", "").upper()
        name = player.get("name", "")
        if pos in FP_PATHS and name:
            if pos not in roster_by_position:
                roster_by_position[pos] = set()
            roster_by_position[pos].add(name.lower())
    
    # Only fetch for positions we have players for
    data = {}
    for pos in roster_by_position:
        try:
            all_projections = _fetch_position_projections(pos, week)
            # Filter to only roster players
            roster_projections = [
                p for p in all_projections 
                if p["name"].lower() in roster_by_position[pos]
            ]
            data[pos] = roster_projections
            print(f"Fetched {len(roster_projections)} {pos} projections for roster players")
            
            # If no projections found, create fallback using unified table data
            if len(roster_projections) == 0:
                print(f"No external projections found for {pos}, creating fallback...")
                fallback_projections = _create_fallback_projections(pos, roster_players, week)
                data[pos] = fallback_projections
                print(f"Created {len(fallback_projections)} fallback {pos} projections")
                
        except Exception as e:
            print(f"Error fetching {pos} projections: {e}")
            # Create fallback projections when API fails
            fallback_projections = _create_fallback_projections(pos, roster_players, week)
            data[pos] = fallback_projections
            print(f"Created {len(fallback_projections)} fallback {pos} projections due to API error")
    
    return data

def _create_fallback_projections(position: str, roster_players: List[Dict[str, Any]], week: int) -> List[Dict[str, Any]]:
    """Create fallback projections using unified table data when external API fails."""
    from app.player_data import get_players_batch, extract_2025_projections
    
    fallback_projections = []
    
    # Get players for this position
    position_players = [p for p in roster_players if p.get("position", "").upper() == position.upper()]
    
    if not position_players:
        return []
    
    # Get player IDs and batch load unified data
    player_ids = [p.get("player_id") for p in position_players if p.get("player_id")]
    
    if player_ids:
        unified_data = get_players_batch(player_ids)
        
        for player in position_players:
            player_id = player.get("player_id")
            player_name = player.get("name", "")
            team = player.get("team", "")
            
            if player_id in unified_data:
                player_data = unified_data[player_id]
                season_projections = extract_2025_projections(player_data)
                
                # Estimate weekly projection from season total
                season_total = season_projections.get("MISC_FPTS", 0)
                weekly_estimate = round(season_total / 17, 1) if season_total > 0 else 5.0
                
                # Add some variance based on position typical scoring
                position_adjustment = {
                    "QB": 1.2,    # QBs typically score higher
                    "RB": 1.0,
                    "WR": 1.0,
                    "TE": 0.9,    # TEs typically score lower
                    "K": 0.7,     # Kickers much lower
                    "DST": 0.8    # Defenses variable
                }.get(position.upper(), 1.0)
                
                weekly_estimate *= position_adjustment
                
                fallback_projections.append({
                    "name": player_name,
                    "team": team,
                    "opp": "",  # Could enhance this with matchup data
                    "position": position.upper(),
                    "projected": max(weekly_estimate, 3.0)  # Minimum 3 points
                })
                
                print(f"Fallback projection for {player_name}: {weekly_estimate} points (from {season_total} season)")
    
    return fallback_projections

@tool
def get_weekly_projections(week: int) -> Dict[str, List[Dict[str, Any]]]:
    """Fetch all weekly projections (use sparingly - makes many API calls)."""
    data = {}
    for pos in FP_PATHS:
        try:
            data[pos] = _fetch_position_projections(pos, week)
            print(f"Fetched {len(data[pos])} {pos} projections")
        except Exception as e:
            print(f"Error fetching {pos} projections: {e}")
            data[pos] = []
    
    return data