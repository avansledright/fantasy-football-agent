# Python 3.12
import json
import os
import logging
import traceback
from app.runtime import build_agent, build_agent_ultra_fast, build_agent_with_precomputed_lineup
from app.types import LambdaResponse, AgentRequest

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Set required environment variables with defaults
ENV_DEFAULTS = {
    "PLAYERS_TABLE": "fantasy-football-players",
    "DDB_TABLE_ROSTER": "fantasy-football-team-roster"
}

for var, default in ENV_DEFAULTS.items():
    if not os.environ.get(var):
        logger.info(f"Setting {var} to default: {default}")
        os.environ[var] = default

def lambda_handler(event, context):
    """Streamlined Lambda handler for fantasy football agent."""
    logger.info(f"Request received for fantasy lineup optimization")
    
    try:
        # Parse parameters
        qs = event.get("queryStringParameters") or {}
        
        # Get week (required)
        try:
            week = int(qs.get("week") or event.get("week") or 1)
            if not 1 <= week <= 18:
                return _error_response(400, "Week must be between 1-18")
        except (ValueError, TypeError):
            return _error_response(400, "Invalid week parameter")
        
        # Get team_id
        team_id = qs.get("team_id", os.environ.get("DEFAULT_TEAM_ID", "1"))
        
        # Get configuration
        scoring = os.environ.get("SCORING", "PPR") 
        lineup_slots = os.environ.get("LINEUP_SLOTS", "QB,RB,RB,WR,WR,TE,FLEX,K,DST").split(",")
        
        logger.info(f"Processing week {week} for team {team_id}")
        
        # Build agent
        try:
            agent = build_agent_with_precomputed_lineup(team_id, week, lineup_slots)
            logger.info("Agent built successfully")
        except Exception as e:
            logger.error(f"Agent build failed: {str(e)}")
            return _error_response(500, f"Failed to build agent: {str(e)}")
        
        # Execute agent
        try:
            prompt = (
                f"Optimize the fantasy lineup for week {week}. "
                f"Use comprehensive unified data analysis and return JSON format."
            )
            
            result = agent(prompt)
            logger.info("Agent completed lineup optimization")
            
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            return _error_response(500, f"Agent execution failed: {str(e)}")
        
        # Parse result
        try:
            if isinstance(result, dict):
                payload = result
            else:
                # Try to extract JSON from agent response
                result_str = str(result)
                
                # Look for JSON block
                import re
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', result_str, re.DOTALL)
                if not json_match:
                    json_match = re.search(r'(\{[^`]*"lineup"[^`]*\})', result_str, re.DOTALL)
                
                if json_match:
                    payload = json.loads(json_match.group(1))
                else:
                    # Fallback: try parsing entire response
                    try:
                        payload = json.loads(result_str)
                    except json.JSONDecodeError:
                        payload = {
                            "raw_response": result_str,
                            "error": "Could not parse JSON from agent response"
                        }
            
            logger.info("Successfully processed lineup optimization")
            return _success_response(payload)
            
        except Exception as e:
            logger.error(f"Result parsing failed: {str(e)}")
            return _error_response(500, f"Failed to parse result: {str(e)}")
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        return _error_response(500, f"Internal error: {str(e)}")

def _success_response(data: dict) -> LambdaResponse:
    """Create successful response."""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(data, ensure_ascii=False),
        "isBase64Encoded": False,
    }

def _error_response(status_code: int, message: str) -> LambdaResponse:
    """Create error response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"error": message}),
        "isBase64Encoded": False,
    }