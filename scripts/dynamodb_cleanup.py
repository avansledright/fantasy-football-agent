import boto3
from boto3.dynamodb.conditions import Attr

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("fantasy-football-players")
def normalize_team_name(player_name: str):
    # Remove DST, strip spaces, uppercase for abbreviation
    key = player_name.replace("DST", "").strip()

    # Try exact mapping first
    if key in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[key]
    # Try uppercase abbreviation
    upper_key = key.upper()
    if upper_key in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[upper_key]
    # Try title case for full names
    title_key = key.title()
    if title_key in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[title_key]

    return None  # Not found


def merge_dst_items(dry_run=True):
    # Scan for DST items (wrong pattern usually has like "TB DST")
    response = table.scan(
        FilterExpression=Attr("position").eq("DST")
    )
    items = response.get("Items", [])

    for item in items:
        player_id = item["player_id"]
        player_name = item.get("player_name", "")

        # Skip if it's already a "correct" one
        if "#" in player_id and not player_name.endswith("DST"):
            continue

        wrong_item = item
        current_stats = wrong_item.get("current_season_stats", {})

        # Normalize team name
        correct_name = normalize_team_name(player_name)
        if not correct_name:
            print(f"⚠️ No mapping for {player_name}, skipping...")
            continue

        if not correct_name:
            print(f"⚠️ No mapping for {player_name}, skipping...")
            continue

        correct_player_id = f"{correct_name}#DST"

        # Get the correct item
        correct_resp = table.get_item(Key={"player_id": correct_player_id})
        correct_item = correct_resp.get("Item")

        if not correct_item:
            print(f"⚠️ Correct item not found for {correct_player_id}")
            continue

        # Merge current_season_stats
        merged_stats = correct_item.get("current_season_stats", {})
        for season, weeks in current_stats.items():
            merged_stats.setdefault(season, {}).update(weeks)

        if dry_run:
            print(f"Would merge {player_id} → {correct_player_id}")
            print("Resulting current_season_stats:", merged_stats)
        else:
            table.update_item(
                Key={"player_id": correct_player_id},
                UpdateExpression="SET current_season_stats = :val",
                ExpressionAttributeValues={":val": merged_stats},
            )
            table.delete_item(Key={"player_id": player_id})
            print(f"✅ Merged and deleted {player_id}")


