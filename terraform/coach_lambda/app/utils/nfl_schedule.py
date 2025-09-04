# nfl_2025_schedule.py
"""NFL 2025 Full Season Schedule - Matchups by Week

Generated from the schedule grid. Each week's matchups are provided as two-way mappings:
TEAM -> OPP and OPP -> TEAM. Use get_matchups_by_week(week) to retrieve the dict for a week.
"""

matchups_by_week = {
    1: {
        "DAL": "PHI",  # Thursday
        "KC": "LAC",   # Friday (Brazil)
        "LV": "NE",
        "PIT": "NYJ",
        "MIA": "IND",
        "ARI": "NO",
        "NYG": "WSH",
        "CAR": "JAX",
        "CIN": "CLE",
        "TB": "ATL",
        "TEN": "DEN",
        "SF": "SEA",
        "DET": "GB",
        "HOU": "LAR",
        "BAL": "BUF",
        "MIN": "CHI",  # Monday
    },
    
    2: {
        "WSH": "GB",   # Thursday
        "JAX": "CIN",
        "BUF": "NYJ",
        "NE": "MIA",
        "LAR": "TEN",
        "CLE": "BAL",
        "SF": "NO",
        "NYG": "DAL",
        "SEA": "PIT",
        "CHI": "DET",
        "DEN": "IND",
        "CAR": "ARI",
        "PHI": "KC",
        "ATL": "MIN",
        "TB": "HOU",   # Monday
        "LAC": "LV",   # Monday
    },
    
    3: {
        "MIA": "BUF",  # Thursday
        "PIT": "NE",
        "HOU": "JAX",
        "IND": "TEN",
        "CIN": "MIN",
        "NYJ": "TB",
        "GB": "CLE",
        "LV": "WSH",
        "ATL": "CAR",
        "LAR": "PHI",
        "NO": "SEA",
        "DEN": "LAC",
        "DAL": "CHI",
        "ARI": "SF",
        "KC": "NYG",
        "DET": "BAL",  # Monday
    },
    
    4: {
        "SEA": "ARI",  # Thursday
        "MIN": "PIT",  # Sunday (Dublin)
        "NO": "BUF",
        "WSH": "ATL",
        "LAC": "NYG",
        "TEN": "HOU",
        "CLE": "DET",
        "CAR": "NE",
        "PHI": "TB",
        "JAX": "SF",
        "IND": "LAR",
        "BAL": "KC",
        "CHI": "LV",
        "GB": "DAL",
        "NYJ": "MIA",  # Monday
        "CIN": "DEN",  # Monday
    },
    
    5: {
        # Bye: ATL, CHI, GB, PIT
        "SF": "LAR",   # Thursday
        "MIN": "CLE",  # Sunday (London)
        "NYG": "NO",
        "DEN": "PHI",
        "HOU": "BAL",
        "DAL": "NYJ",
        "LV": "IND",
        "MIA": "CAR",
        "TEN": "ARI",
        "TB": "SEA",
        "WSH": "LAC",
        "DET": "CIN",
        "NE": "BUF",
        "KC": "JAX",   # Monday
    },
    
    6: {
        # Bye: HOU, MIN
        "PHI": "NYG",  # Thursday
        "DEN": "NYJ",  # Sunday (London)
        "CLE": "PIT",
        "LAC": "MIA",
        "SF": "TB",
        "SEA": "JAX",
        "DAL": "CAR",
        "LAR": "BAL",
        "ARI": "IND",
        "TEN": "LV",
        "CIN": "GB",
        "NE": "NO",
        "DET": "KC",
        "CHI": "WSH",  # Monday
        "BUF": "ATL",  # Monday
    },
    
    7: {
        # Bye: BAL, BUF
        "PIT": "CIN",  # Thursday
        "LAR": "JAX",  # Sunday (London)
        "NE": "TEN",
        "MIA": "CLE",
        "LV": "KC",
        "CAR": "NYJ",
        "NO": "CHI",
        "PHI": "MIN",
        "NYG": "DEN",
        "IND": "LAC",
        "WSH": "DAL",
        "GB": "ARI",
        "ATL": "SF",
        "TB": "DET",   # Monday
        "HOU": "SEA",  # Monday
    },
    
    8: {
        # Bye: ARI, DET, JAX, LAR, LV, SEA
        "MIN": "LAC",  # Thursday
        "NYJ": "CIN",
        "CHI": "BAL",
        "MIA": "ATL",
        "CLE": "NE",
        "NYG": "PHI",
        "BUF": "CAR",
        "SF": "HOU",
        "TB": "NO",
        "DAL": "DEN",
        "TEN": "IND",
        "GB": "PIT",
        "WSH": "KC",   # Monday
    },
    
    9: {
        # Bye: CLE, NYJ, PHI, TB
        "BAL": "MIA",  # Thursday
        "IND": "PIT",
        "ATL": "NE",
        "CHI": "CIN",
        "LAC": "TEN",
        "SF": "NYG",
        "CAR": "GB",
        "DEN": "HOU",
        "MIN": "DET",
        "JAX": "LV",
        "NO": "LAR",
        "KC": "BUF",
        "SEA": "WSH",
        "ARI": "DAL",  # Monday
    },
    
    10: {
        # Bye: CIN, DAL, KC, TEN
        "LV": "DEN",   # Thursday
        "ATL": "IND",  # Sunday (Berlin)
        "JAX": "HOU",
        "BUF": "MIA",
        "NE": "TB",
        "CLE": "NYJ",
        "NYG": "CHI",
        "NO": "CAR",
        "BAL": "MIN",
        "ARI": "SEA",
        "LAR": "SF",
        "DET": "WSH",
        "PIT": "LAC",
        "PHI": "GB",   # Monday
    },
    
    11: {
        # Bye: IND, NO
        "NYJ": "NE",   # Thursday
        "WSH": "MIA",  # Sunday (Madrid)
        "TB": "BUF",
        "LAC": "JAX",
        "CIN": "PIT",
        "CAR": "ATL",
        "GB": "NYG",
        "CHI": "MIN",
        "HOU": "TEN",
        "SF": "ARI",
        "SEA": "LAR",
        "KC": "DEN",
        "BAL": "CLE",
        "DET": "PHI",
        "DAL": "LV",   # Monday
    },
    
    12: {
        # Bye: DEN, LAC, MIA, WSH
        "BUF": "HOU",  # Thursday
        "NE": "CIN",
        "PIT": "CHI",
        "IND": "KC",
        "NYJ": "BAL",
        "NYG": "DET",
        "SEA": "TEN",
        "MIN": "GB",
        "CLE": "LV",
        "JAX": "ARI",
        "ATL": "NO",
        "PHI": "DAL",
        "TB": "LAR",
        "CAR": "SF",   # Monday
    },
    
    13: {
        # Thanksgiving games
        "GB": "DET",   # Thursday (Thanksgiving)
        "KC": "DAL",   # Thursday (Thanksgiving)
        "CIN": "BAL",  # Thursday (Thanksgiving)
        "CHI": "PHI",  # Friday (Black Friday)
        "SF": "CLE",
        "JAX": "TEN",
        "HOU": "IND",
        "ARI": "TB",
        "NO": "MIA",
        "ATL": "NYJ",
        "LAR": "CAR",
        "MIN": "SEA",
        "BUF": "PIT",
        "LV": "LAC",
        "DEN": "WSH",
        "NYG": "NE",   # Monday
    },
    
    14: {
        # Bye: CAR, NE, NYG, SF
        "DAL": "DET",  # Thursday
        "IND": "JAX",
        "NO": "TB",
        "MIA": "NYJ",
        "PIT": "BAL",
        "SEA": "ATL",
        "TEN": "CLE",
        "WSH": "MIN",
        "CHI": "GB",
        "DEN": "LV",
        "LAR": "ARI",
        "CIN": "BUF",
        "HOU": "KC",
        "PHI": "LAC",  # Monday
    },
    
    15: {
        "ATL": "TB",   # Thursday
        "LAC": "KC",
        "BUF": "NE",
        "NYJ": "JAX",
        "BAL": "CIN",
        "LV": "PHI",
        "ARI": "HOU",
        "WSH": "NYG",
        "CLE": "CHI",
        "DET": "LAR",
        "TEN": "SF",
        "CAR": "NO",
        "GB": "DEN",
        "IND": "SEA",
        "MIN": "DAL",
        "MIA": "PIT",  # Monday
    },
    
    16: {
        "LAR": "SEA",  # Thursday
        "GB": "CHI",   # Saturday
        "PHI": "WSH",  # Saturday
        "KC": "TEN",
        "NYJ": "NO",
        "NE": "BAL",
        "BUF": "CLE",
        "TB": "CAR",
        "MIN": "NYG",
        "LAC": "DAL",
        "ATL": "ARI",
        "JAX": "DEN",
        "PIT": "DET",
        "LV": "HOU",
        "CIN": "MIA",
        "SF": "IND",   # Monday
    },
    
    17: {
        # Christmas games
        "DAL": "WSH",  # Thursday (Christmas - Netflix)
        "DET": "MIN",  # Thursday (Christmas - Netflix)
        "DEN": "KC",   # Thursday (Christmas - Prime Video)
        "SEA": "CAR",  # Saturday
        "ARI": "CIN",  # Saturday
        "BAL": "GB",   # Saturday
        "HOU": "LAC",  # Saturday
        "NYG": "LV",   # Saturday
        "PIT": "CLE",
        "JAX": "IND",
        "TB": "MIA",
        "NE": "NYJ",
        "NO": "TEN",
        "PHI": "BUF",
        "CHI": "SF",
        "LAR": "ATL",  # Monday
    },
    
    18: {
        # All games Sunday, Jan 4 (times TBD)
        "NYJ": "BUF",
        "KC": "LV",
        "BAL": "PIT",
        "CLE": "CIN",
        "MIA": "NE",
        "TEN": "JAX",
        "LAC": "DEN",
        "IND": "HOU",
        "DET": "CHI",
        "GB": "MIN",
        "NO": "ATL",
        "SEA": "SF",
        "WSH": "PHI",
        "DAL": "NYG",
        "CAR": "TB",
        "ARI": "LAR",
    }
}

