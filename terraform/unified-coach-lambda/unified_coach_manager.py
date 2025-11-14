"""
Unified Fantasy Football Coach - Combines lineup optimization + conversational analysis
Automatically generates optimal lineup first, then enables follow-up questions
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from strands import Agent
from strands.models import BedrockModel

# Import lineup optimization
from app.projections import create_unified_projections
from app.lineup import optimize_lineup_direct
from app.player_data import load_roster_player_data

# Import chat capabilities
from dynamodb_client import DynamoDBClient
from fantasy_tools import (
    initialize_fantasy_tools,
    analyze_player_performance,
    compare_roster_players,
    analyze_injury_impact,
    analyze_waiver_opportunities_with_projections,
    get_position_waiver_targets
)
from depth_charts import get_team_depth_chart

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


SYSTEM_PROMPT = """You are an elite Fantasy Football Coach combining Dan Campbell's intensity with data-driven optimization.

Your PRIMARY mission: Generate the optimal Week {week} lineup for Team ID {team_id} automatically, then provide conversational follow-up analysis.

CURRENT CONTEXT:
- Team ID: {team_id}
- Week: {week}

═══════════════════════════════════════════════════════════════
WORKFLOW (AUTOMATIC)
═══════════════════════════════════════════════════════════════

**On FIRST message from user:**
1. Automatically call optimize_weekly_lineup(team_id="{team_id}", week={week}) - NO user prompt needed
2. Present the optimized lineup in a clear, motivational way (Dan Campbell style)
3. Highlight key decisions (OP slot strategy, FLEX choice, injury concerns)
4. **ALWAYS show TOP 5-10 BENCH players** with their projections and injury status
5. Flag any injury concerns (Out, IR, Doubtful, Questionable) in both lineup and bench
6. Then ask: "What questions do you have about this lineup?"

**On FOLLOW-UP messages:**
- Answer questions about players, matchups, alternatives
- Provide waiver wire suggestions
- Compare start/sit options
- Analyze injuries and depth charts

═══════════════════════════════════════════════════════════════
YOUR CAPABILITIES
═══════════════════════════════════════════════════════════════

**Lineup Optimization:**
- optimize_weekly_lineup(team_id, week) → Generate optimal lineup automatically

**Player Analysis:**
- analyze_player_performance(player_name) → Deep dive on any player
- compare_roster_players(player1, player2) → Start/sit decisions
- get_team_depth_chart(team, position) → Verify starter status, QB-WR connections

**Roster Management:**
- analyze_injury_impact(team_id) → Identify injury concerns
- analyze_waiver_opportunities_with_projections() → Smart add/drop suggestions
- get_position_waiver_targets(position) → Find waiver gems

═══════════════════════════════════════════════════════════════
LINEUP PHILOSOPHY
═══════════════════════════════════════════════════════════════

**OP Slot Strategy (CRITICAL):**
- DEFAULT: Start QB2 in OP (QBs average 18-25 pts vs RBs 10-15 pts)
- Only use RB/WR if: QB2 injured/bye AND RB projects 18+ points
- Always explain your OP slot decision

**Key Principles (HARD CONSTRAINTS - NEVER VIOLATE):**
- ✗ NEVER start players on BYE (opponent = "BYE")
- ✗ NEVER start players with injury_status = "Out" or "IR"
- ✗ NEVER start players with injury_status = "Doubtful" (50% chance to play)
- ⚠️ BE CAUTIOUS with "Questionable" players - only start if no better healthy option
- ✓ Prioritize projected points over big names
- ✓ Consider matchups and game scripts
- ✓ Bench low-projected starters (<8 pts)

═══════════════════════════════════════════════════════════════
PERSONALITY (Dan Campbell)
═══════════════════════════════════════════════════════════════

You embody Dan Campbell's coaching style:
- Aggressive, confident, motivational
- "We're here to bite kneecaps" mentality
- Passionate about winning
- Direct and honest, no sugarcoating
- Uses football vernacular naturally

Example responses:
- "Listen, we're starting Josh Allen at OP because he's throwing for 300+ yards. That's how you bite kneecaps."
- "Your RB situation? We're riding the hot hand. McCaffrey's getting 25 touches, period."
- "Waiver wire time. We're attacking this like a blitz package - fast and aggressive."

═══════════════════════════════════════════════════════════════
IMPORTANT REMINDERS
═══════════════════════════════════════════════════════════════

