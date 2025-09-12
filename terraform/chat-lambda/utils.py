"""
Message utilities for chat storage and processing
"""
import uuid
from datetime import datetime
from typing import Dict, Any
import logging
import json


logger = logging.getLogger(__name__)

def normalize_position(position: str) -> str:
    """Normalize position abbreviations."""
    pos = position.upper().strip()
    if pos in ("DEF", "D/ST"):
        return "DST"
    return pos

def store_chat_message(db_client, session_id: str, message: str, sender: str, context: Dict[str, Any]) -> None:
    """
    Store chat message in DynamoDB using the database client
    """
    try:
        success = db_client.store_chat_message(session_id, message, sender, context)
        if success:
            logger.info(f"Successfully stored {sender} message for session: {session_id}")
        else:
            logger.warning(f"Failed to store {sender} message for session: {session_id}")
    except Exception as e:
        logger.error(f"Error in store_chat_message utility: {str(e)}")
        # Don't fail the request if storage fails


def create_cors_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a response with CORS headers
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS, GET',
            'Access-Control-Allow-Headers': 'Content-Type, X-Amz-Date, Authorization, X-Api-Key, X-Amz-Security-Token',
            'Content-Type': 'application/json'
        },
        'body': json.dumps(body, default=str)  # default=str handles datetime serialization
    }

def generate_session_id(context: Dict[str, Any]) -> str:
    """
    Generate a session ID based on team context
    """
    team_id = context.get('team_id', 'unknown')
    week = context.get('week', 'unknown')
    timestamp = datetime.utcnow().strftime('%Y%m%d')
    
    return f"{team_id}_{week}_{timestamp}_{str(uuid.uuid4())[:8]}"

def convert_nfl_defense_name(player_id):
    """
    Converts NFL defense names from format "TeamName D/ST" to "Full Team Name#DST"
    
    Args:
        player_id (str): Player ID in format like "Dolphins D/ST"
        
    Returns:
        str: Converted name in format like "Miami Dolphins#DST"
    """
    
    # Mapping dictionary for all 32 NFL teams
    nfl_team_mappings = {
        # AFC East
        "Bills": "Buffalo Bills",
        "Dolphins": "Miami Dolphins", 
        "Patriots": "New England Patriots",
        "Jets": "New York Jets",
        
        # AFC North
        "Ravens": "Baltimore Ravens",
        "Bengals": "Cincinnati Bengals",
        "Browns": "Cleveland Browns",
        "Steelers": "Pittsburgh Steelers",
        
        # AFC South
        "Texans": "Houston Texans",
        "Colts": "Indianapolis Colts",
        "Jaguars": "Jacksonville Jaguars",
        "Titans": "Tennessee Titans",
        
        # AFC West
        "Broncos": "Denver Broncos",
        "Chiefs": "Kansas City Chiefs",
        "Raiders": "Las Vegas Raiders",
        "Chargers": "Los Angeles Chargers",
        
        # NFC East
        "Cowboys": "Dallas Cowboys",
        "Giants": "New York Giants",
        "Eagles": "Philadelphia Eagles",
        "Commanders": "Washington Commanders",
        
        # NFC North
        "Bears": "Chicago Bears",
        "Lions": "Detroit Lions",
        "Packers": "Green Bay Packers",
        "Vikings": "Minnesota Vikings",
        
        # NFC South
        "Falcons": "Atlanta Falcons",
        "Panthers": "Carolina Panthers",
        "Saints": "New Orleans Saints",
        "Buccaneers": "Tampa Bay Buccaneers",
        
        # NFC West
        "Cardinals": "Arizona Cardinals",
        "Rams": "Los Angeles Rams",
        "49ers": "San Francisco 49ers",
        "Seahawks": "Seattle Seahawks"
    }
    
    # Check if the input contains "D/ST"
    if " D/ST" not in player_id:
        return player_id  # Return unchanged if not a defense
    
    # Extract team name by removing " D/ST"
    team_name = player_id.replace(" D/ST", "")
    
    # Look up the full team name
    if team_name in nfl_team_mappings:
        full_team_name = nfl_team_mappings[team_name]
        return f"{full_team_name}#DST"
    else:
        # If team not found, return original format but with #DST
        return player_id.replace(" D/ST", "#DST")
