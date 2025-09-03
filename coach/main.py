# main.py
import sys
import json
import re
import logging
from strands import Agent
from fantasy_tools import load_roster, gather_weekly_data, analyze_players, generate_optimal_lineup

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main execution using the Strands agent"""
    if len(sys.argv) < 3:
        print("Usage: python3 main.py <team_id> <week_number>")
        print("Example: python3 main.py my_team_123 8")
        return
    
    team_id = sys.argv[1]
    try:
        week = int(sys.argv[2])
    except ValueError:
        print("Week number must be an integer")
        return
    
    try:
        # Create agent with all our tools
        agent = Agent(
            name="FantasyFootballCoach",
            description="AI-powered fantasy football coaching assistant that combines historical performance data with current projections to generate optimal lineups",
            tools=[load_roster, gather_weekly_data, analyze_players, generate_optimal_lineup]
        )
        
        print(f"Starting Fantasy Football Agent for team '{team_id}', week {week}...")
        
        # Use the agent with a natural language workflow that leverages AI reasoning
        workflow_prompt = f"""
I need you to help me create the optimal fantasy football lineup for team '{team_id}' for week {week}. 

As my AI fantasy football coach, please:

1. First, load the roster for team '{team_id}' using the load_roster tool
2. Gather all the weekly data for week {week} using gather_weekly_data (this gets both current projections AND historical data)
3. Analyze all players for week {week} using analyze_players (this combines both data sources with opponent matchup analysis)
4. Generate the optimal lineup using generate_optimal_lineup

After getting all the data, I want you to act as an expert fantasy analyst and provide:
- Your recommended starting lineup with rationale
- Key insights about player matchups based on historical vs current opponent data
- Risk assessment for each position
- Any lineup strategy recommendations (e.g., high-floor vs high-ceiling plays)

Use your expertise to analyze the data from the tools and provide strategic insights beyond just the raw numbers.
        """
        
        # Execute the workflow using the agent - this allows the AI to reason about the data
        result = agent(workflow_prompt)
        
        # Extract text from AgentResult object
        result_text = str(result)
        
        print(f"\n=== AI Fantasy Football Coach Analysis ===")
        print(result_text)
        
        # The agent will now provide AI reasoning and analysis, not just tool outputs
        
    except Exception as e:
        logger.error(f"Agent execution failed: {str(e)}")
        import traceback
        traceback.print_exc()

def print_formatted_lineup(lineup_json, week):
    """Print a nicely formatted lineup"""
    print(f"\n=== AI-Powered Lineup Recommendation for Week {week} ===")
    
    positions = [
        ("QB", lineup_json.get("QB")),
        ("RB1", lineup_json.get("RB1")), 
        ("RB2", lineup_json.get("RB2")),
        ("WR1", lineup_json.get("WR1")),
        ("WR2", lineup_json.get("WR2")),
        ("TE", lineup_json.get("TE")),
        ("FLEX", lineup_json.get("FLEX")),
        ("OP", lineup_json.get("OP")),
        ("D/ST", lineup_json.get("DST")),
        ("K", lineup_json.get("K"))
    ]
    
    for pos_name, player_name in positions:
        if player_name and player_name != "None":
            print(f"{pos_name:5}: {player_name}")
        else:
            print(f"{pos_name:5}: {'None'}")
    
    if lineup_json.get("projected_total"):
        print(f"\nProjected Total: {lineup_json.get('projected_total')} points")
    
    if lineup_json.get("rationale"):
        print(f"\nAI Rationale: {lineup_json.get('rationale')}")
    
    if lineup_json.get("key_plays"):
        print(f"\nHigh Confidence Plays: {', '.join(lineup_json.get('key_plays'))}")
    
    if lineup_json.get("risky_plays"):
        print(f"Boom/Bust Candidates: {', '.join(lineup_json.get('risky_plays'))}")

if __name__ == "__main__":
    main()