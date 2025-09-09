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
        except Exception as e:
            print(f"Error fetching {pos} projections: {e}")
            data[pos] = []
    
    return data

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