#!/usr/bin/env python3
"""
Unified NFL Data Loader for DynamoDB (fixed CSV handling)

1) Loads 2024 actuals (hvpkod GitHub) into DynamoDB.
2) Fetches 2025 season-long projections from FantasyPros CSV per position,
   then appends ALL projection stats to each matching player item.

Projection fields written (when present):
  projections_2025_ppr
  projections_2025_pass_att, projections_2025_pass_cmp, projections_2025_pass_yds,
  projections_2025_pass_tds, projections_2025_pass_int,
  projections_2025_rush_att, projections_2025_rush_yds, projections_2025_rush_tds,
  projections_2025_receptions, projections_2025_rec_yds, projections_2025_rec_tds,
  projections_2025_targets
Also:
  projections_last_updated, projection_sources

Run from the same directory as your existing scripts (populate-table.py).
"""

import argparse
import time
import re
import difflib
import os
import sys
import csv
from io import StringIO
from decimal import Decimal
from datetime import datetime
import requests
import boto3
from botocore.exceptions import ClientError
import importlib.util

# -----------------
# Config
# -----------------
TABLE_NAME = "2025-2026-fantasy-football-player-data"
REGION = "us-west-2"
FANTASYPROS_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# -----------------
# Import existing hvpkod loader dynamically (hyphenated filename)
# -----------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
POPULATE_PATH = os.path.join(SCRIPT_DIR, "populate-table.py")
if not os.path.exists(POPULATE_PATH):
    raise FileNotFoundError(f"populate-table.py not found at {POPULATE_PATH}")

spec_pop = importlib.util.spec_from_file_location("populate_table_mod", POPULATE_PATH)
populate_table_mod = importlib.util.module_from_spec(spec_pop)
spec_pop.loader.exec_module(populate_table_mod)  # noqa: E402
FantasyDataLoader = populate_table_mod.FantasyDataLoader

# -----------------
# Name normalization & matching
# -----------------
SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b", re.I)
NON_ALPHA_RE = re.compile(r"[^a-z ]")
MULTISPACE_RE = re.compile(r"\s+")
TEAM_IN_NAME_RE = re.compile(r"^(?P<name>.+?)\s+\((?P<team>[A-Z]{2,4})\)\s*$")

def normalize_name(name: str) -> str:
    if not name:
        return ""
    name = str(name)
    name = name.lower().strip()
    name = SUFFIX_RE.sub("", name)
    name = NON_ALPHA_RE.sub("", name)
    name = MULTISPACE_RE.sub(" ", name)
    return name.strip()

def best_match_player(proj, existing_players):
    """Return the best matching player item from DynamoDB.
    proj expects keys: name, position, team
    """
    proj_name = normalize_name(proj.get("name", ""))
    proj_pos = (proj.get("position") or "").upper()
    proj_team = (proj.get("team") or "").upper()

    exact = []
    for p in existing_players:
        if normalize_name(p.get("player_display_name")) == proj_name:
            exact.append(p)
    if exact:
        if proj_pos:
            filtered = [p for p in exact if (p.get("position", "").upper() == proj_pos)]
            exact = filtered or exact
        if proj_team:
            filtered = [p for p in exact if (p.get("team", "").upper() == proj_team)]
            exact = filtered or exact
        return exact[0]

    names = [normalize_name(p.get("player_display_name", "")) for p in existing_players]
    match = difflib.get_close_matches(proj_name, names, n=1, cutoff=0.86)
    if match:
        idx = names.index(match[0])
        return existing_players[idx]
    return None

