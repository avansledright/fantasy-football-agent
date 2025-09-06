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

{
    "week_1": [
        {"date": "2025-09-04", "time": "20:20", "away_team": "Dallas Cowboys", "home_team": "Philadelphia Eagles", "network": "NBC"},
        {"date": "2025-09-05", "time": "20:00", "away_team": "Kansas City Chiefs", "home_team": "Los Angeles Chargers", "location": "Sao Paulo", "network": "YouTube"},
        {"date": "2025-09-07", "time": "13:00", "away_team": "Tampa Bay Buccaneers", "home_team": "Atlanta Falcons", "network": "FOX"},
        {"date": "2025-09-07", "time": "13:00", "away_team": "Cincinnati Bengals", "home_team": "Cleveland Browns", "network": "FOX"},
        {"date": "2025-09-07", "time": "13:00", "away_team": "Miami Dolphins", "home_team": "Indianapolis Colts", "network": "CBS"},
        {"date": "2025-09-07", "time": "13:00", "away_team": "Carolina Panthers", "home_team": "Jacksonville Jaguars", "network": "FOX"},
        {"date": "2025-09-07", "time": "13:00", "away_team": "Las Vegas Raiders", "home_team": "New England Patriots", "network": "CBS"},
        {"date": "2025-09-07", "time": "13:00", "away_team": "Arizona Cardinals", "home_team": "New Orleans Saints", "network": "CBS"},
        {"date": "2025-09-07", "time": "13:00", "away_team": "Pittsburgh Steelers", "home_team": "New York Jets", "network": "CBS"},
        {"date": "2025-09-07", "time": "13:00", "away_team": "New York Giants", "home_team": "Washington Commanders", "network": "FOX"},
        {"date": "2025-09-07", "time": "16:05", "away_team": "Tennessee Titans", "home_team": "Denver Broncos", "network": "FOX"},
        {"date": "2025-09-07", "time": "16:05", "away_team": "San Francisco 49ers", "home_team": "Seattle Seahawks", "network": "FOX"},
        {"date": "2025-09-07", "time": "16:25", "away_team": "Detroit Lions", "home_team": "Green Bay Packers", "network": "CBS"},
        {"date": "2025-09-07", "time": "16:25", "away_team": "Houston Texans", "home_team": "Los Angeles Rams", "network": "CBS"},
        {"date": "2025-09-07", "time": "20:20", "away_team": "Baltimore Ravens", "home_team": "Buffalo Bills", "network": "NBC"},
        {"date": "2025-09-08", "time": "20:15", "away_team": "Minnesota Vikings", "home_team": "Chicago Bears", "network": "ABC/ESPN"}
    ],
    "week_2": [
        {"date": "2025-09-11", "time": "20:15", "away_team": "Washington Commanders", "home_team": "Green Bay Packers", "network": "Prime Video"},
        {"date": "2025-09-14", "time": "13:00", "away_team": "Cleveland Browns", "home_team": "Baltimore Ravens", "network": "CBS"},
        {"date": "2025-09-14", "time": "13:00", "away_team": "Jacksonville Jaguars", "home_team": "Cincinnati Bengals", "network": "CBS"},
        {"date": "2025-09-14", "time": "13:00", "away_team": "New York Giants", "home_team": "Dallas Cowboys", "network": "FOX"},
        {"date": "2025-09-14", "time": "13:00", "away_team": "Chicago Bears", "home_team": "Detroit Lions", "network": "FOX"},
        {"date": "2025-09-14", "time": "13:00", "away_team": "New England Patriots", "home_team": "Miami Dolphins", "network": "CBS"},
        {"date": "2025-09-14", "time": "13:00", "away_team": "San Francisco 49ers", "home_team": "New Orleans Saints", "network": "FOX"},
        {"date": "2025-09-14", "time": "13:00", "away_team": "Buffalo Bills", "home_team": "New York Jets", "network": "CBS"},
        {"date": "2025-09-14", "time": "13:00", "away_team": "Seattle Seahawks", "home_team": "Pittsburgh Steelers", "network": "FOX"},
        {"date": "2025-09-14", "time": "13:00", "away_team": "Los Angeles Rams", "home_team": "Tennessee Titans", "network": "CBS"},
        {"date": "2025-09-14", "time": "16:05", "away_team": "Carolina Panthers", "home_team": "Arizona Cardinals", "network": "CBS"},
        {"date": "2025-09-14", "time": "16:05", "away_team": "Denver Broncos", "home_team": "Indianapolis Colts", "network": "CBS"},
        {"date": "2025-09-14", "time": "16:25", "away_team": "Philadelphia Eagles", "home_team": "Kansas City Chiefs", "network": "FOX"},
        {"date": "2025-09-14", "time": "20:20", "away_team": "Atlanta Falcons", "home_team": "Minnesota Vikings", "network": "NBC"},
        {"date": "2025-09-15", "time": "19:00", "away_team": "Tampa Bay Buccaneers", "home_team": "Houston Texans", "network": "ABC"},
        {"date": "2025-09-15", "time": "22:00", "away_team": "Los Angeles Chargers", "home_team": "Las Vegas Raiders", "network": "ESPN"}
    ],
    "week_3": [
        {"date": "2025-09-18", "time": "20:15", "away_team": "Miami Dolphins", "home_team": "Buffalo Bills", "network": "Prime Video"},
        {"date": "2025-09-21", "time": "13:00", "away_team": "Atlanta Falcons", "home_team": "Carolina Panthers", "network": "FOX"},
        {"date": "2025-09-21", "time": "13:00", "away_team": "Green Bay Packers", "home_team": "Cleveland Browns", "network": "FOX"},
        {"date": "2025-09-21", "time": "13:00", "away_team": "Houston Texans", "home_team": "Jacksonville Jaguars", "network": "CBS"},
        {"date": "2025-09-21", "time": "13:00", "away_team": "Cincinnati Bengals", "home_team": "Minnesota Vikings", "network": "CBS"},
        {"date": "2025-09-21", "time": "13:00", "away_team": "Pittsburgh Steelers", "home_team": "New England Patriots", "network": "CBS"},
        {"date": "2025-09-21", "time": "13:00", "away_team": "Los Angeles Rams", "home_team": "Philadelphia Eagles", "network": "FOX"},
        {"date": "2025-09-21", "time": "13:00", "away_team": "New York Jets", "home_team": "Tampa Bay Buccaneers", "network": "FOX"},
        {"date": "2025-09-21", "time": "13:00", "away_team": "Indianapolis Colts", "home_team": "Tennessee Titans", "network": "CBS"},
        {"date": "2025-09-21", "time": "13:00", "away_team": "Las Vegas Raiders", "home_team": "Washington Commanders", "network": "FOX"},
        {"date": "2025-09-21", "time": "16:05", "away_team": "Denver Broncos", "home_team": "Los Angeles Chargers", "network": "CBS"},
        {"date": "2025-09-21", "time": "16:05", "away_team": "New Orleans Saints", "home_team": "Seattle Seahawks", "network": "CBS"},
        {"date": "2025-09-21", "time": "16:25", "away_team": "Dallas Cowboys", "home_team": "Chicago Bears", "network": "FOX"},
        {"date": "2025-09-21", "time": "16:25", "away_team": "Arizona Cardinals", "home_team": "San Francisco 49ers", "network": "FOX"},
        {"date": "2025-09-21", "time": "20:20", "away_team": "Kansas City Chiefs", "home_team": "New York Giants", "network": "NBC"},
        {"date": "2025-09-22", "time": "20:15", "away_team": "Detroit Lions", "home_team": "Baltimore Ravens", "network": "ESPN/ABC"}
    ],
    "week_4": [
        {"date": "2025-09-25", "time": "20:15", "away_team": "Seattle Seahawks", "home_team": "Arizona Cardinals", "network": "Prime Video"},
        {"date": "2025-09-28", "time": "09:30", "away_team": "Minnesota Vikings", "home_team": "Pittsburgh Steelers", "location": "Dublin", "network": "NFLN"},
        {"date": "2025-09-28", "time": "13:00", "away_team": "Washington Commanders", "home_team": "Atlanta Falcons", "network": "CBS"},
        {"date": "2025-09-28", "time": "13:00", "away_team": "New Orleans Saints", "home_team": "Buffalo Bills", "network": "CBS"},
        {"date": "2025-09-28", "time": "13:00", "away_team": "Cleveland Browns", "home_team": "Detroit Lions", "network": "FOX"},
        {"date": "2025-09-28", "time": "13:00", "away_team": "Tennessee Titans", "home_team": "Houston Texans", "network": "CBS"},
        {"date": "2025-09-28", "time": "13:00", "away_team": "Carolina Panthers", "home_team": "New England Patriots", "network": "FOX"},
        {"date": "2025-09-28", "time": "13:00", "away_team": "Los Angeles Chargers", "home_team": "New York Giants", "network": "CBS"},
        {"date": "2025-09-28", "time": "13:00", "away_team": "Philadelphia Eagles", "home_team": "Tampa Bay Buccaneers", "network": "FOX"},
        {"date": "2025-09-28", "time": "16:05", "away_team": "Indianapolis Colts", "home_team": "Los Angeles Rams", "network": "FOX"},
        {"date": "2025-09-28", "time": "16:05", "away_team": "Jacksonville Jaguars", "home_team": "San Francisco 49ers", "network": "FOX"},
        {"date": "2025-09-28", "time": "16:25", "away_team": "Baltimore Ravens", "home_team": "Kansas City Chiefs", "network": "CBS"},
        {"date": "2025-09-28", "time": "16:25", "away_team": "Chicago Bears", "home_team": "Las Vegas Raiders", "network": "CBS"},
        {"date": "2025-09-28", "time": "20:20", "away_team": "Green Bay Packers", "home_team": "Dallas Cowboys", "network": "NBC"},
        {"date": "2025-09-29", "time": "19:15", "away_team": "New York Jets", "home_team": "Miami Dolphins", "network": "ESPN"},
        {"date": "2025-09-29", "time": "20:15", "away_team": "Cincinnati Bengals", "home_team": "Denver Broncos", "network": "ABC"}
    ],
    "week_5": [
        {"date": "2025-10-02", "time": "20:15", "away_team": "San Francisco 49ers", "home_team": "Los Angeles Rams", "network": "Prime Video"},
        {"date": "2025-10-05", "time": "09:30", "away_team": "Minnesota Vikings", "home_team": "Cleveland Browns", "location": "Tottenham", "network": "NFLN"},
        {"date": "2025-10-05", "time": "13:00", "away_team": "Houston Texans", "home_team": "Baltimore Ravens", "network": "CBS"},
        {"date": "2025-10-05", "time": "13:00", "away_team": "Miami Dolphins", "home_team": "Carolina Panthers", "network": "FOX"},
        {"date": "2025-10-05", "time": "13:00", "away_team": "Las Vegas Raiders", "home_team": "Indianapolis Colts", "network": "FOX"},
        {"date": "2025-10-05", "time": "13:00", "away_team": "New York Giants", "home_team": "New Orleans Saints", "network": "CBS"},
        {"date": "2025-10-05", "time": "13:00", "away_team": "Dallas Cowboys", "home_team": "New York Jets", "network": "FOX"},
        {"date": "2025-10-05", "time": "13:00", "away_team": "Denver Broncos", "home_team": "Philadelphia Eagles", "network": "CBS"},
        {"date": "2025-10-05", "time": "16:05", "away_team": "Tennessee Titans", "home_team": "Arizona Cardinals", "network": "CBS"},
        {"date": "2025-10-05", "time": "16:05", "away_team": "Tampa Bay Buccaneers", "home_team": "Seattle Seahawks", "network": "CBS"},
        {"date": "2025-10-05", "time": "16:25", "away_team": "Detroit Lions", "home_team": "Cincinnati Bengals", "network": "FOX"},
        {"date": "2025-10-05", "time": "16:25", "away_team": "Washington Commanders", "home_team": "Los Angeles Chargers", "network": "FOX"},
        {"date": "2025-10-05", "time": "20:20", "away_team": "New England Patriots", "home_team": "Buffalo Bills", "network": "NBC"},
        {"date": "2025-10-06", "time": "20:15", "away_team": "Kansas City Chiefs", "home_team": "Jacksonville Jaguars", "network": "ESPN/ABC"}
    ],
    "week_6": [
        {"date": "2025-10-09", "time": "20:15", "away_team": "Philadelphia Eagles", "home_team": "New York Giants", "network": "Prime Video"},
        {"date": "2025-10-12", "time": "09:30", "away_team": "Denver Broncos", "home_team": "New York Jets", "location": "Tottenham", "network": "NFLN"},
        {"date": "2025-10-12", "time": "13:00", "away_team": "Los Angeles Rams", "home_team": "Baltimore Ravens", "network": "FOX"},
        {"date": "2025-10-12", "time": "13:00", "away_team": "Dallas Cowboys", "home_team": "Carolina Panthers", "network": "FOX"},
        {"date": "2025-10-12", "time": "13:00", "away_team": "Arizona Cardinals", "home_team": "Indianapolis Colts", "network": "FOX"},
        {"date": "2025-10-12", "time": "13:00", "away_team": "Seattle Seahawks", "home_team": "Jacksonville Jaguars", "network": "FOX"},
        {"date": "2025-10-12", "time": "13:00", "away_team": "Los Angeles Chargers", "home_team": "Miami Dolphins", "network": "CBS"},
        {"date": "2025-10-12", "time": "13:00", "away_team": "Cleveland Browns", "home_team": "Pittsburgh Steelers", "network": "CBS"},
        {"date": "2025-10-12", "time": "13:00", "away_team": "San Francisco 49ers", "home_team": "Tampa Bay Buccaneers", "network": "CBS"},
        {"date": "2025-10-12", "time": "16:05", "away_team": "Tennessee Titans", "home_team": "Las Vegas Raiders", "network": "FOX"},
        {"date": "2025-10-12", "time": "16:25", "away_team": "Cincinnati Bengals", "home_team": "Green Bay Packers", "network": "CBS"},
        {"date": "2025-10-12", "time": "16:25", "away_team": "New England Patriots", "home_team": "New Orleans Saints", "network": "CBS"},
        {"date": "2025-10-12", "time": "20:20", "away_team": "Detroit Lions", "home_team": "Kansas City Chiefs", "network": "NBC"},
        {"date": "2025-10-13", "time": "19:15", "away_team": "Buffalo Bills", "home_team": "Atlanta Falcons", "network": "ESPN"},
        {"date": "2025-10-13", "time": "20:15", "away_team": "Chicago Bears", "home_team": "Washington Commanders", "network": "ABC"}
    ],
    "week_7": [
        {"date": "2025-10-16", "time": "20:15", "away_team": "Pittsburgh Steelers", "home_team": "Cincinnati Bengals", "network": "Prime Video"},
        {"date": "2025-10-19", "time": "09:30", "away_team": "Los Angeles Rams", "home_team": "Jacksonville Jaguars", "location": "Wembley", "network": "NFLN"},
        {"date": "2025-10-19", "time": "13:00", "away_team": "New Orleans Saints", "home_team": "Chicago Bears", "network": "FOX"},
        {"date": "2025-10-19", "time": "13:00", "away_team": "Miami Dolphins", "home_team": "Cleveland Browns", "network": "CBS"},
        {"date": "2025-10-19", "time": "13:00", "away_team": "Las Vegas Raiders", "home_team": "Kansas City Chiefs", "network": "CBS"},
        {"date": "2025-10-19", "time": "13:00", "away_team": "Philadelphia Eagles", "home_team": "Minnesota Vikings", "network": "FOX"},
        {"date": "2025-10-19", "time": "13:00", "away_team": "Carolina Panthers", "home_team": "New York Jets", "network": "FOX"},
        {"date": "2025-10-19", "time": "13:00", "away_team": "New England Patriots", "home_team": "Tennessee Titans", "network": "CBS"},
        {"date": "2025-10-19", "time": "16:05", "away_team": "New York Giants", "home_team": "Denver Broncos", "network": "CBS"},
        {"date": "2025-10-19", "time": "16:05", "away_team": "Indianapolis Colts", "home_team": "Los Angeles Chargers", "network": "CBS"},
        {"date": "2025-10-19", "time": "16:25", "away_team": "Green Bay Packers", "home_team": "Arizona Cardinals", "network": "FOX"},
        {"date": "2025-10-19", "time": "16:25", "away_team": "Washington Commanders", "home_team": "Dallas Cowboys", "network": "FOX"},
        {"date": "2025-10-19", "time": "20:20", "away_team": "Atlanta Falcons", "home_team": "San Francisco 49ers", "network": "NBC"},
        {"date": "2025-10-20", "time": "19:00", "away_team": "Tampa Bay Buccaneers", "home_team": "Detroit Lions", "network": "ESPN/ABC"},
        {"date": "2025-10-20", "time": "22:00", "away_team": "Houston Texans", "home_team": "Seattle Seahawks", "network": "ESPN+"}
    ],
    "week_8": [
        {"date": "2025-10-23", "time": "20:15", "away_team": "Minnesota Vikings", "home_team": "Los Angeles Chargers", "network": "Prime Video"},
        {"date": "2025-10-26", "time": "13:00", "away_team": "Miami Dolphins", "home_team": "Atlanta Falcons", "network": "CBS"},
        {"date": "2025-10-26", "time": "13:00", "away_team": "Chicago Bears", "home_team": "Baltimore Ravens", "network": "CBS"},
        {"date": "2025-10-26", "time": "13:00", "away_team": "Buffalo Bills", "home_team": "Carolina Panthers", "network": "FOX"},
        {"date": "2025-10-26", "time": "13:00", "away_team": "New York Jets", "home_team": "Cincinnati Bengals", "network": "CBS"},
        {"date": "2025-10-26", "time": "13:00", "away_team": "San Francisco 49ers", "home_team": "Houston Texans", "network": "FOX"},
        {"date": "2025-10-26", "time": "13:00", "away_team": "Cleveland Browns", "home_team": "New England Patriots", "network": "FOX"},
        {"date": "2025-10-26", "time": "13:00", "away_team": "New York Giants", "home_team": "Philadelphia Eagles", "network": "FOX"},
        {"date": "2025-10-26", "time": "16:05", "away_team": "Tampa Bay Buccaneers", "home_team": "New Orleans Saints", "network": "FOX"},
        {"date": "2025-10-26", "time": "16:25", "away_team": "Dallas Cowboys", "home_team": "Denver Broncos", "network": "CBS"},
        {"date": "2025-10-26", "time": "16:25", "away_team": "Tennessee Titans", "home_team": "Indianapolis Colts", "network": "CBS"},
        {"date": "2025-10-26", "time": "20:20", "away_team": "Green Bay Packers", "home_team": "Pittsburgh Steelers", "network": "NBC"},
        {"date": "2025-10-27", "time": "20:15", "away_team": "Washington Commanders", "home_team": "Kansas City Chiefs", "network": "ESPN/ABC"}
    ],
    "week_9": [
        {"date": "2025-10-30", "time": "20:15", "away_team": "Baltimore Ravens", "home_team": "Miami Dolphins", "network": "Prime Video"},
        {"date": "2025-11-02", "time": "13:00", "away_team": "Chicago Bears", "home_team": "Cincinnati Bengals", "network": "CBS"},
        {"date": "2025-11-02", "time": "13:00", "away_team": "Minnesota Vikings", "home_team": "Detroit Lions", "network": "FOX"},
        {"date": "2025-11-02", "time": "13:00", "away_team": "Carolina Panthers", "home_team": "Green Bay Packers", "network": "FOX"},
        {"date": "2025-11-02", "time": "13:00", "away_team": "Denver Broncos", "home_team": "Houston Texans", "network": "FOX"},
        {"date": "2025-11-02", "time": "13:00", "away_team": "Atlanta Falcons", "home_team": "New England Patriots", "network": "CBS"},
        {"date": "2025-11-02", "time": "13:00", "away_team": "San Francisco 49ers", "home_team": "New York Giants", "network": "CBS"},
        {"date": "2025-11-02", "time": "13:00", "away_team": "Indianapolis Colts", "home_team": "Pittsburgh Steelers", "network": "CBS"},
        {"date": "2025-11-02", "time": "13:00", "away_team": "Los Angeles Chargers", "home_team": "Tennessee Titans", "network": "CBS"},
        {"date": "2025-11-02", "time": "16:05", "away_team": "New Orleans Saints", "home_team": "Los Angeles Rams", "network": "FOX"},
        {"date": "2025-11-02", "time": "16:05", "away_team": "Jacksonville Jaguars", "home_team": "Las Vegas Raiders", "network": "FOX"},
        {"date": "2025-11-02", "time": "16:25", "away_team": "Kansas City Chiefs", "home_team": "Buffalo Bills", "network": "CBS"},
        {"date": "2025-11-02", "time": "20:20", "away_team": "Seattle Seahawks", "home_team": "Washington Commanders", "network": "NBC"},
        {"date": "2025-11-03", "time": "20:15", "away_team": "Arizona Cardinals", "home_team": "Dallas Cowboys", "network": "ESPN/ABC"}
    ],
    "week_10": [
        {"date": "2025-11-06", "time": "20:15", "away_team": "Las Vegas Raiders", "home_team": "Denver Broncos", "network": "Prime Video"},
        {"date": "2025-11-09", "time": "09:30", "away_team": "Atlanta Falcons", "home_team": "Indianapolis Colts", "location": "Berlin", "network": "NFLN"},
        {"date": "2025-11-09", "time": "13:00", "away_team": "New Orleans Saints", "home_team": "Carolina Panthers", "network": "FOX"},
        {"date": "2025-11-09", "time": "13:00", "away_team": "New York Giants", "home_team": "Chicago Bears", "network": "FOX"},
        {"date": "2025-11-09", "time": "13:00", "away_team": "Jacksonville Jaguars", "home_team": "Houston Texans", "network": "CBS"},
        {"date": "2025-11-09", "time": "13:00", "away_team": "Buffalo Bills", "home_team": "Miami Dolphins", "network": "CBS"},
        {"date": "2025-11-09", "time": "13:00", "away_team": "Baltimore Ravens", "home_team": "Minnesota Vikings", "network": "FOX"},
        {"date": "2025-11-09", "time": "13:00", "away_team": "Cleveland Browns", "home_team": "New York Jets", "network": "CBS"},
        {"date": "2025-11-09", "time": "13:00", "away_team": "New England Patriots", "home_team": "Tampa Bay Buccaneers", "network": "CBS"},
        {"date": "2025-11-09", "time": "16:05", "away_team": "Arizona Cardinals", "home_team": "Seattle Seahawks", "network": "CBS"},
        {"date": "2025-11-09", "time": "16:25", "away_team": "Los Angeles Rams", "home_team": "San Francisco 49ers", "network": "FOX"},
        {"date": "2025-11-09", "time": "16:25", "away_team": "Detroit Lions", "home_team": "Washington Commanders", "network": "FOX"},
        {"date": "2025-11-09", "time": "20:20", "away_team": "Pittsburgh Steelers", "home_team": "Los Angeles Chargers", "network": "NBC"},
        {"date": "2025-11-10", "time": "20:15", "away_team": "Philadelphia Eagles", "home_team": "Green Bay Packers", "network": "ESPN/ABC"}
    ],
    "week_11": [
        {"date": "2025-11-13", "time": "20:15", "away_team": "New York Jets", "home_team": "New England Patriots", "network": "Prime Video"},
        {"date": "2025-11-16", "time": "09:30", "away_team": "Washington Commanders", "home_team": "Miami Dolphins", "location": "Madrid", "network": "NFLN"},
        {"date": "2025-11-16", "time": "13:00", "away_team": "Carolina Panthers", "home_team": "Atlanta Falcons", "network": "FOX"},
        {"date": "2025-11-16", "time": "13:00", "away_team": "Tampa Bay Buccaneers", "home_team": "Buffalo Bills", "network": "CBS"},
        {"date": "2025-11-16", "time": "13:00", "away_team": "Los Angeles Chargers", "home_team": "Jacksonville Jaguars", "network": "CBS"},
        {"date": "2025-11-16", "time": "13:00", "away_team": "Chicago Bears", "home_team": "Minnesota Vikings", "network": "FOX"},
        {"date": "2025-11-16", "time": "13:00", "away_team": "Green Bay Packers", "home_team": "New York Giants", "network": "FOX"},
        {"date": "2025-11-16", "time": "13:00", "away_team": "Cincinnati Bengals", "home_team": "Pittsburgh Steelers", "network": "CBS"},
        {"date": "2025-11-16", "time": "13:00", "away_team": "Houston Texans", "home_team": "Tennessee Titans", "network": "FOX"},
        {"date": "2025-11-16", "time": "16:05", "away_team": "San Francisco 49ers", "home_team": "Arizona Cardinals", "network": "FOX"},
        {"date": "2025-11-16", "time": "16:05", "away_team": "Seattle Seahawks", "home_team": "Los Angeles Rams", "network": "FOX"},
        {"date": "2025-11-16", "time": "16:25", "away_team": "Baltimore Ravens", "home_team": "Cleveland Browns", "network": "CBS"},
        {"date": "2025-11-16", "time": "16:25", "away_team": "Kansas City Chiefs", "home_team": "Denver Broncos", "network": "CBS"},
        {"date": "2025-11-16", "time": "20:20", "away_team": "Detroit Lions", "home_team": "Philadelphia Eagles", "network": "NBC"},
        {"date": "2025-11-17", "time": "20:15", "away_team": "Dallas Cowboys", "home_team": "Las Vegas Raiders", "network": "ESPN/ABC"}
    ],
    "week_12": [
        {"date": "2025-11-20", "time": "20:15", "away_team": "Buffalo Bills", "home_team": "Houston Texans", "network": "Prime Video"},
        {"date": "2025-11-23", "time": "13:00", "away_team": "New York Jets", "home_team": "Baltimore Ravens", "network": "CBS"},
        {"date": "2025-11-23", "time": "13:00", "away_team": "Pittsburgh Steelers", "home_team": "Chicago Bears", "network": "CBS"},
        {"date": "2025-11-23", "time": "13:00", "away_team": "New England Patriots", "home_team": "Cincinnati Bengals", "network": "CBS"},
        {"date": "2025-11-23", "time": "13:00", "away_team": "New York Giants", "home_team": "Detroit Lions", "network": "FOX"},
        {"date": "2025-11-23", "time": "13:00", "away_team": "Minnesota Vikings", "home_team": "Green Bay Packers", "network": "FOX"},
        {"date": "2025-11-23", "time": "13:00", "away_team": "Indianapolis Colts", "home_team": "Kansas City Chiefs", "network": "CBS"},
        {"date": "2025-11-23", "time": "13:00", "away_team": "Seattle Seahawks", "home_team": "Tennessee Titans", "network": "FOX"},
        {"date": "2025-11-23", "time": "16:05", "away_team": "Jacksonville Jaguars", "home_team": "Arizona Cardinals", "network": "CBS"},
        {"date": "2025-11-23", "time": "16:05", "away_team": "Cleveland Browns", "home_team": "Las Vegas Raiders", "network": "CBS"},
        {"date": "2025-11-23", "time": "16:25", "away_team": "Philadelphia Eagles", "home_team": "Dallas Cowboys", "network": "FOX"},
        {"date": "2025-11-23", "time": "16:25", "away_team": "Atlanta Falcons", "home_team": "New Orleans Saints", "network": "FOX"},
        {"date": "2025-11-23", "time": "20:20", "away_team": "Tampa Bay Buccaneers", "home_team": "Los Angeles Rams", "network": "NBC"},
        {"date": "2025-11-24", "time": "20:15", "away_team": "Carolina Panthers", "home_team": "San Francisco 49ers", "network": "ESPN"}
    ],
    "week_13": [
        {"date": "2025-11-27", "time": "13:00", "away_team": "Green Bay Packers", "home_team": "Detroit Lions", "network": "FOX"},
        {"date": "2025-11-27", "time": "16:30", "away_team": "Kansas City Chiefs", "home_team": "Dallas Cowboys", "network": "CBS"},
        {"date": "2025-11-27", "time": "20:20", "away_team": "Cincinnati Bengals", "home_team": "Baltimore Ravens", "network": "NBC"},
        {"date": "2025-11-28", "time": "15:00", "away_team": "Chicago Bears", "home_team": "Philadelphia Eagles", "network": "Prime Video"},
        {"date": "2025-11-30", "time": "13:00", "away_team": "Los Angeles Rams", "home_team": "Carolina Panthers", "network": "FOX"},
        {"date": "2025-11-30", "time": "13:00", "away_team": "San Francisco 49ers", "home_team": "Cleveland Browns", "network": "CBS"},
        {"date": "2025-11-30", "time": "13:00", "away_team": "Houston Texans", "home_team": "Indianapolis Colts", "network": "CBS"},
        {"date": "2025-11-30", "time": "13:00", "away_team": "New Orleans Saints", "home_team": "Miami Dolphins", "network": "FOX"},
        {"date": "2025-11-30", "time": "13:00", "away_team": "Atlanta Falcons", "home_team": "New York Jets", "network": "FOX"},
        {"date": "2025-11-30", "time": "13:00", "away_team": "Arizona Cardinals", "home_team": "Tampa Bay Buccaneers", "network": "FOX"},
        {"date": "2025-11-30", "time": "13:00", "away_team": "Jacksonville Jaguars", "home_team": "Tennessee Titans", "network": "CBS"},
        {"date": "2025-11-30", "time": "16:05", "away_team": "Minnesota Vikings", "home_team": "Seattle Seahawks", "network": "FOX"},
        {"date": "2025-11-30", "time": "16:25", "away_team": "Las Vegas Raiders", "home_team": "Los Angeles Chargers", "network": "CBS"},
        {"date": "2025-11-30", "time": "16:25", "away_team": "Buffalo Bills", "home_team": "Pittsburgh Steelers", "network": "CBS"},
        {"date": "2025-11-30", "time": "20:20", "away_team": "Denver Broncos", "home_team": "Washington Commanders", "network": "NBC"},
        {"date": "2025-12-01", "time": "20:15", "away_team": "New York Giants", "home_team": "New England Patriots", "network": "ESPN"}
    ],
    "week_14": [
        {"date": "2025-12-04", "time": "20:15", "away_team": "Dallas Cowboys", "home_team": "Detroit Lions", "network": "Prime Video"},
        {"date": "2025-12-07", "time": "13:00", "away_team": "Seattle Seahawks", "home_team": "Atlanta Falcons", "network": "FOX"},
        {"date": "2025-12-07", "time": "13:00", "away_team": "Pittsburgh Steelers", "home_team": "Baltimore Ravens", "network": "CBS"},
        {"date": "2025-12-07", "time": "13:00", "away_team": "Tennessee Titans", "home_team": "Cleveland Browns", "network": "FOX"},
        {"date": "2025-12-07", "time": "13:00", "away_team": "Chicago Bears", "home_team": "Green Bay Packers", "network": "FOX"},
        {"date": "2025-12-07", "time": "13:00", "away_team": "Indianapolis Colts", "home_team": "Jacksonville Jaguars", "network": "CBS"},
        {"date": "2025-12-07", "time": "13:00", "away_team": "Washington Commanders", "home_team": "Minnesota Vikings", "network": "FOX"},
        {"date": "2025-12-07", "time": "13:00", "away_team": "Miami Dolphins", "home_team": "New York Jets", "network": "CBS"},
        {"date": "2025-12-07", "time": "13:00", "away_team": "New Orleans Saints", "home_team": "Tampa Bay Buccaneers", "network": "CBS"},
        {"date": "2025-12-07", "time": "16:05", "away_team": "Denver Broncos", "home_team": "Las Vegas Raiders", "network": "CBS"},
        {"date": "2025-12-07", "time": "16:25", "away_team": "Los Angeles Rams", "home_team": "Arizona Cardinals", "network": "FOX"},
        {"date": "2025-12-07", "time": "16:25", "away_team": "Cincinnati Bengals", "home_team": "Buffalo Bills", "network": "FOX"},
        {"date": "2025-12-07", "time": "20:20", "away_team": "Houston Texans", "home_team": "Kansas City Chiefs", "network": "NBC"},
        {"date": "2025-12-08", "time": "20:15", "away_team": "Philadelphia Eagles", "home_team": "Los Angeles Chargers", "network": "ESPN/ABC"}
    ],
    "week_15": [
        {"date": "2025-12-11", "time": "20:15", "away_team": "Atlanta Falcons", "home_team": "Tampa Bay Buccaneers", "network": "Prime Video"},
        {"date": "2025-12-14", "time": "13:00", "away_team": "Cleveland Browns", "home_team": "Chicago Bears", "network": "FOX"},
        {"date": "2025-12-14", "time": "13:00", "away_team": "Baltimore Ravens", "home_team": "Cincinnati Bengals", "network": "CBS"},
        {"date": "2025-12-14", "time": "13:00", "away_team": "Arizona Cardinals", "home_team": "Houston Texans", "network": "FOX"},
        {"date": "2025-12-14", "time": "13:00", "away_team": "New York Jets", "home_team": "Jacksonville Jaguars", "network": "CBS"},
        {"date": "2025-12-14", "time": "13:00", "away_team": "Los Angeles Chargers", "home_team": "Kansas City Chiefs", "network": "CBS"},
        {"date": "2025-12-14", "time": "13:00", "away_team": "Buffalo Bills", "home_team": "New England Patriots", "network": "CBS"},
        {"date": "2025-12-14", "time": "13:00", "away_team": "Washington Commanders", "home_team": "New York Giants", "network": "FOX"},
        {"date": "2025-12-14", "time": "13:00", "away_team": "Las Vegas Raiders", "home_team": "Philadelphia Eagles", "network": "FOX"},
        {"date": "2025-12-14", "time": "16:25", "away_team": "Green Bay Packers", "home_team": "Denver Broncos", "network": "CBS"},
        {"date": "2025-12-14", "time": "16:25", "away_team": "Detroit Lions", "home_team": "Los Angeles Rams", "network": "FOX"},
        {"date": "2025-12-14", "time": "16:25", "away_team": "Carolina Panthers", "home_team": "New Orleans Saints", "network": "FOX"},
        {"date": "2025-12-14", "time": "16:25", "away_team": "Indianapolis Colts", "home_team": "Seattle Seahawks", "network": "CBS"},
        {"date": "2025-12-14", "time": "16:25", "away_team": "Tennessee Titans", "home_team": "San Francisco 49ers", "network": "FOX"},
        {"date": "2025-12-14", "time": "20:20", "away_team": "Minnesota Vikings", "home_team": "Dallas Cowboys", "network": "NBC"},
        {"date": "2025-12-15", "time": "20:15", "away_team": "Miami Dolphins", "home_team": "Pittsburgh Steelers", "network": "ESPN/ABC"}
    ],
    "week_16": [
        {"date": "2025-12-18", "time": "20:15", "away_team": "Los Angeles Rams", "home_team": "Seattle Seahawks", "network": "Prime Video"},
        {"date": "2025-12-20", "time": "TBD", "away_team": "Green Bay Packers", "home_team": "Chicago Bears", "network": "FOX"},
        {"date": "2025-12-20", "time": "TBD", "away_team": "Philadelphia Eagles", "home_team": "Washington Commanders", "network": "FOX"},
        {"date": "2025-12-21", "time": "13:00", "away_team": "New England Patriots", "home_team": "Baltimore Ravens", "network": "CBS"},
        {"date": "2025-12-21", "time": "13:00", "away_team": "Tampa Bay Buccaneers", "home_team": "Carolina Panthers", "network": "FOX"},
        {"date": "2025-12-21", "time": "13:00", "away_team": "Buffalo Bills", "home_team": "Cleveland Browns", "network": "CBS"},
        {"date": "2025-12-21", "time": "13:00", "away_team": "Los Angeles Chargers", "home_team": "Dallas Cowboys", "network": "FOX"},
        {"date": "2025-12-21", "time": "13:00", "away_team": "New York Jets", "home_team": "New Orleans Saints", "network": "CBS"},
        {"date": "2025-12-21", "time": "13:00", "away_team": "Minnesota Vikings", "home_team": "New York Giants", "network": "FOX"},
        {"date": "2025-12-21", "time": "13:00", "away_team": "Kansas City Chiefs", "home_team": "Tennessee Titans", "network": "CBS"},
        {"date": "2025-12-21", "time": "16:05", "away_team": "Atlanta Falcons", "home_team": "Arizona Cardinals", "network": "FOX"},
        {"date": "2025-12-21", "time": "16:05", "away_team": "Jacksonville Jaguars", "home_team": "Denver Broncos", "network": "FOX"},
        {"date": "2025-12-21", "time": "16:25", "away_team": "Pittsburgh Steelers", "home_team": "Detroit Lions", "network": "CBS"},
        {"date": "2025-12-21", "time": "16:25", "away_team": "Las Vegas Raiders", "home_team": "Houston Texans", "network": "CBS"},
        {"date": "2025-12-21", "time": "20:20", "away_team": "Cincinnati Bengals", "home_team": "Miami Dolphins", "network": "NBC"},
        {"date": "2025-12-22", "time": "20:15", "away_team": "San Francisco 49ers", "home_team": "Indianapolis Colts", "network": "ESPN"}
    ],
    "week_17": [
        {"date": "2025-12-25", "time": "13:00", "away_team": "Dallas Cowboys", "home_team": "Washington Commanders", "network": "NETFLIX"},
        {"date": "2025-12-25", "time": "16:30", "away_team": "Detroit Lions", "home_team": "Minnesota Vikings", "network": "NETFLIX"},
        {"date": "2025-12-25", "time": "20:15", "away_team": "Denver Broncos", "home_team": "Kansas City Chiefs", "network": "Prime Video"},
        {"date": "2025-12-27", "time": "TBD", "away_team": "Seattle Seahawks", "home_team": "Carolina Panthers", "network": "TBD"},
        {"date": "2025-12-27", "time": "TBD", "away_team": "Arizona Cardinals", "home_team": "Cincinnati Bengals", "network": "TBD"},
        {"date": "2025-12-27", "time": "TBD", "away_team": "Baltimore Ravens", "home_team": "Green Bay Packers", "network": "TBD"},
        {"date": "2025-12-27", "time": "TBD", "away_team": "Houston Texans", "home_team": "Los Angeles Chargers", "network": "TBD"},
        {"date": "2025-12-27", "time": "TBD", "away_team": "New York Giants", "home_team": "Las Vegas Raiders", "network": "TBD"},
        {"date": "2025-12-28", "time": "13:00", "away_team": "Pittsburgh Steelers", "home_team": "Cleveland Browns", "network": "CBS"},
        {"date": "2025-12-28", "time": "13:00", "away_team": "Jacksonville Jaguars", "home_team": "Indianapolis Colts", "network": "FOX"},
        {"date": "2025-12-28", "time": "13:00", "away_team": "Tampa Bay Buccaneers", "home_team": "Miami Dolphins", "network": "FOX"},
        {"date": "2025-12-28", "time": "13:00", "away_team": "New England Patriots", "home_team": "New York Jets", "network": "CBS"},
        {"date": "2025-12-28", "time": "13:00", "away_team": "New Orleans Saints", "home_team": "Tennessee Titans", "network": "CBS"},
        {"date": "2025-12-28", "time": "16:25", "away_team": "Philadelphia Eagles", "home_team": "Buffalo Bills", "network": "FOX"},
        {"date": "2025-12-28", "time": "20:20", "away_team": "Chicago Bears", "home_team": "San Francisco 49ers", "network": "NBC"},
        {"date": "2025-12-29", "time": "20:15", "away_team": "Los Angeles Rams", "home_team": "Atlanta Falcons", "network": "ESPN"}
    ],
    "week_18": [
        {"date": "2026-01-03", "time": "TBD", "away_team": "New Orleans Saints", "home_team": "Atlanta Falcons", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "New York Jets", "home_team": "Buffalo Bills", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Detroit Lions", "home_team": "Chicago Bears", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Cleveland Browns", "home_team": "Cincinnati Bengals", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Los Angeles Chargers", "home_team": "Denver Broncos", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Indianapolis Colts", "home_team": "Houston Texans", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Tennessee Titans", "home_team": "Jacksonville Jaguars", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Arizona Cardinals", "home_team": "Los Angeles Rams", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Kansas City Chiefs", "home_team": "Las Vegas Raiders", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Green Bay Packers", "home_team": "Minnesota Vikings", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Miami Dolphins", "home_team": "New England Patriots", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Dallas Cowboys", "home_team": "New York Giants", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Washington Commanders", "home_team": "Philadelphia Eagles", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Baltimore Ravens", "home_team": "Pittsburgh Steelers", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Seattle Seahawks", "home_team": "San Francisco 49ers", "network": "TBD"},
        {"date": "2026-01-04", "time": "TBD", "away_team": "Carolina Panthers", "home_team": "Tampa Bay Buccaneers", "network": "TBD"}
    ]
}