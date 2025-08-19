#!/usr/bin/env python3
import re
import json
import pandas as pd

# === Config ===
PROJECTIONS_YEAR = 2025
STATS_YEAR = 2024
POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"]

PROJ_URL = "https://www.fantasypros.com/nfl/projections/{}.php?week=draft&export=xls"
STATS_URL = "https://www.fantasypros.com/nfl/stats/{}.php?export=xls"

# NFL team abbreviations list
nfl_teams = [
    "ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB","HOU","IND",
    "JAX","JAC","KC","LV","LAC","LAR","MIA","MIN","NE","NO","NYG","NYJ",
    "PHI","PIT","SF","SEA","TB","TEN","WAS"
]
TEAM_PATTERN = r"(?:%s)" % "|".join(map(re.escape, nfl_teams))

def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten multi-index headers into single strings and tidy 'Unnamed' prefixes."""
    if isinstance(df.columns, pd.MultiIndex):
        new_cols = []
        for col in df.columns.values:
            parts = [str(c) for c in col if c and str(c).lower() != "nan"]
            if parts and parts[0].lower().startswith("unnamed"):
                parts = parts[1:]
            new_cols.append("_".join(parts) if len(parts) > 1 else (parts[0] if parts else ""))
        df.columns = [c.strip() for c in new_cols]
    else:
        df.columns = [str(c).strip() for c in df.columns]
    return df

def clean_player_name(text: str) -> str:
    """
    Remove team codes in forms like:
      'Name (TEAM)'  or  'Name TEAM' (trailing token)
    """
    s = str(text).strip()
    # 'Name (TEAM)'
    m = re.match(fr"^(.*?)\s+\(({TEAM_PATTERN})\)$", s)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    # 'Name TEAM' (TEAM at end)
    m = re.match(fr"^(.*?)[\s]+({TEAM_PATTERN})$", s)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    # fallback: remove any stray standalone team tokens in parens or brackets at end
    s = re.sub(fr"\s*[\(\[]({TEAM_PATTERN})[\)\]]\s*$", "", s)
    s = re.sub(fr"\s+({TEAM_PATTERN})\s*$", "", s)
    return re.sub(r"\s+", " ", s).strip()

def read_table(url: str, pos: str) -> pd.DataFrame | None:
    dfs = pd.read_html(url)
    if not dfs:
        print(f"⚠️ No table found for {pos} at {url}")
        return None
    df = dfs[0].fillna("")
    return flatten_columns(df)

def normalize_player_column(df: pd.DataFrame, pos: str) -> pd.DataFrame | None:
    # Find the player column dynamically
    player_col = next((c for c in df.columns if "Player" in str(c)), None)
    if not player_col:
        print(f"⚠️ No Player column for {pos}. Columns: {df.columns.tolist()}")
        return None
    if player_col != "Player":
        df = df.rename(columns={player_col: "Player"})
    df["Player"] = df["Player"].apply(clean_player_name)
    return df

def scrape_block(url_tmpl: str, out_year: int, pos: str) -> list[dict]:
    url = url_tmpl.format(pos.lower())
    print(f"Scraping {pos}: {url}")
    df = read_table(url, pos)
    if df is None:
        return []
    df = normalize_player_column(df, pos)
    if df is None:
        return []
    return df.to_dict(orient="records")

def main():
    for pos in POSITIONS:
        # Projections -> 2025_{pos}.json
        proj_records = scrape_block(PROJ_URL, PROJECTIONS_YEAR, pos)
        with open(f"{PROJECTIONS_YEAR}_{pos}.json", "w") as f:
            json.dump(proj_records, f, indent=2)
        print(f"✅ {pos}: wrote {len(proj_records)} rows to {PROJECTIONS_YEAR}_{pos}.json")

        # Last season stats -> 2024_{pos}.json
        stats_records = scrape_block(STATS_YEAR and STATS_URL, STATS_YEAR, pos)
        with open(f"{STATS_YEAR}_{pos}.json", "w") as f:
            json.dump(stats_records, f, indent=2)
        print(f"📊 {pos}: wrote {len(stats_records)} rows to {STATS_YEAR}_{pos}.json")

if __name__ == "__main__":
    main()
