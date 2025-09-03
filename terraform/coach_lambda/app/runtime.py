import os
from strands import Agent
from strands.models import BedrockModel
from app.tools.projections import get_weekly_projections
from app.tools.dynamo import get_team_roster, get_player_history_2024
from app.tools.lineup import choose_optimal_lineup

SYSTEM_PROMPT = """\
You select an optimal fantasy football lineup (PPR by default) for the given team and week.
Use the registered tools to:
1) fetch weekly projections by position from FantasyPros,
2) load the user's current roster from DynamoDB,
3) enrich each roster player with 2024 history including opponent splits if available,
4) choose the best starters for the requested lineup slots (QB,RB,RB,WR,WR,TE,FLEX,K,DST by default).

Rules:
- FLEX may be RB/WR/TE only.
- OP may be QB/RB/WR/TE.
- Prefer the player's Week projection; adjust up/down using 2024 opponent split and recent-4 average if available.
- If two players are close (±0.3 pts), break ties by higher projection, then consistency (lower stdev last 4), then team implied points (if provided).
- Always return STRICT JSON like:
{
  "lineup":[{"slot":"QB","player":"Josh Allen","team":"BUF","position":"QB","projected":22.4,"adjusted":23.1}],
  "bench":[{"player":"...","position":"WR","projected":...,"adjusted":...}],
  "explanations":"short rationale text"
}
"""

def build_agent() -> Agent:
    # Bedrock (Anthropic Claude). Model ID can be overridden via env.
    # Example Claude 4 Sonnet model id (as commonly shown in Strands docs/blogs).
    model_id = os.environ.get(
        "BEDROCK_MODEL_ID",
        "us.anthropic.claude-sonnet-4-20250514-v1:0",
    )
    temperature = float(os.environ.get("MODEL_TEMPERATURE", "0.1"))

    bedrock_model = BedrockModel(
        model_id=model_id,
        temperature=temperature,
        streaming=False,
        # Optional extras:
        # region_name=os.environ.get("AWS_REGION", "us-west-2"),
        # cache_prompt="lineup_planner_v1",
    )

    # Build agent with our tools
    agent = Agent(
        model=bedrock_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            get_weekly_projections,
            get_team_roster,
            get_player_history_2024,
            choose_optimal_lineup,
        ],
    )
    return agent
