#!/usr/bin/env python3
import pandas as pd
import json

# NFL team abbreviations
nfl_teams = [
    "ARI","ATL","BAL","BUF","CAR","CHI","CIN","CLE","DAL","DEN","DET","GB","HOU","IND",
    "JAX","JAC","KC","LV","LAC","LAR","MIA","MIN","NE","NO","NYG","NYJ",
    "PHI","PIT","SF","SEA","TB","TEN","WAS"
]

def remove_nfl_abbreviations(text: str) -> str:
    result = text
    for team in nfl_teams:
        result = result.replace(" " + team, "")
    return result.strip()

BASE_URL = "https://www.fantasypros.com/nfl/projections/{}.php?week=draft&export=xls"
POSITIONS = ["QB", "RB", "WR", "TE", "K", "DST"]

def scrape_position(pos: str):
    url = BASE_URL.format(pos.lower())
    print(f"Scraping {pos} from {url} ...")

    # Read the "export=xls" table directly
    df = pd.read_html(url)[0]
    df = df.fillna("")

    # Flatten multi-index headers
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join([str(c) for c in col if c and c != "nan"]).strip()
                      for col in df.columns.values]
    else:
        df.columns = [str(c).strip() for c in df.columns]

    # Find player column
    player_col = next((c for c in df.columns if "Player" in str(c)), None)
    if not player_col:
        print(f"⚠️ No Player column for {pos}. Columns are: {df.columns.tolist()}")
        return []

    # Normalize to "Player"
    df = df.rename(columns={player_col: "Player"})
    df["Player"] = df["Player"].apply(remove_nfl_abbreviations)

    return df.to_dict(orient="records")

def scrape_all_positions():
    for pos in POSITIONS:
        data = scrape_position(pos)
        fname = f"{pos}_projections.json"
        with open(fname, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ Saved {len(data)} records to {fname}")

if __name__ == "__main__":
    scrape_all_positions()
