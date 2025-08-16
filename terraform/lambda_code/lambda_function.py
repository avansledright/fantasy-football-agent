# lambda_function.py
import json
import os
from strands import Agent
from strands.models import BedrockModel
from tools.fantasy_draft_tool import get_best_available_player

# Load the draft system prompt
with open("prompts/draft_agent_prompt.txt") as f:
    DRAFT_PROMPT = f.read()

# Configure the Bedrock model (Claude 3.5 Haiku by default)
bedrock_model = BedrockModel(
    model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20240620-v1:0"),
    max_tokens=4000,
    temperature=0.0,
)

# Create the agent
agent = Agent(
    model=bedrock_model,
    system_prompt=DRAFT_PROMPT,
    tools=[get_best_available_player],
)

def lambda_handler(event, context):
    team_needs = event.get("team_needs", {})
    already_drafted = event.get("already_drafted", [])

    query = (
        f"My current team needs: {team_needs}. "
        f"Already drafted player IDs: {already_drafted}. "
        "Who should I pick next?"
    )

    result = agent(query)
    print(result)
    print(f"type of result: {type(result)}")
    # Safely extract output text
    output_text = getattr(result, "text", None) or \
                  getattr(result, "output", None) or \
                  getattr(result, "response", {}).get("output_text")

    # Fallback: stringify whole result
    if not output_text:
        output_text = str(result)

    return {
        "statusCode": 200,
        "body": json.dumps({
            "recommendation": output_text,
            "tool_calls": getattr(result, "tool_calls", [])
        })
    }