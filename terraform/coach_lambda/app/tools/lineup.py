from typing import Dict, List, TypedDict, Literal, Any
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
    # Weighted blend; fallback gracefully
    p = projected if projected is not None else 0.0
    r = recent4 if recent4 is not None else p
    v = vs_opp if vs_opp is not None else r
    return round(0.70 * p + 0.20 * v + 0.10 * r, 4)

def _slot_order(lineup_slots: List[str]) -> List[str]:
    return [s.upper() for s in lineup_slots]

def _fits(slot: str, pos: str) -> bool:
    slot = slot.upper()
    pos = pos.upper()
    if slot in ("QB","RB","WR","TE","K","DST"):
        return slot == pos
    if slot == "FLEX":
        return pos in ("RB","WR","TE")
    if slot == "OP":  # Offensive Player slot
        return pos in ("QB","RB","WR","TE")
    return False

@tool
def choose_optimal_lineup(
    lineup_slots: List[str],
    roster: Dict[str, Any],
    projections: Dict[str, List[Dict[str, Any]]],
    histories: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Pick the optimal lineup given slots, roster, projections and history.

    Args:
      lineup_slots: e.g. ["QB","RB","RB","WR","WR","TE","FLEX","K","DST"]
      roster: TeamRoster object from get_team_roster
      projections: dict from get_weekly_projections()
      histories: dict mapping player name -> history dict from get_player_history_2024()

    Returns:
      dict with "lineup" and "bench"
    """
    # Build candidate map from roster players only
    proj_index: Dict[str, Dict[str, Any]] = {}
    for pos, rows in projections.items():
        for r in rows:
            # Key by display name; you may want to add a more robust name normalizer
            proj_index[(r["name"], r.get("position",""))] = r

    candidates: List[Candidate] = []
    for p in roster.get("players", []):
        name = p.get("name")
        pos = p.get("position", "").upper()
        # Skip players whose position isn't supported
        if pos not in ("QB","RB","WR","TE","K","DST"):
            continue
        proj = proj_index.get((name, pos))
        projected = float(proj.get("projected", 0.0)) if proj else 0.0
        team = proj.get("team", p.get("team","")) if proj else p.get("team","")
        opp = proj.get("opp","") if proj else ""
        hist = histories.get(name, {})
        recent4 = float(hist.get("recent4_avg", projected or 0.0))
        vs_opp = hist.get("vs_opp_avg", None)
        adj = _adjusted_score(projected, recent4, vs_opp)
        candidates.append(Candidate(
            name=name, position=pos, team=team, opp=opp,
            projected=projected, recent4_avg=recent4, vs_opp_avg=vs_opp,
            adjusted=adj
        ))

    # Greedy fill by slot, highest adjusted score that fits and not yet used
    chosen: List[Dict[str, Any]] = []
    used_names: set[str] = set()
    for slot in _slot_order(lineup_slots):
        fitting = [c for c in candidates if _fits(slot, c["position"]) and c["name"] not in used_names]
        fitting.sort(key=lambda x: (x["adjusted"], x["projected"]), reverse=True)
        if fitting:
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
        else:
            chosen.append({"slot": slot, "player": None})

    bench = [c for c in candidates if c["name"] not in used_names]
    bench.sort(key=lambda x: (x["adjusted"], x["projected"]), reverse=True)

    return {"lineup": chosen, "bench": bench[:15]}
