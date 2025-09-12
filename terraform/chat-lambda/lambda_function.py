"""
Fantasy Football AI Chat Manager Lambda Function
Handles chat messages from the web interface using Strands SDK
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, Any

from chat_manager import ChatManager
from utils import create_cors_response

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Global chat manager instance (for Lambda container reuse)
chat_manager = None

def get_chat_manager():
    """Get or create chat manager instance"""
    global chat_manager
    if chat_manager is None:
        chat_manager = ChatManager()
    return chat_manager

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for chat messages
    """
    try:
        logger.info(f"Received event: {json.dumps(event, default=str)}")
        
        # Handle CORS preflight
        if event.get('httpMethod') == 'OPTIONS':
            return create_cors_response(200, {'message': 'CORS preflight response'})
        
        # Handle health check
        if event.get('httpMethod') == 'GET' and event.get('path', '').endswith('/health'):
            return handle_health_check()
        
        # Parse the request body
        body_str = event.get('body', '{}')
        if isinstance(body_str, str):
            body = json.loads(body_str)
        else:
            body = body_str
        
        message = body.get('message', '').strip()
        context_data = body.get('context', {})
        
        if not message:
            return create_cors_response(400, {'error': 'Message is required'})
        
        # Validate context data
        if not context_data.get('team_id'):
            context_data['team_id'] = 'team1'  # Default team ID
        
        if not context_data.get('week'):
            context_data['week'] = '2'  # Default week
            
        if not context_data.get('league_name'):
            context_data['league_name'] = 'Default League'
        
        logger.info(f"Processing message: '{message}' for team: {context_data.get('team_id')}")
        
        # Initialize chat manager and process the message
        manager = get_chat_manager()
        response_data = manager.process_message(message, context_data)
        
        logger.info(f"Chat response generated successfully for session: {response_data.get('session_id')}")
        
        return create_cors_response(200, response_data)
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request body: {str(e)}")
        return create_cors_response(400, {'error': 'Invalid JSON format'})
        
    except Exception as e:
        logger.error(f"Error processing chat message: {str(e)}", exc_info=True)
        return create_cors_response(500, {
            'error': 'Internal server error',
            'message': 'I\'m having trouble processing your request right now. Please try again!',
            'session_id': f"error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            'timestamp': datetime.utcnow().isoformat()
        })

def handle_health_check() -> Dict[str, Any]:
    """
    Handle health check requests
    """
    try:
        manager = get_chat_manager()
        health_status = manager.get_health_status()
        
        status_code = 200 if health_status['status'] == 'healthy' else 503
        
        return create_cors_response(status_code, health_status)
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return create_cors_response(503, {
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

def warm_lambda():
    """
    Warm up the Lambda function by initializing components
    """
    try:
        logger.info("Warming up Lambda function...")
        manager = get_chat_manager()
        logger.info("Lambda function warmed up successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to warm up Lambda: {str(e)}")
        return False

# Warm up on module import for faster cold starts
if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
    warm_lambda()