import os
import json
from strands import Agent
from strands.models import BedrockModel
from app.tools.projections import get_weekly_projections
from app.tools.dynamo import load_team_roster, format_roster_for_agent
from app.batch_history import load_all_player_histories_batch, format_all_histories_for_agent
from app.tools.lineup import optimize_lineup_direct
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
    projections_tool_result = get_weekly_projections(week)
    
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

Your task is to identify the optimal lineup using the given team roster, the team matchups and player performance data as well as projection data for 2025.

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
        model_id=os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-5-haiku-20240620-v1:0"),
        max_tokens=3000,
        temperature=0.0,
        stream=False
    )

    # Minimal agent - most work is done, just need explanation/validation
    agent = Agent(
        model=bedrock_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[],  # No tools needed - everything is pre-computed
    )
    
    return agent

def _format_lineup_summary(lineup_result: dict) -> str:
    """Format the computed lineup for agent context."""
    if not lineup_result:
        return "No lineup computed."
    
    summary = "COMPUTED LINEUP:\n"
    
    lineup = lineup_result.get("lineup", [])
    for entry in lineup:
        slot = entry.get("slot", "")
        player = entry.get("player", "Empty")
        if player and player != "Empty":
            projected = entry.get("projected", 0)
            adjusted = entry.get("adjusted", 0)
            team = entry.get("team", "")
            summary += f"  {slot}: {player} ({team}) - Proj: {projected}, Adj: {adjusted}\n"
        else:
            error = entry.get("error", "No player found")
            summary += f"  {slot}: EMPTY ({error})\n"
    
    bench = lineup_result.get("bench", [])[:5]  # Top 5 bench players
    if bench:
        summary += "\nTOP BENCH PLAYERS:\n"
        for player in bench:
            name = player.get("name", "")
            pos = player.get("position", "")
            projected = player.get("projected", 0)
            adjusted = player.get("adjusted", 0)
            summary += f"  {name} ({pos}) - Proj: {projected}, Adj: {adjusted}\n"
    
    debug = lineup_result.get("debug_info", {})
    if debug:
        summary += f"\nDEBUG: {debug.get('lineup_filled', 0)}/{len(lineup)} slots filled, "
        summary += f"{debug.get('projection_matches', 0)} players with projections\n"
    
    return summary

def build_agent_ultra_fast(team_id: str, week: int, lineup_slots: list) -> dict:
    """Ultra-fast version that skips the agent entirely and returns pre-computed result.
    
    Returns the lineup result directly without LLM processing.
    """
    
    print(f"Ultra-fast mode: Computing lineup without LLM...")
    
    roster = load_team_roster(team_id)
    player_names = [p.get("name") for p in roster.get("players", []) if p.get("name")]
    all_histories = load_all_player_histories_batch(player_names)
    
    projections_tool_result = get_weekly_projections(week)
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