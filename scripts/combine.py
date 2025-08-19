#!/usr/bin/env python3
import json
import re
from pathlib import Path
from collections import defaultdict

# Configuration
YEARS = ["2024", "2025"]
POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"]
INPUT_DIRS = {y: Path(y) for y in YEARS}  # expects 2024/ and 2025/ folders
OUTPUT_DIR = Path("combined")
OUTPUT_DIR.mkdir(exist_ok=True)

# ---- Helpers ----

def canonical_player(name: str) -> str:
    """Light normalization for player key (trim & collapse whitespace)."""
    return re.sub(r"\s+", " ", (name or "").strip())

def load_json(path: Path):
    with open(path, "r") as f:
        return json.load(f)

def find_file(folder: Path, year: str, pos: str) -> Path | None:
    candidates = [
        folder / f"{year}_{pos}.json",
        folder / f"{pos}.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None

def normalize_projection_fields(d: dict) -> dict:
    """Normalize 2025 projections field names to match 2024 actuals keys."""
    normalized = {}
    for k, v in d.items():
        if k.endswith("TDS"):
            k = k[:-3] + "TD"
        if k.endswith("INTS"):
            k = k[:-4] + "INT"
        normalized[k] = v
    return normalized

def merge_actuals_and_projections(actuals_list, proj_list, pos: str):
    """
    Merge by 'Player'. Keep:
      - "2024_actuals": original record from 2024 file
      - "2025_projection": normalized record from 2025 file
      - "POSITION": pos
    """
    merged: dict[str, dict] = defaultdict(dict)

    for rec in actuals_list or []:
        name = canonical_player(rec.get("Player", ""))
        if not name:
            continue
        merged[name]["Player"] = name
        merged[name]["POSITION"] = pos
        merged[name]["2024_actuals"] = rec

    for rec in proj_list or []:
        name = canonical_player(rec.get("Player", ""))
        if not name:
            continue
        merged[name]["Player"] = name
        merged[name]["POSITION"] = pos
        merged[name]["2025_projection"] = normalize_projection_fields(rec)

    # Stable-ish order: by 2024 rank if present, else by player name
    def sort_key(item):
        d = item[1]
        rank = None
        if "2024_actuals" in d:
            rank = d["2024_actuals"].get("Rank")
        return (0, rank) if isinstance(rank, (int, float)) else (1, d["Player"])

    return [v for _, v in sorted(merged.items(), key=sort_key)]

def process_position(pos: str):
    path_2024 = find_file(INPUT_DIRS["2024"], "2024", pos)
    path_2025 = find_file(INPUT_DIRS["2025"], "2025", pos)

    if not path_2024 and not path_2025:
        print(f"⚠️  No files found for position {pos}; skipping.")
        return

    actuals = load_json(path_2024) if path_2024 else []
    projections = load_json(path_2025) if path_2025 else []

    combined = merge_actuals_and_projections(actuals, projections, pos)

    out_path = OUTPUT_DIR / f"{pos}.json"
    with open(out_path, "w") as f:
        json.dump(combined, f, indent=2)
    print(f"✅ Wrote {out_path} (players: {len(combined)})")

def discover_positions() -> set[str]:
    patterns = [
        re.compile(r"^(20\d{2})_(QB|RB|WR|TE|K|DST)\.json$", re.IGNORECASE),
        re.compile(r"^(QB|RB|WR|TE|K|DST)\.json$", re.IGNORECASE),
    ]
    found = set()
    for year, folder in INPUT_DIRS.items():
        if not folder.exists():
            continue
        for p in folder.glob("*.json"):
            for pat in patterns:
                m = pat.match(p.name)
                if m:
                    pos = (m.group(2) if pat.groups >= 2 else m.group(1)).upper()
                    found.add(pos)
                    break
    return found or set(POSITIONS)

# ---- Main ----

if __name__ == "__main__":
    positions = sorted(discover_positions())
    if not positions:
        print("No position files found. Nothing to do.")
    else:
        print(f"📂 Positions to process: {', '.join(positions)}")
        for pos in positions:
            process_position(pos)