# Bye weeks by team
bye_weeks = {
    "ARI": 8, "ATL": 5, "BAL": 7, "BUF": 7, "CAR": 14, "CHI": 5,
    "CIN": 10, "CLE": 9, "DAL": 10, "DEN": 12, "DET": 8, "GB": 5,
    "HOU": 6, "IND": 11, "JAX": 8, "KC": 10, "LAC": 12, "LAR": 8,
    "LV": 8, "MIA": 12, "MIN": 6, "NE": 14, "NO": 11, "NYG": 14,
    "NYJ": 9, "PHI": 9, "PIT": 5, "SEA": 8, "SF": 14, "TB": 9,
    "TEN": 10, "WSH": 12
}

def get_matchups_by_week(week: int) -> dict:
    if week not in matchups_by_week:
        return [f"No matchups found for week {week}"]
    
    week_matchups = matchups_by_week[week]
    formatted_matchups = []
    processed_teams = set()
    
    for away_team, home_team in week_matchups.items():
        # Skip if we've already processed this matchup from the other direction
        if away_team in processed_teams or home_team in processed_teams:
            continue
            
        formatted_matchup = f"HOME: {home_team} AWAY: {away_team}"
        formatted_matchups.append(formatted_matchup)
        
        # Mark both teams as processed to avoid duplicate matchups
        processed_teams.add(away_team)
        processed_teams.add(home_team)
    
    return formatted_matchups