# -----------------
# FantasyPros CSV fetcher (robust)
# -----------------
class FantasyProsCSV:
    """Fetch and parse FantasyPros season projections via CSV endpoints."""

    POS_URLS = {
        "qb": "https://www.fantasypros.com/nfl/projections/qb.php",
        "rb": "https://www.fantasypros.com/nfl/projections/rb.php",
        "wr": "https://www.fantasypros.com/nfl/projections/wr.php",
        "te": "https://www.fantasypros.com/nfl/projections/te.php",
        "k":  "https://www.fantasypros.com/nfl/projections/k.php",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": FANTASYPROS_UA,
            "Accept": "text/csv,application/octet-stream,application/vnd.ms-excel;q=0.9,*/*;q=0.8",
            "Referer": "https://www.fantasypros.com/",
            "Cache-Control": "no-cache",
        })

    def fetch(self, pos: str) -> str:
        base = self.POS_URLS[pos]
        params_list = [
            {"week": "draft", "scoring": "PPR", "csv": "1"},
            {"week": "draft", "csv": "1"},
            {"week": "draft", "scoring": "PPR", "export": "1"},
        ]
        last_err = None
        for params in params_list:
            try:
                r = self.session.get(base, params=params, timeout=30)
                r.raise_for_status()
                text = r.text
                # If site returned HTML (blocked) instead of CSV, try next variant
                head = text[:512].lower()
                if "<html" in head or "<!doctype" in head:
                    last_err = ValueError("Received HTML instead of CSV (likely blocked)")
                    continue
                return text
            except Exception as e:
                last_err = e
                continue
        raise last_err or RuntimeError("Unable to fetch CSV")

    @staticmethod
    def _colkey(label) -> str:
        # Guard against None/empty labels from malformed CSV rows
        if label is None:
            return ""
        s = str(label).strip().lower()
        s = s.replace("/", "_").replace(" ", "_")
        s = s.replace("passing_", "pass_").replace("rushing_", "rush_").replace("receiving_", "rec_")
        s = s.replace("yd", "yds")
        s = s.replace("td", "tds")
        return s

    def parse(self, csv_text: str):
        # Manual parse to avoid DictReader's None-key behavior with extra columns
        sio = StringIO(csv_text)
        reader = csv.reader(sio)
        rows = list(reader)
        if not rows or len(rows) < 2:
            return []
        headers = [self._colkey(h) for h in rows[0]]
        width = len(headers)
        out = []
        for raw in rows[1:]:
            if not any(raw):
                continue
            row_vals = (raw + [""] * (width - len(raw)))[:width]
            d = {headers[i]: row_vals[i] for i in range(width) if headers[i]}
            out.append(d)
        return out

