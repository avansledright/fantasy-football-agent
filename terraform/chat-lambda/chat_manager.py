"""
Chat Manager for Fantasy Football Bot
Handles message processing and Strands SDK integration
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List
import os 

from strands import Agent
from strands.models import BedrockModel

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
from utils import store_chat_message, generate_session_id

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Fantasy Football AI Coach assistant. You help users make informed decisions about their fantasy football teams using real data and analysis.

You embody all of Dan Campbell's mannerisms and vernacular. Only speak as if you are Dan Campbell.

Your capabilities include:
- Looking up any NFL player's current team, stats, and depth chart position
- Analyzing team rosters and player performance
- Providing start/sit recommendations
- Suggesting waiver wire pickups and comparing them to current roster
- Comparing player matchups
- Optimizing lineups
- Tracking injury reports
- Analyzing historical trends and projections
- Checking NFL team depth charts to verify QB-WR connections, backup RBs, and starter status

You have access to the user's current roster information in your context. When making waiver wire recommendations, always compare against their current players to suggest specific adds/drops.

Always provide specific, data-driven advice when possible. Use the available tools to access player stats, projections, and waiver wire data. Be conversational but informative, and always explain your reasoning. Just because a player has higher ownership doesn't mean he isn't available. Projections should be higher in your consideration.

When discussing players, include relevant context like:
- Recent performance trends
- Matchup difficulty
- Injury status
- Projected points
- Ownership percentages (for waiver pickups)
- How they compare to current roster players

Key Guidelines:
1. Use the current roster information provided in your context - no need to call tools for roster data
2. Always compare waiver options against current roster players
3. Provide actionable recommendations with clear reasoning
4. Consider both short-term (weekly) and long-term (season-long) implications
5. Be honest about uncertainty when projections are unclear
6. Keep responses focused and practical for fantasy managers
7. Be sure to analyze current player stats for waiver pickups
8. A player or team who is on BYE should NEVER be considered for a waiver pickup
9. When asked about a specific player (e.g., "Who is Jameis Winston playing for?", "Tell me about Patrick Mahomes"):
   - First use analyze_player_performance(player_name) to get their team, stats, and current situation
   - Then use get_team_depth_chart(team, position) to show their depth chart position and context
   - Provide comprehensive info: current team, role (starter/backup), recent performance, and fantasy relevance
10. Use get_team_depth_chart to verify QB-WR connections (WR value depends on QB quality), check RB backup situations, or confirm starter status
"""

