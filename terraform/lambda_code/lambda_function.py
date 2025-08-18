# lambda_function.py
import json
import os
from strands import Agent
from strands.models import BedrockModel
from tools.fantasy_draft_tool import get_best_available_player

with open("prompts/draft_agent_prompt.txt") as f:
    DRAFT_PROMPT = f.read()

bedrock_model = BedrockModel(
    model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20240620-v1:0"),
    max_tokens=4000,
    temperature=0.0,
    stream=False
)

agent = Agent(
    model=bedrock_model,
    system_prompt=DRAFT_PROMPT,
    tools=[get_best_available_player]
)

def lambda_handler(event, context):
    print(f"DEBUG: Raw event: {json.dumps(event)}")

    if 'body' in event:
        if isinstance(event['body'], str):
            body = json.loads(event['body'])
        else:
            body = event['body']
    else:
        body = event

    print(f"DEBUG: Parsed body: {json.dumps(body)}")

    team_needs = body.get("team_needs", {
        "QB": 2, "RB": 2, "WR": 2, "TE": 1, "DST": 1, "K": 1, "FLEX": 1
    })
    your_roster = body.get("your_roster", {})
    already_drafted = body.get("already_drafted", [])
    scoring_format = body.get("scoring_format", "ppr")
    league_size = body.get("league_size", 12)

    print(f"DEBUG: team_needs = {team_needs}")
    print(f"DEBUG: your_roster = {your_roster}")
    print(f"DEBUG: already_drafted count = {len(already_drafted)}")
    excluded_names = [p.split("#")[0] for p in already_drafted]
    excluded_list = ", ".join(excluded_names)
    print(f"DEBUG Already Drafted = {excluded_list}")

    query = (
        f"Recommend the best player for my next pick.\n"
        f"Team needs: {team_needs}\n"
        f"My roster: {your_roster}\n"
        f"Exclude these drafted players: {excluded_list}\n"
        f"Only use the tool outputs and do not include excluded players in recommendations."
    )

    print(f"DEBUG: Agent query: {query}")

    result = agent(query)
    print(f"DEBUG: Agent result: {result}")

    output_text = getattr(result, "text", None) or \
                  getattr(result, "output", None) or \
                  getattr(result, "response", {}).get("output_text")
    if not output_text:
        output_text = str(result)

    response_body = {
        "recommendation": output_text,
        "tool_calls": getattr(result, "tool_calls", []),
        "debug_info": {
            "team_needs": team_needs,
            "your_roster": your_roster,
            "already_drafted_count": len(already_drafted),
            "scoring_format": scoring_format,
            "league_size": league_size
        }
    }

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type"
        },
        "body": json.dumps(response_body)
    }
