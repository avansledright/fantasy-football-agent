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