1. Call optimize_weekly_lineup() FIRST on every new conversation
2. Present lineup results clearly with total projected points
3. **ALWAYS include bench players (top 5-10) with projections and injury status**
4. **Check injury_status field for EVERY player - flag Out/IR/Doubtful/Questionable**
5. Explain key decisions (especially OP slot and injury replacements)
6. Be ready for follow-up questions
7. Use tools to back up your analysis
8. Stay in Dan Campbell character throughout
"""


class UnifiedCoachManager:
    """Manages unified coaching: lineup optimization + conversational analysis"""

    def __init__(self):
        self.db_client = DynamoDBClient()
        initialize_fantasy_tools(self.db_client)

        # Initialize Bedrock model
        bedrock_model = BedrockModel(
            model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
            max_tokens=1500,  # Reduced from 4000 - lineup responses typically 800-1200 tokens
            temperature=0.1,
            stream=False
        )

        # Define lineup slots
        self.lineup_slots = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "OP", "K", "DST"]

        # Initialize tools - include lineup optimizer
        self.tools = [
            self._create_lineup_optimizer_tool(),
            analyze_player_performance,
            compare_roster_players,
            analyze_injury_impact,
            analyze_waiver_opportunities_with_projections,
            get_position_waiver_targets,
            get_team_depth_chart
        ]

        # Agent will be created per-message with updated context
        self.bedrock_model = bedrock_model
        logger.info("UnifiedCoachManager initialized")

    def _create_lineup_optimizer_tool(self):
        """Create the lineup optimization tool"""
        from strands import tool

        @tool
        def optimize_weekly_lineup(team_id: str, week: int) -> Dict[str, Any]:
            """Generate optimized fantasy lineup for the week.

            This tool automatically analyzes your entire roster and generates the optimal
            starting lineup based on projections, matchups, and injury status.

            Args:
                team_id: Your fantasy team ID
                week: NFL week number (1-18)

            Returns:
                Optimized lineup with starters, bench, and projected points
            """
            try:
                # Load roster
                roster_data = self.db_client.get_team_roster(team_id)
                if not roster_data:
                    return {"error": f"Roster not found for team {team_id}"}

                roster_players = roster_data.get("players", [])

                # Load comprehensive player data
                unified_player_data = load_roster_player_data(roster_players)

                # Create weekly projections
                projections_data = create_unified_projections(roster_players, week)

                # Optimize lineup
                result = optimize_lineup_direct(
                    self.lineup_slots,
                    roster_players,
                    projections_data
                )

                result['week'] = week
                result['team_id'] = team_id
                result['team_name'] = roster_data.get('team_name', 'Your Team')

                return result

            except Exception as e:
                logger.error(f"Error optimizing lineup: {str(e)}")
                return {"error": f"Lineup optimization failed: {str(e)}"}

        return optimize_weekly_lineup

    def process_message(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process user message with unified coaching"""
        try:
            team_id = context.get('team_id', '7')
            week = context.get('week', 11)

            # Generate session ID
            session_id = f"{team_id}_{datetime.utcnow().strftime('%Y%m%d')}"

            # Store user message in NEW unified chat history table
            self._store_message(session_id, message, "user", context)

            # Build context-aware system prompt
            system_prompt = SYSTEM_PROMPT.format(week=week, team_id=team_id)

            # Create agent with current context
            agent = Agent(
                model=self.bedrock_model,
                system_prompt=system_prompt,
                tools=self.tools
            )

            # Get AI response
            response = agent(message)

            # Extract response content
            if hasattr(response, 'content'):
                response_text = response.content
            elif isinstance(response, str):
                response_text = response
            else:
                response_text = str(response)

            # Store AI response
            self._store_message(session_id, response_text, "assistant", context)

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "response": response_text,
                    "session_id": session_id,
                    "week": week,
                    "team_id": team_id
                })
            }

        except Exception as e:
            logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return {
                "statusCode": 500,
                "body": json.dumps({"error": str(e)})
            }

    def _store_message(self, session_id: str, message: str, sender: str, context: Dict[str, Any]):
        """Store message in NEW unified chat history table"""
        try:
            table_name = os.environ.get('UNIFIED_CHAT_HISTORY_TABLE', 'fantasy-football-unified-chat-history')
            dynamodb = self.db_client.dynamodb

            table = dynamodb.Table(table_name)

            timestamp = datetime.utcnow().isoformat()
            expires_at = int((datetime.utcnow() + timedelta(days=7)).timestamp())

            item = {
                'session_id': session_id,
                'timestamp': timestamp,
                'message': message,
                'sender': sender,
                'team_id': context.get('team_id', 'unknown'),
                'week': context.get('week', 'unknown'),
                'expires_at': expires_at
            }

            table.put_item(Item=item)
            logger.debug(f"Stored {sender} message for session: {session_id}")

        except Exception as e:
            logger.error(f"Error storing message: {str(e)}")


# Global instance
unified_coach = None


def get_unified_coach():
    """Get or create unified coach instance"""
    global unified_coach
    if unified_coach is None:
        unified_coach = UnifiedCoachManager()
    return unified_coach
