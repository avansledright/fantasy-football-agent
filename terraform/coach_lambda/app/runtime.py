import os
import json
from strands import Agent
from strands.models import BedrockModel
from app.tools.projections import get_roster_projections
from app.tools.dynamo import load_team_roster, format_roster_for_agent
from app.tools.stats import get_previous_week_stats, get_player_recent_trends, get_position_leaders_by_week
from app.batch_history import load_all_player_histories_batch, format_all_histories_for_agent
from app.tools.lineup import optimize_lineup_direct
from app.tools.stats_tools_wrapper import create_context_aware_stats_tools
from app.utils.nfl_schedule import get_matchups_by_week

def build_agent_with_precomputed_lineup(team_id: str, week: int, lineup_slots: list) -> tuple[Agent, dict]:
    """Build agent and pre-compute the optimal lineup.
    
    Returns:
        tuple of (agent, precomputed_lineup_result)
    """
    
    print(f"Loading roster for team {team_id}...")
    roster = load_team_roster(team_id)
    
    print(f"Loading history for {len(roster.get('players', []))} players...")
    player_names = [p.get("name") for p in roster.get("players", []) if p.get("name")]
    all_histories = load_all_player_histories_batch(player_names)
    
    print(f"Fetching weekly projections...")
    # Get projections using the tool (we need this data anyway)
    projections_data = get_roster_projections(week, roster.get("players", []))
    projections_tool_result = json.dumps(projections_data)
    print(f"Projection tool result {projections_tool_result}")
    print(f"Getting weekly team matchups")
    weekly_matchups = get_matchups_by_week(week)
    print(weekly_matchups)
    
    
    # Format all context for agent
    roster_context = format_roster_for_agent(roster)
    history_context = format_all_histories_for_agent(all_histories)
    
    SYSTEM_PROMPT = f"""You are a fantasy football lineup optimizer for week {week}.

TEAM ROSTER:
{roster_context}

PLAYER PERFORMANCE DATA:
{history_context}

WEEK TEAM MATCHUPS: 
{weekly_matchups}
This is shown as AWAY: Home. Example DET: GB is Detroit at Green Bay or Detroit is the away team.

PROJECTIONS:
{projections_tool_result}

You have access to additional tools for analyzing 2025 season stats:
- get_previous_week_stats: Get actual performance data from previous weeks in 2025
- get_player_recent_trends: Analyze recent performance trends for specific players
- get_position_leaders_by_week: See top performers by position for any week

Use these tools to gather additional context about player performance and trends before making your final lineup recommendations.

Your task is to identify the optimal lineup using the given team roster, the team matchups, player performance data, and current 2025 season stats.

The roster should consist of EXACTLY these positions:
{lineup_slots}
Reminder: The OP slot can be RB/WR/TE/QB

Return your final recommendation in this EXACT JSON format:
{{
  "lineup": [{{"slot":"QB","player":"Josh Allen","team":"BUF","position":"QB","projected":22.4,"adjusted":23.1}}],
  "bench": [{{"player":"...","position":"WR","projected":...,"adjusted":...}}],
  "explanations": "Detailed explanation of lineup choices and any adjustments made"
}}
"""

    bedrock_model = BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
        max_tokens=3000,
        temperature=0.0,
        stream=False
    )

    # Create context-aware stats tools with the current week
    (
        get_previous_week_stats,
        get_player_recent_trends,
        get_position_leaders_by_week,
        get_week_schedule_and_completion_status,
        get_optimal_analysis_week
    ) = create_context_aware_stats_tools(week)
    
    # Include the context-aware stats tools
    agent = Agent(
        model=bedrock_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            get_previous_week_stats,
            get_player_recent_trends, 
            get_position_leaders_by_week,
            get_week_schedule_and_completion_status,
            get_optimal_analysis_week
        ],
    )
    
    return agent

def build_agent_ultra_fast(team_id: str, week: int, lineup_slots: list) -> dict:
    """Ultra-fast version that skips the agent entirely and returns pre-computed result.
    
    Returns the lineup result directly without LLM processing.
    """
    
    print(f"Ultra-fast mode: Computing lineup without LLM...")
    
    roster = load_team_roster(team_id)
    player_names = [p.get("name") for p in roster.get("players", []) if p.get("name")]
    all_histories = load_all_player_histories_batch(player_names)
    
    projections_tool_result = get_roster_projections(week)
    try:
        projections_data = json.loads(projections_tool_result) if isinstance(projections_tool_result, str) else projections_tool_result
    except:
        projections_data = {}
    
    lineup_result = optimize_lineup_direct(
        lineup_slots=lineup_slots,
        roster_players=roster.get("players", []),
        projections_data=projections_data,
        histories_data=all_histories
    )
    
    # Add a simple explanation
    lineup_result["explanations"] = (
        f"Lineup optimized using week {week} projections combined with 2024 performance data. "
        f"Selections based on adjusted scores (70% projection + 20% vs opponent + 10% recent form). "
        f"Filled {lineup_result.get('debug_info', {}).get('lineup_filled', 0)} slots."
    )
    
    return lineup_result

# Backward compatibility  
def build_agent(team_id: str, week: int, lineup_slots) -> Agent:
    """Backward compatible function that returns just the agent."""
    agent = build_agent_with_precomputed_lineup(team_id, week, lineup_slots)
    return agent