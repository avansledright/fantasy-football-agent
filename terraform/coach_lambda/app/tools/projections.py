import re
import time
from typing import Dict, List, Literal, TypedDict
import requests
from bs4 import BeautifulSoup  # add to requirements

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