# Example team abbreviation map
TEAM_NAME_MAP = {
    # Abbreviations
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB":  "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC":  "Kansas City Chiefs",
    "LV":  "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE":  "New England Patriots",
    "NO":  "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SF":  "San Francisco 49ers",
    "SEA": "Seattle Seahawks",
    "TB":  "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",

    # Aliases / full names without #DST
    "Tampa Bay": "Tampa Bay Buccaneers",
    "New England": "New England Patriots",
    "Kansas City": "Kansas City Chiefs",
    "San Francisco": "San Francisco 49ers",
    "Los Angeles Rams": "Los Angeles Rams",
    "Los Angeles Chargers": "Los Angeles Chargers",
    "Las Vegas": "Las Vegas Raiders",
    "Washington": "Washington Commanders",
    "New York Giants": "New York Giants",
    "New York Jets": "New York Jets",
    "Miami": "Miami Dolphins",
    "Minnesota": "Minnesota Vikings",
    "Philadelphia": "Philadelphia Eagles",
    "Pittsburgh": "Pittsburgh Steelers",
    "Chicago": "Chicago Bears",
    "Cincinnati": "Cincinnati Bengals",
    "Baltimore": "Baltimore Ravens",
    "Detroit": "Detroit Lions",
    "Carolina": "Carolina Panthers",
    "Arizona": "Arizona Cardinals",
    "Atlanta": "Atlanta Falcons",
    "Cleveland": "Cleveland Browns",
    "Denver": "Denver Broncos",
    "Dallas": "Dallas Cowboys",
    "Houston": "Houston Texans",
    "Tennessee": "Tennessee Titans",
    "Green Bay": "Green Bay Packers",
    "New Orleans": "New Orleans Saints",
    "Jacksonville": "Jacksonville Jaguars",
    "New England Patriots DST": "New England Patriots",
    "Las Vegas Raiders DST": "Las Vegas Raiders",
    "JAC": "Jacksonville Jaguars",
    "JACKSONVILLE": "Jacksonville Jaguars",
    "JACKSONVILLE JAGUARS": "Jacksonville Jaguars",
    
    "CHI": "Chicago Bears",
    "CHICAGO": "Chicago Bears",
    "CHICAGO BEARS": "Chicago Bears",
    
    "PIT": "Pittsburgh Steelers",
    "PITTSBURGH": "Pittsburgh Steelers",
    "PITTSBURGH STEELERS": "Pittsburgh Steelers",
    
    "MIN": "Minnesota Vikings",
    "MINNESOTA": "Minnesota Vikings",
    "MINNESOTA VIKINGS": "Minnesota Vikings",
    
    "PHI": "Philadelphia Eagles",
    "PHILADELPHIA": "Philadelphia Eagles",
    "PHILADELPHIA EAGLES": "Philadelphia Eagles",
    
    "CIN": "Cincinnati Bengals",
    "CINCINNATI": "Cincinnati Bengals",
    "CINCINNATI BENGALS": "Cincinnati Bengals",
    
    "SEA": "Seattle Seahawks",
    "SEATTLE": "Seattle Seahawks",
    "SEATTLE SEAHAWKS": "Seattle Seahawks",
    
    "IND": "Indianapolis Colts",
    "INDIANAPOLIS": "Indianapolis Colts",
    "INDIANAPOLIS COLTS": "Indianapolis Colts",
    
    "CAR": "Carolina Panthers",
    "CAROLINA": "Carolina Panthers",
    "CAROLINA PANTHERS": "Carolina Panthers",
    
    "BAL": "Baltimore Ravens",
    "BALTIMORE": "Baltimore Ravens",
    "BALTIMORE RAVENS": "Baltimore Ravens",
    
    "ARI": "Arizona Cardinals",
    "ARIZONA": "Arizona Cardinals",
    "ARIZONA CARDINALS": "Arizona Cardinals",
    
    "DAL": "Dallas Cowboys",
    "DALLAS": "Dallas Cowboys",
    "DALLAS COWBOYS": "Dallas Cowboys",
    
    "BUF": "Buffalo Bills",
    "BUFFALO": "Buffalo Bills",
    "BUFFALO BILLS": "Buffalo Bills",
    
    "DET": "Detroit Lions",
    "DETROIT": "Detroit Lions",
    "DETROIT LIONS": "Detroit Lions",
    
    "SF": "San Francisco 49ers",
    "SAN FRANCISCO": "San Francisco 49ers",
    "SAN FRANCISCO 49ERS": "San Francisco 49ers",
    
    "ATL": "Atlanta Falcons",
    "ATLANTA": "Atlanta Falcons",
    "ATLANTA FALCONS": "Atlanta Falcons",
    
    "KC": "Kansas City Chiefs",
    "KANSAS CITY": "Kansas City Chiefs",
    "KANSAS CITY CHIEFS": "Kansas City Chiefs",
    
    "HOU": "Houston Texans",
    "TEXANS": "Houston Texans",
    "HOUSTON": "Houston Texans",
    "HOUSTON TEXANS": "Houston Texans",
    
    "NE": "New England Patriots",
    "NEW ENGLAND": "New England Patriots",
    "NEW ENGLAND PATRIOTS": "New England Patriots",
    
    "WAS": "Washington Commanders",
    "WASHINGTON": "Washington Commanders",
    "WASHINGTON COMMANDERS": "Washington Commanders",
    
    "MIA": "Miami Dolphins",
    "MIAMI": "Miami Dolphins",
    "MIAMI DOLPHINS": "Miami Dolphins",
    
    "LV": "Las Vegas Raiders",
    "LAS VEGAS": "Las Vegas Raiders",
    "LAS VEGAS RAIDERS": "Las Vegas Raiders",
    
    "LAR": "Los Angeles Rams",
    "LOS ANGELES RAMS": "Los Angeles Rams",
    
    "LAC": "Los Angeles Chargers",
    "LOS ANGELES CHARGERS": "Los Angeles Chargers",
}



if __name__ == "__main__":
    merge_dst_items(dry_run=False)
