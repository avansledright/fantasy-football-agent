# app/runtime.py
"""
Streamlined runtime using unified player data table.
"""

import os
import json
from strands import Agent
from strands.models import BedrockModel
from app.projections import get_roster_projections
from app.dynamo import load_team_roster, format_roster_for_agent
from app.player_data import load_roster_player_data, format_player_histories, analyze_player_performance, compare_roster_players
from app.lineup import optimize_lineup_direct
from app.schedule import get_matchups_by_week
from app.waiver_wire import get_position_waiver_targets, analyze_waiver_opportunities_with_projections

def build_agent_with_precomputed_lineup(team_id: str, week: int, lineup_slots: list) -> Agent:
    """Build agent with comprehensive unified table data."""
    
    print(f"Loading roster for team {team_id}...")
    roster = load_team_roster(team_id)
    
    print(f"Loading comprehensive player data from unified table...")
    roster_players = roster.get("players", [])
    unified_player_data = load_roster_player_data(roster_players)
    
    print(f"Fetching external weekly projections...")
    projections_data = get_roster_projections(week, roster_players)
    projections_json = json.dumps(projections_data)
    
    print(f"Getting weekly matchups...")
    weekly_matchups = get_matchups_by_week(week)
    
    # Format context for agent
    roster_context = format_roster_for_agent(roster)
    player_data_context = format_player_histories(unified_player_data)
    
    SYSTEM_PROMPT = f"""You are a fantasy football lineup optimizer for week {week}.

TEAM ROSTER:
{roster_context}

If the team roster contains players with below 10 points projected we should be considering alternative players through waiver acquisition

COMPREHENSIVE PLAYER DATA:
{player_data_context}

WEEKLY MATCHUPS: 
{weekly_matchups}

WEEKLY PROJECTIONS (External API):
{projections_json}

You have access to advanced analysis tools:

- analyze_player_performance: Get comprehensive analysis for individual players
- compare_roster_players: Compare multiple players across different metrics
- get_position_waiver_targets(position, week={week}) - Get specific waiver targets for a position with low ownership.
-  analyze_waiver_opportunities_with_projections(current_roster, external_projections, week={week}) - Analyze waiver wire opportunities using external projection data.

Your task: Optimize the lineup for week {week} using:
1. 2024 historical performance data
2. 2025 season projections 
3. Current 2025 weekly performance
4. External weekly projections
5. Team matchups and game context
6. Consider player acquisitions through waiver wire using the tool get_position_waiver_targets(position, week={week})
7. Analyze best waiver wire acquisitions with the tool analyze_waiver_opportunities_with_projections
8. For waiver suggestions be sure to analyze their past performance against their opponents
9. If a waiver suggestion is projected less than 5 points they should not be considered for acquisition

Required lineup positions: {lineup_slots}
(FLEX = RB/WR/TE, OP = QB/RB/WR/TE)

Return in this exact JSON format:
{{
  "lineup": [{{"slot":"QB","player":"Josh Allen","team":"BUF","position":"QB","projected":22.4,"adjusted":23.1}}],
  "bench": [{{"player":"...","position":"...","projected":...,"adjusted":...}}],
  "explanations": "Detailed reasoning incorporating all data sources and analysis. Including all top waiver picks (atleast 3 per position). Include explanation into each waiver wire selection"
}}
"""

    bedrock_model = BedrockModel(
        model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
        max_tokens=3000,
        temperature=0.0,
        stream=False
    )
    
    # Import the injury analysis tool
    from app.player_data import analyze_player_performance, compare_roster_players, analyze_injury_impact
    
    agent = Agent(
        model=bedrock_model,
        system_prompt=SYSTEM_PROMPT,
        tools=[analyze_player_performance, compare_roster_players, analyze_injury_impact, analyze_waiver_opportunities_with_projections, get_position_waiver_targets]
    )
    
    return agent

def build_agent_ultra_fast(team_id: str, week: int, lineup_slots: list) -> dict:
    """Ultra-fast optimization using direct computation."""
    
    print(f"Ultra-fast mode: Direct optimization with unified data...")
    
    roster = load_team_roster(team_id)
    roster_players = roster.get("players", [])
    
    # Get external projections
    projections_data = get_roster_projections(week, roster_players)
    if isinstance(projections_data, str):
        projections_data = json.loads(projections_data)
    
    # Direct optimization
    result = optimize_lineup_direct(
        lineup_slots=lineup_slots,
        roster_players=roster_players,
        projections_data=projections_data
    )
    
    # Enhanced explanation
    result["explanations"] = (
        f"Week {week} lineup optimized using comprehensive unified data: "
        f"external weekly projections, 2025 season projections, 2024 historical performance, "
        f"and confidence-weighted scoring. Filled {result.get('debug_info', {}).get('lineup_filled', 0)} slots "
        f"with average confidence of {result.get('debug_info', {}).get('avg_confidence', 0)}."
    )
    
    return result

# Backward compatibility
def build_agent(team_id: str, week: int, lineup_slots) -> Agent:
    """Backward compatible agent builder."""
    return build_agent_with_precomputed_lineup(team_id, week, lineup_slots)