#!/usr/bin/env python3
import os
import sys
import json
import argparse
from decimal import Decimal
import requests
import boto3
from boto3.dynamodb.conditions import Attr

# ---- Configuration ----
STATE_FILE = os.getenv("DRAFT_STATE_FILE", "draft_state.json")
TABLE_NAME = os.getenv("DDB_TABLE_NAME", "2025-2026-fantasy-football-player-data")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
LAMBDA_API_URL = os.getenv("LAMBDA_API_URL")  # e.g., https://abc123.execute-api.us-west-2.amazonaws.com/prod

# Your league’s starting requirements + bench
STARTING_REQUIREMENTS = {
    "QB": 2,
    "RB": 2,
    "WR": 2,
    "TE": 1,
    "DEF": 1,
    "K": 1,
    # FLEX is special: can be filled by RB/WR/TE
    "FLEX": 1,
}
BENCH_SPOTS = 8

FLEX_ELIGIBLE = {"RB", "WR", "TE"}

# ---- DynamoDB setup ----
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
table = dynamodb.Table(TABLE_NAME)

# ---- State helpers ----
def load_state():
    if not os.path.exists(STATE_FILE):
        return {"drafted": [], "my_roster": []}
    with open(STATE_FILE, "r") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def reset_state():
    save_state({"drafted": [], "my_roster": []})

# ---- DynamoDB lookups ----
def _decimal_to_native(v):
    if isinstance(v, list):
        return [_decimal_to_native(x) for x in v]
    if isinstance(v, dict):
        return {k: _decimal_to_native(x) for k, x in v.items()}
    if isinstance(v, Decimal):
        # keep integers as int when possible
        return int(v) if v % 1 == 0 else float(v)
    return v

def resolve_player_by_name(name: str, season: int | None = None):
    """
    Resolve a player by display name (case-insensitive).
    We pull one representative item (any week) for that player_id.
    """
    # Scan with case-insensitive match using lower() mirror (DynamoDB has no lower fn),
    # so we match exact case-insensitive by filtering on equality after pulling candidates.
    # To narrow results, filter on season if provided.
    fe = Attr("player_display_name").exists()
    if season is not None:
        fe = fe & Attr("season").eq(season)

    # Pull in chunks (pagination)
    last_evaluated_key = None
    candidates = []
    target_lower = name.strip().lower()
    while True:
        kwargs = {"FilterExpression": fe, "ProjectionExpression": "player_id, player_display_name, position, team"}
        if last_evaluated_key:
            kwargs["ExclusiveStartKey"] = last_evaluated_key
        resp = table.scan(**kwargs)
        items = resp.get("Items", [])
        for it in items:
            if str(it.get("player_display_name", "")).strip().lower() == target_lower:
                candidates.append(it)
        last_evaluated_key = resp.get("LastEvaluatedKey")
        if not last_evaluated_key:
            break

    if not candidates:
        # Try a contains-style search as a fallback (best-effort)
        last_evaluated_key = None
        while True:
            kwargs = {"FilterExpression": fe, "ProjectionExpression": "player_id, player_display_name, position, team"}
            if last_evaluated_key:
                kwargs["ExclusiveStartKey"] = last_evaluated_key
            resp = table.scan(**kwargs)
            items = resp.get("Items", [])
            for it in items:
                disp = str(it.get("player_display_name", ""))
                if target_lower in disp.lower():
                    candidates.append(it)
            last_evaluated_key = resp.get("LastEvaluatedKey")
            if not last_evaluated_key:
                break

    if not candidates:
        raise ValueError(f"Player '{name}' not found in DynamoDB.")

    # Deduplicate by player_id, prefer entries that have position/team populated
    by_id = {}
    for it in candidates:
        pid = it.get("player_id")
        if not pid:
            continue
        if pid not in by_id:
            by_id[pid] = it
        else:
            # keep the one with more fields filled
            cur = by_id[pid]
            cur_score = (1 if cur.get("position") else 0) + (1 if cur.get("team") else 0)
            new_score = (1 if it.get("position") else 0) + (1 if it.get("team") else 0)
            if new_score > cur_score:
                by_id[pid] = it

    # If multiple IDs (e.g., same display name across seasons/teams), pick one deterministically
    best = sorted(by_id.values(), key=lambda x: (x.get("position") is not None, x.get("team") is not None), reverse=True)[0]
    return _decimal_to_native(best)

