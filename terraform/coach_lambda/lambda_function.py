# Python 3.12
import json
import os
from app.runtime import build_agent
from app.types import LambdaResponse, AgentRequest

# Lambda entrypoint for API Gateway (proxy integration)
def lambda_handler(event, context):
    # Pull week from querystring (?week=1). Default to 1 if missing.
    qs = event.get("queryStringParameters") or {}
    week_raw = qs.get("week") or event.get("week")  # allow direct invoke
    try:
        week = int(week_raw) if week_raw is not None else 1
        if week < 1 or week > 18:
            raise ValueError("Week must be 1-18")
    except Exception:
        return _resp(400, {"error": "Invalid or missing 'week' (1-18)"})

    # Optional: team_id for multi-team tables (defaults to "1" per your example)
    team_id = qs.get("team_id", os.environ.get("DEFAULT_TEAM_ID", "1"))

    agent = build_agent()

    # Ask the agent to compute the lineup
    req: AgentRequest = {
        "week": week,
        "team_id": team_id,
        "scoring": os.environ.get("SCORING", "PPR"),  # hint to the agent (not enforced)
        "lineup_slots": os.environ.get("LINEUP_SLOTS", "QB,RB,RB,WR,WR,TE,FLEX,K,DST").split(","),
    }

    try:
        result = agent(
            f"Compute the optimal fantasy lineup for week {week} for team '{team_id}'. "
            "Return strict JSON with keys: lineup (list of slot objects), bench (list), "
            "explanations (string). Use projections + 2024 history vs opponent if available.",
            context=req,  # Strands context is available to tools
        )
    except Exception as e:
        # If LLM fails, we still return a 500 with message
        return _resp(500, {"error": "Agent execution failed", "detail": str(e)})

    # Result is an LLM string; our tools also return JSON snippets.
    # We try to parse JSON from the assistant output; if parsing fails, wrap it.
    try:
        payload = json.loads(str(result))
    except Exception:
        payload = {"raw": str(result)}

    return _resp(200, payload)


def _resp(status_code: int, body: dict) -> LambdaResponse:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, ensure_ascii=False),
        "isBase64Encoded": False,
    }