# -----------------
# Projections updater
# -----------------
class ProjectionsUpdater:
    def __init__(self, table_name: str, region: str):
        self.dynamodb = boto3.resource("dynamodb", region_name=region)
        self.table = self.dynamodb.Table(table_name)
        self.fp = FantasyProsCSV()

    @staticmethod
    def _to_float(val):
        try:
            if val is None:
                return 0.0
            s = str(val).strip().replace(",", "")
            if s == "":
                return 0.0
            return float(s)
        except Exception:
            return 0.0

    @staticmethod
    def _to_int(val):
        return int(round(ProjectionsUpdater._to_float(val)))

    def _row_to_projection(self, pos: str, row: dict):
        """Map CSV row to our projection schema."""
        # Player & team
        name = row.get("player") or row.get("player_name") or row.get("name") or ""
        team = row.get("team", "")
        if not team and name:
            m = TEAM_IN_NAME_RE.match(name.strip())
            if m:
                name = m.group("name")
                team = m.group("team")

        proj = {
            "name": name.strip(),
            "team": (team or "").strip().upper(),
            "position": pos.upper(),
        }

        # PPR points (FPTS)
        fpts = self._to_float(row.get("fpts") or row.get("fantasy_points") or row.get("points"))
        if fpts > 0:
            proj["ppr_points"] = fpts

        # QB
        if pos == "qb":
            proj.update({
                "pass_att": self._to_int(row.get("pass_att") or row.get("att")),
                "pass_cmp": self._to_int(row.get("pass_cmp") or row.get("cmp")),
                "pass_yds": self._to_int(row.get("pass_yds") or row.get("yds")),
                "pass_tds": self._to_int(row.get("pass_tds") or row.get("tds")),
                "pass_int": self._to_int(row.get("pass_int") or row.get("int")),
                "rush_att": self._to_int(row.get("rush_att")),
                "rush_yds": self._to_int(row.get("rush_yds")),
                "rush_tds": self._to_int(row.get("rush_tds")),
            })

        # RB/WR/TE
        if pos in ("rb", "wr", "te"):
            proj.update({
                "rush_att": self._to_int(row.get("rush_att") or row.get("att")),
                "rush_yds": self._to_int(row.get("rush_yds") or row.get("yds")),
                "rush_tds": self._to_int(row.get("rush_tds") or row.get("tds")),
                "receptions": self._to_int(row.get("rec") or row.get("receptions")),
                "rec_yds": self._to_int(row.get("rec_yds")),
                "rec_tds": self._to_int(row.get("rec_tds")),
                "targets": self._to_int(row.get("tar") or row.get("targets")),
            })

        # K
        if pos == "k":
            proj.update({
                "field_goals": self._to_int(row.get("fg")),
                "field_goal_attempts": self._to_int(row.get("fga")),
                "extra_points": self._to_int(row.get("xpt") or row.get("xp")),
            })
        return proj

    def fetch_all(self):
        """Return list of normalized projection dicts across positions."""
        results = []
        per_pos_counts = {}
        for pos in ["qb", "rb", "wr", "te", "k"]:
            try:
                csv_text = self.fp.fetch(pos)
                rows = self.fp.parse(csv_text)
                per_pos_counts[pos] = len(rows)
                for row in rows:
                    proj = self._row_to_projection(pos, row)
                    if proj.get("name"):
                        results.append(proj)
                time.sleep(0.5)
            except Exception as e:
                print(f"⚠️  Failed fetching {pos}: {e}")
        print("✅ Per-position projection rows:", per_pos_counts)
        print(f"✅ Collected {len(results)} projections from FantasyPros CSV")
        return results

    def update_table(self, projections: list):
        """Attach projections to existing items."""
        # Load existing items
        scan_kwargs = {}
        all_items = []
        while True:
            resp = self.table.scan(**scan_kwargs)
            all_items.extend(resp.get("Items", []))
            if "LastEvaluatedKey" not in resp:
                break
            scan_kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        print(f"📦 Loaded {len(all_items)} existing items for matching")

        updated = 0
        not_found = 0
        for i, proj in enumerate(projections, 1):
            item = best_match_player(proj, all_items)
            if not item:
                not_found += 1
                if not_found <= 25:
                    print(f"⚠️  No match for projection: {proj.get('name')} ({proj.get('position')}/{proj.get('team')})")
                continue

            key = {"player_id": item["player_id"]}

            # Build update attributes
            update = {
                "projections_last_updated": datetime.now().isoformat(),
                "projection_sources": 1,
            }
            if proj.get("ppr_points") is not None and proj.get("ppr_points") > 0:
                update["projections_2025_ppr"] = Decimal(str(round(float(proj["ppr_points"]), 2)))

            # Passing
            for fld in ["pass_att", "pass_cmp", "pass_yds", "pass_tds", "pass_int"]:
                v = proj.get(fld)
                if v is not None and v > 0:
                    update[f"projections_2025_{fld}"] = int(v)

            # Rushing
            for fld in ["rush_att", "rush_yds", "rush_tds"]:
                v = proj.get(fld)
                if v is not None and v > 0:
                    update[f"projections_2025_{fld}"] = int(v)

            # Receiving
            for fld in ["receptions", "rec_yds", "rec_tds", "targets"]:
                v = proj.get(fld)
                if v is not None and v > 0:
                    update[f"projections_2025_{fld}"] = int(v)

            # Skip no-op updates
            if len(update) <= 2 and "projections_2025_ppr" not in update:
                continue

            try:
                expr = "SET " + ", ".join([f"{k} = :{k}" for k in update.keys()])
                values = {f":{k}": v for k, v in update.items()}
                self.table.update_item(Key=key, UpdateExpression=expr, ExpressionAttributeValues=values)
                updated += 1
            except ClientError as e:
                print(f"❌ Update error for {item.get('player_display_name')}: {e}")

            if i % 200 == 0:
                print(f"🔄 Processed {i}/{len(projections)} projections...")

        print(f"✅ Updated {updated} players with projections; ⚠️ Unmatched: {not_found}")
        return updated > 0

# -----------------
# Unified runner
# -----------------
def run_combined_load(table: str = TABLE_NAME, region: str = REGION, clear_first: bool = True):
    start = time.time()
    print("🚀 Starting unified NFL data load (2024 actuals + 2025 projections via CSV)...")

    # 1) Load 2024 season actuals via existing module
    hvp = FantasyDataLoader(table, region)
    if not hvp.run_full_refresh(season=2024, clear_first=clear_first):
        print("❌ Failed to load 2024 season data")
        return False

    # 2) Fetch & update projections
    updater = ProjectionsUpdater(table, region)
    proj = updater.fetch_all()
    if not proj:
        print("❌ No projections fetched")
        return False

    ok = updater.update_table(proj)
    if not ok:
        print("❌ No updates applied from projections")
        return False

    dur = time.time() - start
    print(f"🎉 Unified load complete in {dur:.1f}s")
    return True

def main():
    parser = argparse.ArgumentParser(description="Unified NFL Data Loader (2024 + 2025 projections via CSV)")
    parser.add_argument("--table", default=TABLE_NAME, help="DynamoDB table name")
    parser.add_argument("--region", default=REGION, help="AWS region")
    parser.add_argument("--no-clear", action="store_true", help="Don't clear table first")

    args = parser.parse_args()

    success = run_combined_load(
        table=args.table,
        region=args.region,
        clear_first=not args.no_clear,
    )

    if success:
        print("✅ Operation completed successfully!")
        exit(0)
    else:
        print("❌ Operation failed!")
        exit(1)

if __name__ == "__main__":
    main()