def resolve_player(name_or_id: str, season: int | None = None):
    """Resolve by ID (fast) or by display name (scan)."""
    s = name_or_id.strip()
    if s.startswith("00-"):  # looks like an NFL GSIS id
        # Try to fetch one item for that player id (any)
        resp = table.scan(
            FilterExpression=Attr("player_id").eq(s),
            ProjectionExpression="player_id, player_display_name, position, team"
        )
        items = resp.get("Items", [])
        if not items:
            raise ValueError(f"Player ID '{s}' not found.")
        # Prefer items with position/team
        best = sorted(items, key=lambda x: (x.get("position") is not None, x.get("team") is not None), reverse=True)[0]
        return _decimal_to_native(best)
    else:
        return resolve_player_by_name(s, season=season)

# ---- Roster & needs ----
def count_positions(roster):
    counts = {"QB": 0, "RB": 0, "WR": 0, "TE": 0, "DEF": 0, "K": 0}
    for p in roster:
        pos = str(p.get("position", "")).upper()
        # normalize DST/DEF variations
        if pos in {"DST", "D/ST", "DEF"}:
            pos = "DEF"
        if pos in counts:
            counts[pos] += 1
    return counts

def compute_team_needs(my_roster):
    """
    Compute a dict of needed positions for starters, handling FLEX properly.
    We DO NOT include a key 'FLEX' because your Lambda tool filters by concrete positions.
    Instead, if FLEX slots remain, we add RB/WR/TE as 'needed' even when their base requirements are met.
    """
    counts = count_positions(my_roster)

    # Base needs for concrete positions (no FLEX)
    needs = {}
    for pos in ["QB", "RB", "WR", "TE", "DEF", "K"]:
        req = STARTING_REQUIREMENTS.get(pos, 0)
        have = counts.get(pos, 0)
        if have < req:
            needs[pos] = req - have

    # FLEX calculation
    req_flex = STARTING_REQUIREMENTS.get("FLEX", 0)
    # extras beyond base that can occupy FLEX
    extra_flex_filled = sum(max(0, counts[p] - STARTING_REQUIREMENTS.get(p, 0)) for p in FLEX_ELIGIBLE)
    flex_remaining = max(0, req_flex - min(extra_flex_filled, req_flex))

    if flex_remaining > 0:
        # mark RB/WR/TE as needed (at least 1) so the tool considers them
        for p in FLEX_ELIGIBLE:
            # If already needed > 0, leave it; otherwise set to 1 to signal eligibility
            if needs.get(p, 0) == 0:
                needs[p] = 1

    return needs

def bench_slots_used(my_roster):
    starters_total = sum(STARTING_REQUIREMENTS.values())  # includes FLEX
    return max(0, len(my_roster) - starters_total)

# ---- Commands ----
def cmd_reset(_args):
    reset_state()
    print("🔄 Draft state reset.")

def cmd_board(_args):
    state = load_state()
    print("📋 Drafted players:")
    for p in state["drafted"]:
        print(f" - {p['player_display_name']} ({p.get('position','?')} – {p.get('team','?')}) [{p['player_id']}]")
    print(f"Total drafted: {len(state['drafted'])}")

def cmd_roster(_args):
    state = load_state()
    print("🧑‍🤝‍🧑 My Roster:")
    for p in state["my_roster"]:
        print(f" - {p['player_display_name']} ({p.get('position','?')} – {p.get('team','?')}) [{p['player_id']}]")
    print(f"Bench spots used: {bench_slots_used(state['my_roster'])}/{BENCH_SPOTS}")
    needs = compute_team_needs(state["my_roster"])
    print(f"Remaining starter needs (incl. FLEX logic): {needs}")

