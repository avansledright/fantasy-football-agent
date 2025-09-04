import re
import time
from typing import Dict, List, Literal, TypedDict
import requests
from bs4 import BeautifulSoup

from strands import tool

Positions = Literal["QB", "RB", "WR", "TE", "K", "DST"]

class ProjectionRow(TypedDict):
    name: str
    team: str
    opp: str
    position: Positions
    projected: float

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FantasyAgent/1.0; +https://example.com/agent)"
}

FP_BASE = "https://www.fantasypros.com/nfl/projections"
FP_PATHS = {
    "QB": "qb.php",
    "RB": "rb.php",
    "WR": "wr.php",
    "TE": "te.php",
    "K":  "k.php",
    "DST":"dst.php",
}

def _fetch_projection_table(position: Positions, week: int) -> List[ProjectionRow]:
    url = f"{FP_BASE}/{FP_PATHS[position]}?week={week}"
    # Basic retry to be resilient
    for attempt in range(3):
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            break
        time.sleep(1 + attempt)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    if not table:
        return []

    # Find column indices dynamically
    thead = table.find("thead")
    headers = [th.get_text(strip=True) for th in thead.find_all("th")] if thead else []
    # FantasyPros commonly uses "Player" and "FPTS"
    col_idx = {name: i for i, name in enumerate(headers)}
    fpts_key = "FPTS" if "FPTS" in col_idx else next((h for h in headers if "FPTS" in h), None)

    rows: List[ProjectionRow] = []
    tbody = table.find("tbody")
    if not tbody:
        return rows

    for tr in tbody.find_all("tr"):
        tds = tr.find_all(["td", "th"])
        if not tds or len(tds) < 2:
            continue
        player_cell = tds[col_idx.get("Player", 0)]
        player_text = player_cell.get_text(" ", strip=True)

        # Examples: "Josh Allen (BUF)" or "Lions D/ST (DET)"
        m = re.match(r"(.+?)\s+\(([A-Z]{2,3})\)", player_text)
        if m:
            name, team = m.group(1), m.group(2)
        else:
            # Fallback: split by last space and parentheses
            name = re.sub(r"\s*\([^)]+\)$", "", player_text).strip()
            team = ""

        opp = ""
        if "Opp" in col_idx:
            opp = tds[col_idx["Opp"]].get_text(strip=True)
            # Normalize e.g., "@CLE" -> "CLE"
            opp = opp.lstrip("@")

        # Projected points
        projected_val = 0.0
        if fpts_key and fpts_key in col_idx:
            txt = tds[col_idx[fpts_key]].get_text(strip=True)
            try:
                projected_val = float(txt)
            except Exception:
                projected_val = 0.0

        rows.append(ProjectionRow(
            name=name,
            team=team,
            opp=opp,
            position=position,
            projected=projected_val
        ))
    return rows


@tool
def get_weekly_projections(week: int) -> Dict[str, List[ProjectionRow]]:
    """Fetch FantasyPros weekly projections for all positions needed.
    Args:
        week: integer week (1-18)
    Returns:
        dict with keys: QB, RB, WR, TE, K, DST -> list of ProjectionRow
    """
    data: Dict[str, List[ProjectionRow]] = {}
    for pos in ("QB", "RB", "WR", "TE", "K", "DST"):
        try:
            data[pos] = _fetch_projection_table(pos, week)
        except Exception:
            data[pos] = []
    return data


@tool  
def debug_projections(week: int) -> str:
    """Debug tool to see what projections data looks like."""
    
    # Import your actual projections function
    from app.tools.projections import get_weekly_projections
    
    try:
        result = get_weekly_projections(week)
        
        # Parse the result
        if isinstance(result, str):
            data = json.loads(result)
        else:
            data = result
            
        # Check specific players
        debug_info = {
            "total_positions": len(data) if isinstance(data, dict) else 0,
            "positions": list(data.keys()) if isinstance(data, dict) else [],
            "sample_players": {}
        }
        
        problem_players = ["DK Metcalf", "Sam Darnold", "Saquon Barkley", "Josh Jacobs"]
        
        for pos, players in data.items() if isinstance(data, dict) else []:
            for player in players:
                name = player.get("name", "")
                if name in problem_players:
                    debug_info["sample_players"][name] = {
                        "position": pos,
                        "team": player.get("team", ""),
                        "projected": player.get("projected", 0),
                        "full_data": player
                    }
        
        return f"Projections Debug for Week {week}:\n{json.dumps(debug_info, indent=2)}"
        
    except Exception as e:
        return f"Debug error: {str(e)}"

# Alternative: Check if your data source is using 2024 data
def check_data_source_year():
    """Check if projections are pulling from correct year."""
    print("🔍 CHECKING DATA SOURCE:")
    print("1. Is your projections API pulling 2025 data?")
    print("2. Are you using FantasyPros current week data?") 
    print("3. Check API endpoint URL for year parameters")
    print("4. Verify player movement updates in data source")

# Quick fix mapping for immediate use
QUICK_TEAM_FIXES = {
    "DK Metcalf": "PIT",
    "Sam Darnold": "SEA", 
    "Saquon Barkley": "PHI",
    "Josh Jacobs": "GB",
    "Stefon Diggs": "NE",
    "Keenan Allen": "CHI",
    "Calvin Ridley": "TEN",
}

def apply_quick_team_fixes(lineup_data):
    """Apply quick team fixes to lineup data."""
    if isinstance(lineup_data, dict):
        # Fix lineup
        for player in lineup_data.get("lineup", []):
            name = player.get("player", "")
            if name in QUICK_TEAM_FIXES:
                old_team = player.get("team", "")
                player["team"] = QUICK_TEAM_FIXES[name]
                print(f"Fixed {name}: {old_team} → {QUICK_TEAM_FIXES[name]}")
        
        # Fix bench
        for player in lineup_data.get("bench", []):
            name = player.get("name", player.get("player", ""))
            if name in QUICK_TEAM_FIXES:
                old_team = player.get("team", "")
                player["team"] = QUICK_TEAM_FIXES[name] 
                print(f"Fixed {name}: {old_team} → {QUICK_TEAM_FIXES[name]}")
    
    return lineup_data