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

# Lambda entrypoint for API Gateway (proxy integration)
def lambda_handler(event, context):
    logger.info(f"Lambda invoked with event: {json.dumps(event, default=str)}")
    logger.info(f"Context: {context}")
    
    try:
        # Pull week from querystring (?week=1). Default to 1 if missing.
        qs = event.get("queryStringParameters") or {}
        logger.info(f"Query string parameters: {qs}")
        
        week_raw = qs.get("week") or event.get("week")  # allow direct invoke
        logger.info(f"Raw week parameter: {week_raw}")
        
        try:
            week = int(week_raw) if week_raw is not None else 1
            logger.info(f"Parsed week: {week}")
            if week < 1 or week > 18:
                raise ValueError("Week must be 1-18")
        except Exception as e:
            logger.error(f"Error parsing week parameter: {str(e)}")
            return _resp(400, {"error": "Invalid or missing 'week' (1-18)"})

        # Optional: team_id for multi-team tables (defaults to "1" per your example)
        team_id = qs.get("team_id", os.environ.get("DEFAULT_TEAM_ID", "1"))
        logger.info(f"Team ID: {team_id}")

        # Log environment variables (be careful not to log sensitive data)
        scoring = os.environ.get("SCORING", "PPR")
        lineup_slots = os.environ.get("LINEUP_SLOTS", "QB,RB,RB,WR,WR,TE,FLEX,K,DST").split(",")
        logger.info(f"Scoring: {scoring}")
        logger.info(f"Lineup slots: {lineup_slots}")

        logger.info("Building agent...")
        try:
            agent = build_agent(team_id, week, lineup_slots)  # Pass team_id and week
            logger.info("Agent built successfully")
        except Exception as e:
            logger.error(f"Failed to build agent: {str(e)}")
            logger.error(f"Agent build traceback: {traceback.format_exc()}")
            return _resp(500, {"error": "Failed to build agent", "detail": str(e)})

        # Ask the agent to compute the lineup
        req: AgentRequest = {
            "week": week,
            "team_id": team_id,
            "scoring": scoring,
            "lineup_slots": lineup_slots,
        }
        logger.info(f"Agent request: {req}")

        prompt = (f"Compute the optimal fantasy lineup for week {week} for team '{team_id}'. "
                 "Return strict JSON with keys: lineup (list of slot objects), bench (list), "
                 "explanations (string). Use projections + 2024 history vs opponent if available.")
        logger.info(f"Agent prompt: {prompt}")

        try:
            agent = build_agent_with_precomputed_lineup(team_id, week, req["lineup_slots"])
            logger.info("Agent built successfully with pre-computed lineup")
            
            result = agent(
                f"Review and explain the computed lineup for week {week}. "
                "Make any necessary adjustments and return the final lineup in the required JSON format."
            )
            logger.info("Agent execution completed")
        except Exception as e:
            logger.error(f"Agent execution failed: {str(e)}")
            logger.error(f"Agent execution traceback: {traceback.format_exc()}")
            return _resp(500, {"error": "Agent execution failed", "detail": str(e)})

        # Result parsing - handle both direct JSON and LLM response with JSON
        try:
            logger.info("Attempting to parse agent result as JSON...")
            
            # If result is already a dict (from ultra-fast mode), use it directly
            if isinstance(result, dict):
                payload = result
                logger.info("Using direct dict result")
            else:
                # Try to parse as JSON first
                result_str = str(result)
                try:
                    payload = json.loads(result_str)
                    logger.info("Successfully parsed full result as JSON")
                except json.JSONDecodeError:
                    # Look for JSON within the LLM response
                    logger.info("Full parse failed, looking for JSON block in response...")
                    
                    # Find JSON block (look for ```json or just { })
                    import re
                    
                    # Try to find JSON in code block
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', result_str, re.DOTALL)
                    if not json_match:
                        # Try to find standalone JSON object
                        json_match = re.search(r'(\{[^`]*"lineup"[^`]*\})', result_str, re.DOTALL)
                    
                    if json_match:
                        json_str = json_match.group(1)
                        logger.info(f"Found JSON block: {json_str[:200]}...")
                        try:
                            payload = json.loads(json_str)
                            logger.info("Successfully parsed extracted JSON")
                        except json.JSONDecodeError as je:
                            logger.warning(f"Failed to parse extracted JSON: {je}")
                            payload = {"raw": result_str, "parse_error": str(je)}
                    else:
                        logger.warning("No JSON block found in response")
                        payload = {"raw": result_str, "parse_error": "No JSON found"}
            
            logger.info(f"Final payload keys: {payload.keys() if isinstance(payload, dict) else 'Not a dict'}")
            
        except Exception as e:
            logger.error(f"Unexpected error during result parsing: {str(e)}")
            payload = {"raw": str(result), "error": str(e)}

        logger.info("Returning successful response")
        return _resp(200, payload)

    except Exception as e:
        # Catch-all for any unexpected errors
        logger.error(f"Unexpected error in lambda_handler: {str(e)}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        return _resp(500, {"error": "Internal server error", "detail": str(e)})


def _resp(status_code: int, body: dict) -> LambdaResponse:
    logger.info(f"Creating response with status {status_code}")
    logger.info(f"Response body keys: {body.keys() if isinstance(body, dict) else 'Not a dict'}")
    
    response = {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, ensure_ascii=False),
        "isBase64Encoded": False,
    }
    
    logger.info(f"Response created successfully")
    return response