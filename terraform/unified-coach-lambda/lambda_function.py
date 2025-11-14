"""
Lambda handler for Unified Fantasy Football Coach
Entry point for API Gateway requests
"""

import json
import logging
from unified_coach_manager import get_unified_coach

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    """Handle incoming requests from API Gateway"""
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            body = json.loads(body)

        message = body.get('message', '')
        request_context = body.get('context', {})

        # Extract team_id and week from context or query params
        query_params = event.get('queryStringParameters') or {}
        team_id = request_context.get('team_id') or query_params.get('team_id', '7')
        week = request_context.get('week') or int(query_params.get('week', 11))

        # Build full context
        full_context = {
            'team_id': str(team_id),
            'week': int(week),
            **request_context
        }

        logger.info(f"Processing message for team={team_id}, week={week}: {message}")

        # Get unified coach and process message
        coach = get_unified_coach()
        result = coach.process_message(message, full_context)

        # Add CORS headers
        if isinstance(result, dict) and 'headers' not in result:
            result['headers'] = {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }

        return result

    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }
