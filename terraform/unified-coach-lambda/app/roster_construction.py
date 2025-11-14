# app/roster_construction.py
"""
Roster construction analysis for smart waiver wire recommendations.
"""

from typing import Dict, List, Any, Set
from strands import tool

# League roster requirements
LEAGUE_ROSTER_REQUIREMENTS = {
    "QB": {"starters": 1, "maximum": 4},
    "RB": {"starters": 2, "maximum": 8}, 
    "WR": {"starters": 2, "maximum": 8},
    "TE": {"starters": 1, "maximum": 3},
    "K": {"starters": 1, "maximum": 3},
    "DST": {"starters": 1, "maximum": 3},
    "FLEX": {"starters": 1, "eligible": ["RB", "WR", "TE"]},
    "OP": {"starters": 1, "eligible": ["QB", "RB", "WR", "TE"]},
    "BENCH": {"maximum": 8}
}

def analyze_roster_construction(current_roster: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze current roster construction and identify positional needs."""
    
    # Group players by position and health status
    position_analysis = {}
    
    for position in ["QB", "RB", "WR", "TE", "K", "DST"]:
        players_at_position = [p for p in current_roster if p.get("position") == position]
        
        healthy_players = []
        injured_players = []
        questionable_players = []
        
        for player in players_at_position:
            injury_status = player.get("injury_status", "Healthy")
            if injury_status in ["Healthy", "ACTIVE"]:
                healthy_players.append(player)
            elif injury_status in ["Questionable"]:
                questionable_players.append(player)
            else:
                injured_players.append(player)
        
        # Calculate needs
        requirements = LEAGUE_ROSTER_REQUIREMENTS.get(position, {})
        starters_needed = requirements.get("starters", 0)
        maximum_allowed = requirements.get("maximum", 0)
        
        # Account for FLEX and OP eligibility
        effective_starters_needed = starters_needed
        if position in ["RB", "WR", "TE"]:
            effective_starters_needed += 1  # FLEX position
        if position in ["QB", "RB", "WR", "TE"]:
            effective_starters_needed += 1  # OP position
        
        # Determine priority level
        total_healthy = len(healthy_players)
        total_usable = len(healthy_players) + len(questionable_players)
        
        if total_healthy < starters_needed:
            priority = "CRITICAL"
            urgency_reason = f"Only {total_healthy} healthy, need {starters_needed} starters"
        elif total_usable < effective_starters_needed:
            priority = "HIGH" 
            urgency_reason = f"Need depth for flex/OP eligibility"
        elif total_healthy < effective_starters_needed:
            priority = "MEDIUM"
            urgency_reason = f"Questionable players create uncertainty"
        elif len(players_at_position) >= maximum_allowed:
            priority = "NONE"
            urgency_reason = f"At roster maximum ({maximum_allowed})"
        else:
            priority = "LOW"
            urgency_reason = "Adequate depth available"
        
        position_analysis[position] = {
            "total_players": len(players_at_position),
            "healthy_players": len(healthy_players),
            "injured_players": len(injured_players),
            "questionable_players": len(questionable_players),
            "starters_required": starters_needed,
            "effective_need": effective_starters_needed,
            "maximum_allowed": maximum_allowed,
            "priority": priority,
            "urgency_reason": urgency_reason,
            "healthy_player_names": [p.get("name") for p in healthy_players],
            "injured_player_names": [p.get("name") for p in injured_players],
            "questionable_player_names": [p.get("name") for p in questionable_players]
        }
    
    return position_analysis

def get_waiver_priority_positions(roster_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Get positions that should be prioritized for waiver wire additions."""
    
    priority_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    priority_positions = []
    
    for priority_level in priority_order:
        positions_at_level = []
        
        for position, analysis in roster_analysis.items():
            if analysis["priority"] == priority_level:
                positions_at_level.append({
                    "position": position,
                    "priority": priority_level,
                    "reason": analysis["urgency_reason"],
                    "healthy_count": analysis["healthy_players"],
                    "injured_count": analysis["injured_players"],
                    "total_count": analysis["total_players"],
                    "max_allowed": analysis["maximum_allowed"]
                })
        
        if positions_at_level:
            # Sort by severity within priority level
            positions_at_level.sort(key=lambda x: x["healthy_count"])
            priority_positions.extend(positions_at_level)
    
    return priority_positions

@tool
def analyze_roster_needs_for_waivers(
    current_roster: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Analyze roster construction to determine waiver wire priorities."""
    
    roster_analysis = analyze_roster_construction(current_roster)
    priority_positions = get_waiver_priority_positions(roster_analysis)
    
    # Separate into actionable vs non-actionable
    actionable_positions = [p for p in priority_positions if p["priority"] in ["CRITICAL", "HIGH", "MEDIUM"]]
    avoid_positions = [p for p in priority_positions if p["priority"] == "NONE"]
    
    return {
        "roster_breakdown": roster_analysis,
        "waiver_priorities": actionable_positions,
        "positions_to_avoid": avoid_positions,
        "total_roster_size": len(current_roster),
        "analysis": _generate_roster_analysis_summary(roster_analysis, actionable_positions, avoid_positions)
    }

def _generate_roster_analysis_summary(
    roster_analysis: Dict[str, Any], 
    actionable: List[Dict[str, Any]], 
    avoid: List[Dict[str, Any]]
) -> str:
    """Generate human-readable roster analysis summary."""
    
    summary_parts = []
    
    if actionable:
        summary_parts.append("WAIVER PRIORITIES:")
        for pos_info in actionable[:3]:  # Top 3 priorities
            summary_parts.append(
                f"- {pos_info['position']}: {pos_info['priority']} priority - {pos_info['reason']}"
            )
    
    if avoid:
        avoid_positions = [p["position"] for p in avoid]
        summary_parts.append(f"AVOID: {', '.join(avoid_positions)} (at roster limits)")
    
    # Add specific recommendations
    critical_positions = [p for p in actionable if p["priority"] == "CRITICAL"]
    if critical_positions:
        crit_pos = [p["position"] for p in critical_positions]
        summary_parts.append(f"IMMEDIATE ACTION NEEDED: {', '.join(crit_pos)}")
    
    return " | ".join(summary_parts)

@tool
def should_target_position_for_waiver(
    position: str,
    current_roster: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Determine if a specific position should be targeted for waiver pickup."""
    
    roster_analysis = analyze_roster_construction(current_roster)
    position_info = roster_analysis.get(position.upper(), {})
    
    if not position_info:
        return {
            "should_target": False,
            "reason": f"Position {position} not recognized",
            "priority": "NONE"
        }
    
    priority = position_info.get("priority", "NONE")
    should_target = priority in ["CRITICAL", "HIGH", "MEDIUM"]
    
    return {
        "should_target": should_target,
        "priority": priority,
        "reason": position_info.get("urgency_reason", ""),
        "current_healthy": position_info.get("healthy_players", 0),
        "current_total": position_info.get("total_players", 0),
        "max_allowed": position_info.get("maximum_allowed", 0),
        "recommendation": _get_position_recommendation(position_info)
    }

def _get_position_recommendation(position_info: Dict[str, Any]) -> str:
    """Get specific recommendation for a position."""
    
    priority = position_info.get("priority", "NONE")
    healthy = position_info.get("healthy_players", 0)
    total = position_info.get("total_players", 0)
    
    if priority == "CRITICAL":
        return f"MUST ADD - Only {healthy} healthy players"
    elif priority == "HIGH":
        return f"STRONGLY CONSIDER - Limited depth with {healthy} healthy"
    elif priority == "MEDIUM":
        return f"CONSIDER - Could use additional depth"
    elif priority == "LOW":
        return f"OPTIONAL - Adequate depth exists"
    else:
        return f"AVOID - At roster limit with {total} players"