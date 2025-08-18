# NFL team abbreviations list
nfl_teams = [
    "ARI",  # Arizona Cardinals
    "ATL",  # Atlanta Falcons
    "BAL",  # Baltimore Ravens
    "BUF",  # Buffalo Bills
    "CAR",  # Carolina Panthers
    "CHI",  # Chicago Bears
    "CIN",  # Cincinnati Bengals
    "CLE",  # Cleveland Browns
    "DAL",  # Dallas Cowboys
    "DEN",  # Denver Broncos
    "DET",  # Detroit Lions
    "GB",   # Green Bay Packers
    "HOU",  # Houston Texans
    "IND",  # Indianapolis Colts
    "JAX",  # Jacksonville Jaguars
    "JAC",  # Jacksonville 
    "KC",   # Kansas City Chiefs
    "LV",   # Las Vegas Raiders
    "LAC",  # Los Angeles Chargers
    "LAR",  # Los Angeles Rams
    "MIA",  # Miami Dolphins
    "MIN",  # Minnesota Vikings
    "NE",   # New England Patriots
    "NO",   # New Orleans Saints
    "NYG",  # New York Giants
    "NYJ",  # New York Jets
    "PHI",  # Philadelphia Eagles
    "PIT",  # Pittsburgh Steelers
    "SF",   # San Francisco 49ers
    "SEA",  # Seattle Seahawks
    "TB",   # Tampa Bay Buccaneers
    "TEN",  # Tennessee Titans
    "WAS"   # Washington Commanders
]

def remove_nfl_abbreviations(text):
    """
    Remove NFL team abbreviations from a string.
    Case sensitive - only removes abbreviations in capital letters.
    
    Args:
        text (str): Input string to process
        
    Returns:
        str: String with NFL abbreviations removed
    """
    result = text
    for team in nfl_teams:
        result = result.replace(team, "")
    return result