def cmd_search(args):
    # Best-effort name search with contains matching
    needle = args.query.strip().lower()
    print(f"🔎 Searching for: {args.query}")
    fe = Attr("player_display_name").exists()
    last = None
    found = {}
    while True:
        kwargs = {"FilterExpression": fe, "ProjectionExpression": "player_id, player_display_name, position, team"}
        if last:
            kwargs["ExclusiveStartKey"] = last
        resp = table.scan(**kwargs)
        for it in resp.get("Items", []):
            name = str(it.get("player_display_name", ""))
            if needle in name.lower():
                pid = it.get("player_id")
                if pid not in found:
                    found[pid] = {
                        "player_id": pid,
                        "player_display_name": name,
                        "position": it.get("position"),
                        "team": it.get("team"),
                    }
        last = resp.get("LastEvaluatedKey")
        if not last:
            break
    if not found:
        print("No matches.")
        return
    for it in found.values():
        print(f" - {it['player_display_name']} ({it.get('position','?')} – {it.get('team','?')}) [{it['player_id']}]")
    print(f"Matches: {len(found)}")

def cmd_draft(args, mine=False):
    """
    Mark a player as drafted.
    If mine=True, also add to my_roster (i.e., it's your pick).
    Accepts a name or an ID.
    """
    state = load_state()
    try:
        pl = resolve_player(args.player)
    except Exception as e:
        print(f"❌ {e}")
        return

    record = {
        "player_id": pl.get("player_id"),
        "player_display_name": pl.get("player_display_name") or pl.get("player_name") or "Unknown",
        "position": normalize_pos(pl.get("position")),
        "team": pl.get("team"),
    }

    # If already in drafted, skip
    if any(p["player_id"] == record["player_id"] for p in state["drafted"]):
        print(f"⚠️ Already drafted: {record['player_display_name']} [{record['player_id']}]")
    else:
        state["drafted"].append(record)
        print(f"✅ Marked drafted: {record['player_display_name']} ({record['position']} – {record['team']}) [{record['player_id']}]")

    if mine:
        if any(p["player_id"] == record["player_id"] for p in state["my_roster"]):
            print("⚠️ Already on your roster.")
        else:
            # Enforce bench cap (soft-check; you can remove if you prefer)
            if bench_slots_used(state["my_roster"]) >= BENCH_SPOTS:
                print(f"⚠️ Bench is full ({BENCH_SPOTS}). Adding anyway as drafted, but not to roster.")
            else:
                state["my_roster"].append(record)
                print(f"🧩 Added to your roster.")

    save_state(state)

def cmd_mydraft(args):
    cmd_draft(args, mine=True)

def normalize_pos(pos):
    if not pos:
        return pos
    p = str(pos).upper()
    if p in {"DST", "D/ST", "DEF"}:
        return "DEF"
    return p

def cmd_pick(_args):
    if not LAMBDA_API_URL:
        print("❌ LAMBDA_API_URL not set.")
        sys.exit(1)

    state = load_state()
    needs = compute_team_needs(state["my_roster"])

    payload = {
        "team_needs": needs,
        "already_drafted": [p["player_id"] for p in state["drafted"]],
    }

    print(f"📡 Asking Agent → {LAMBDA_API_URL}")
    try:
        resp = requests.post(LAMBDA_API_URL, json=payload, timeout=30)
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return

    if resp.status_code != 200:
        print(f"❌ Agent error {resp.status_code}: {resp.text}")
        return

    try:
        data = resp.json()
    except Exception:
        print("❌ Invalid JSON from Agent.")
        print(resp.text)
        return

    print("🤖 Agent Response:")
    print(json.dumps(data, indent=2))

# ---- CLI ----
def build_parser():
    p = argparse.ArgumentParser(description="Fantasy Draft CLI (DynamoDB + Agent Lambda)")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("reset", help="Reset draft state")

    sub.add_parser("board", help="Show all drafted players")

    sub.add_parser("roster", help="Show your roster and remaining needs")

    s = sub.add_parser("search", help="Search players by (partial) display name")
    s.add_argument("query")

    d = sub.add_parser("draft", help="Mark a player (by name or ID) as drafted (not your pick)")
    d.add_argument("player")

    md = sub.add_parser("mydraft", help="Draft a player for YOUR roster (also marks as drafted)")
    md.add_argument("player")

    sub.add_parser("pick", help="Ask Agent for best available player given current state")

    return p

def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "reset":
        cmd_reset(args)
    elif args.command == "board":
        cmd_board(args)
    elif args.command == "roster":
        cmd_roster(args)
    elif args.command == "search":
        cmd_search(args)
    elif args.command == "draft":
        cmd_draft(args, mine=False)
    elif args.command == "mydraft":
        cmd_mydraft(args)
    elif args.command == "pick":
        cmd_pick(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