class ChatManager:
    """Manages chat conversations and AI responses"""
    
    def __init__(self):
        self.db_client = DynamoDBClient()
        self.fantasy_tools = initialize_fantasy_tools(self.db_client)
        
        # Initialize Bedrock model
        bedrock_model = BedrockModel(
            model_id=os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-20250514-v1:0"),
            max_tokens=4000,
            temperature=0.0,
            stream=False
        )
        
        # Initialize Strands Agent with tools
        self.agent = Agent(
            model=bedrock_model,
            system_prompt=SYSTEM_PROMPT,
            tools=[
                analyze_player_performance,
                compare_roster_players,
                analyze_injury_impact,
                analyze_waiver_opportunities_with_projections,
                get_position_waiver_targets,
                get_team_depth_chart
            ]
        )
        if hasattr(self, 'fantasy_tools') and self.fantasy_tools:
            # Context will be updated per request in process_message
            pass
        logger.info("ChatManager initialized with Strands SDK")
    
    def process_message(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming chat message and generate response"""
        try:
            # Generate session ID
            session_id = generate_session_id(context)
            
            # Store user message
            store_chat_message(
                self.db_client, 
                session_id, 
                message, 
                'user', 
                context
            )
            if self.fantasy_tools:
                prepared_context = self._prepare_tool_context(context)
                self.fantasy_tools.update_context(prepared_context)
            
            # Get chat history for context
            chat_history = self._get_chat_history(session_id)
            
            # Build enhanced system prompt with context
            enhanced_prompt = self._build_enhanced_prompt(context)
            
            # Prepare conversation for Strands
            conversation = self._build_conversation(message, chat_history, context)
            
            # Generate AI response using Strands
            ai_response = self._generate_strands_response(
                conversation, 
                enhanced_prompt, 
                context
            )
            
            # Store AI response
            store_chat_message(
                self.db_client, 
                session_id, 
                ai_response, 
                'assistant', 
                context
            )
            
            return {
                'message': ai_response,
                'session_id': session_id,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {
                'message': self._generate_fallback_response(message, context),
                'session_id': generate_session_id(context),
                'timestamp': datetime.utcnow().isoformat(),
                'error': True
            }
    
    def _build_enhanced_prompt(self, context: Dict[str, Any]) -> str:
        """Build enhanced system prompt with current context"""
        team_id = context.get('team_id', 'your team')
        week = context.get('week', 'current week')
        league_name = context.get('league_name', 'your league')
        
        # Extract current roster information from context
        roster_info = ""
        if context.get('current_team', {}).get('players'):
            players = context['current_team']['players']
            
            # Organize by position and status
            starters = [p for p in players if p.get('status') == 'starter']
            bench = [p for p in players if p.get('status') == 'bench']
            
            roster_info = f"""
    Current Roster Information:
    STARTERS:
    """
            for player in starters:
                roster_info += f"- {player.get('name')} ({player.get('position')}) - {player.get('team')} - Slot: {player.get('slot')} - Status: {player.get('injury_status')}\n"
            
            roster_info += "\nBENCH:\n"
            for player in bench:
                roster_info += f"- {player.get('name')} ({player.get('position')}) - {player.get('team')} - Status: {player.get('injury_status')}\n"

        enhanced_prompt = f"""{SYSTEM_PROMPT}

    Current Context:
    - Team ID: {team_id}
    - Week: {week}
    - League: {league_name}
    - Season: 2025

    {roster_info}

    IMPORTANT: You have direct access to the user's current roster information above. Use this roster data to make comparisons with waiver wire recommendations. You do NOT need to call additional tools to get roster information - it's provided in your context.

    When providing waiver wire advice, compare the available players against the current roster players shown above, especially focusing on:
    1. Bench players who could be dropped
    2. Positional needs based on current starters
    3. Injury replacements needed
    4. Upgrade opportunities over current players
    """
        return enhanced_prompt
    def _prepare_tool_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare context for tool usage"""
        tool_context = context.copy()
        
        # Ensure week is properly formatted
        if 'week' in tool_context:
            try:
                tool_context['week'] = str(int(tool_context['week']))
            except (ValueError, TypeError):
                tool_context['week'] = '1'
        else:
            tool_context['week'] = '1'
        
        return tool_context
    def _build_conversation(self, message: str, chat_history: List[Dict], context: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build conversation history for Strands"""
        conversation = []
        
        # Add recent chat history (limit to last 10 messages for context)
        recent_history = chat_history[-10:] if len(chat_history) > 10 else chat_history
        
        for msg in reversed(recent_history):  # Reverse to get chronological order
            role = "user" if msg['sender'] == 'user' else "assistant"
            conversation.append({
                "role": role,
                "content": msg['message']
            })
        
        # Add current message
        conversation.append({
            "role": "user",
            "content": message
        })
        
        return conversation
    
    def _generate_strands_response(self, conversation: List[Dict[str, str]], system_prompt: str, context: Dict[str, Any]) -> str:
        """Generate response using Strands SDK"""
        try:
            # Update agent's system prompt for this conversation
            self.agent.system_prompt = system_prompt
            
            # Get the latest user message
            user_message = conversation[-1]['content']
            
            # Add context information to the user message if it contains roster references
            if any(word in user_message.lower() for word in ['compare', 'roster', 'lineup', 'current', 'my team']):
                context_note = f"\n\n[Context: User has team {context.get('team_id')} in week {context.get('week')}. Current roster information is provided in the system prompt above.]"
                user_message += context_note
            
            # Generate response using Strands Agent
            response = self.agent(user_message)
            
            # Extract the response content
            if hasattr(response, 'content'):
                return response.content
            elif isinstance(response, str):
                return response
            else:
                return str(response)
            
        except Exception as e:
            logger.error(f"Error generating Strands response: {str(e)}")
            return self._generate_fallback_response(conversation[-1]['content'], context)
    
    def _generate_fallback_response(self, message: str, context: Dict[str, Any]) -> str:
        """Generate a fallback response when Strands fails"""
        message_lower = message.lower()
        team_id = context.get('team_id', 'your team')
        
        if any(word in message_lower for word in ['roster', 'lineup', 'team']):
            return f"I can help you analyze your Team {team_id} roster and suggest optimal lineups. Let me gather your current roster information and provide recommendations."
        
        elif any(word in message_lower for word in ['waiver', 'pickup', 'add']):
            return f"I can help you find the best waiver wire pickups for Team {team_id}. What positions are you looking to improve?"
        
        elif any(word in message_lower for word in ['start', 'sit', 'bench']):
            return f"I can help you make start/sit decisions for Team {team_id}. Which players are you considering?"
        
        elif any(word in message_lower for word in ['matchup', 'opponent']):
            return f"I can analyze matchups for your Team {team_id} players. What specific matchups are you concerned about?"
        
        elif any(word in message_lower for word in ['injury', 'hurt', 'injured']):
            return f"I can check injury reports for your Team {team_id} players. Let me get the latest injury information."
        
        elif any(word in message_lower for word in ['projection', 'points', 'score']):
            return f"I can provide player projections and scoring analysis for Team {team_id}. Which players are you interested in?"
        
        else:
            return f"I'm your Fantasy Football AI Coach for Team {team_id}. I can help with roster analysis, start/sit decisions, waiver pickups, and matchup analysis. What would you like to know?"
    
    def _get_chat_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get recent chat history"""
        try:
            return self.db_client.get_chat_history(session_id, limit)
        except Exception as e:
            logger.error(f"Error retrieving chat history: {str(e)}")
            return []
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the chat manager"""
        try:
            # Test database connection
            test_roster = self.db_client.get_team_roster("test")
            db_status = "healthy"
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            db_status = "unhealthy"
        
        return {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "components": {
                "database": db_status,
                "strands_agent": "healthy" if self.agent else "unhealthy",
                "fantasy_tools": "healthy" if self.fantasy_tools else "unhealthy"
            },
            "timestamp": datetime.utcnow().isoformat()
        }