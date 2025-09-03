# fantasy_tools.py

import boto3
import json
import logging
from strands import tool
from data_models import Player
from scrapers import FantasyProjectionScraper
from historical_data import HistoricalDataManager
from utils import _get_current_week_matchups, find_player_projection, get_bye_weeks, calculate_combined_player_score, validate_lineup_requirements

logger = logging.getLogger(__name__)

# Global instances
projection_scraper = FantasyProjectionScraper()
historical_manager = HistoricalDataManager()
roster_data = []
weekly_data = {}
analyzed_players = []

# AWS clients - only DynamoDB needed for roster data
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
roster_table = dynamodb.Table('fantasy-football-team-roster')

@tool
def load_roster(team_id: str) -> str:
    """Load team roster from DynamoDB database."""
    global roster_data
    try:
        response = roster_table.get_item(Key={'team_id': team_id})
        
        if 'Item' not in response:
            return f"Error: No roster found for team_id: {team_id}"
        
        roster_items = response['Item']['players']
        roster_data = []
        
        for player_data in roster_items:
            player = Player(
                player_id=player_data['player_id'],
                name=player_data['name'],
                position=player_data['position'],
                team=player_data['team']
            )
            roster_data.append(player)
        
        logger.info(f"Loaded {len(roster_data)} players from roster")
        return f"Successfully loaded {len(roster_data)} players from roster for team {team_id}"
        
    except Exception as e:
        error_msg = f"Error loading roster: {str(e)}"
        logger.error(error_msg)
        return error_msg

@tool
def gather_weekly_data(week: int) -> str:
    """Gather both historical data and current projections for the specified week."""
    global weekly_data
    try:
        logger.info(f"Gathering data for week {week}")
        
        # Load historical data from local files
        historical_data = historical_manager.load_historical_data()
        
        # Scrape current week projections
        projections = projection_scraper.scrape_all_projections(week)
        
        # Scrape injury report
        injuries = projection_scraper.scrape_injury_report()
        
        # Get 2025 bye weeks
        bye_weeks_dict = get_bye_weeks()
        
        weekly_data = {
            'projections': projections,
            'historical_data': historical_data,
            'injuries': injuries,
            'bye_weeks': bye_weeks_dict.get(week, []),
            'current_week': week
        }
        
        total_projections = sum(len(pos_proj) for pos_proj in projections.values())
        total_historical = sum(len(pos_data.get('players', {})) for pos_data in historical_data.values())
        
        return f"Successfully gathered data for week {week}: {total_projections} current projections, {total_historical} players with historical data, {len(injuries)} injury reports, bye teams: {weekly_data['bye_weeks']}"
        
    except Exception as e:
        error_msg = f"Error gathering weekly data: {str(e)}"
        logger.error(error_msg)
        return error_msg

@tool
def analyze_players(week: int) -> str:
    """Analyze all players combining historical performance with current projections."""
    global analyzed_players, roster_data, weekly_data
    try:
        if not roster_data:
            return "Error: No roster loaded. Please load roster first."
        
        if not weekly_data:
            return "Error: No weekly data available. Please gather weekly data first."
        
        analyzed_players = []
        available_count = 0
        
        # Get current week matchups
        current_matchups = _get_current_week_matchups(week)
        
        analysis_summary = []
        analysis_summary.append(f"\n=== PLAYER ANALYSIS FOR WEEK {week} ===")
        analysis_summary.append("-" * 80)
        
        for player in roster_data:
            # Check bye week and injury status
            player.bye_week = player.team in weekly_data['bye_weeks']
            player.injury_status = weekly_data['injuries'].get(player.name, "Healthy")
            player.is_playing = not player.bye_week and player.injury_status not in ['Out', 'Doubtful']
            
            # Get opponent for this week
            player.opponent = current_matchups.get(player.team, "")
            
            # Get current week projections
            position_projections = weekly_data['projections'].get(player.position, {})
            player.projected_points = find_player_projection(player.name, position_projections)
            
            # Get comprehensive historical stats
            historical_stats = historical_manager.get_player_stats(player.name, player.position, week, player.opponent)
            player.past_performance = historical_stats
            
            # Set enhanced player metrics
            if historical_stats:
                player.season_average = historical_stats.get('season_average', 0.0)
                player.last_3_weeks_avg = historical_stats.get('recent_average', 0.0)
                player.consistency_score = historical_stats.get('consistency_score', 0.0)
                player.trend = historical_stats.get('trend', 'Unknown')
                player.vs_opponent_avg = historical_stats.get('vs_opponent_avg', 0.0)
                player.vs_opponent_games = historical_stats.get('vs_opponent_games', 0)
                
                # Enhanced matchup rating based on trend and consistency
                player.matchup_rating = _calculate_matchup_rating(player, historical_stats)
            else:
                player.season_average = 0.0
                player.last_3_weeks_avg = 0.0
                player.consistency_score = 0.0
                player.trend = "No Data"
                player.vs_opponent_avg = 0.0
                player.vs_opponent_games = 0
                player.matchup_rating = "No Data"
            
            # Create detailed player summary
            status_icon = "✅" if player.is_playing else "❌"
            injury_text = f" ({player.injury_status})" if player.injury_status != "Healthy" else ""
            bye_text = " (BYE)" if player.bye_week else ""
            
            # Format opponent history
            if player.vs_opponent_games > 0:
                vs_opp_text = f"vs {player.opponent}: {player.vs_opponent_avg:.1f} avg ({player.vs_opponent_games} games)"
                # Add comparison to season average
                if player.season_average > 0:
                    diff = player.vs_opponent_avg - player.season_average
                    if diff > 0:
                        vs_opp_text += f" [+{diff:.1f} vs season avg]"
                    elif diff < 0:
                        vs_opp_text += f" [{diff:.1f} vs season avg]"
            else:
                vs_opp_text = f"vs {player.opponent}: No historical data" if player.opponent else "No opponent data"
            
            player_line = (
                f"{status_icon} {player.name:<20} ({player.position:<2}) | "
                f"Proj: {player.projected_points:>5.1f} | "
                f"Season: {player.season_average:>5.1f} | "
                f"Recent: {player.last_3_weeks_avg:>5.1f} | "
                f"Trend: {player.trend:<12} | "
                f"{vs_opp_text}"
                f"{injury_text}{bye_text}"
            )
            
            analysis_summary.append(player_line)
            
            analyzed_players.append(player)
            if player.is_playing:
                available_count += 1
            
            logger.info(f"{player.name}: Playing={player.is_playing}, Proj={player.projected_points:.1f}, Season={player.season_average:.1f}, Recent={player.last_3_weeks_avg:.1f}, vs {player.opponent}: {player.vs_opponent_avg:.1f}")
        
        analysis_summary.append("-" * 80)
        analysis_summary.append(f"SUMMARY: {len(analyzed_players)} total players, {available_count} available to play")
        
        # Return the detailed analysis
        detailed_analysis = "\n".join(analysis_summary)
        
        return f"Analyzed {len(analyzed_players)} players. {available_count} available to play in week {week}.\n{detailed_analysis}"
        
    except Exception as e:
        error_msg = f"Error analyzing players: {str(e)}"
        logger.error(error_msg)
        return error_msg

@tool
def generate_optimal_lineup() -> str:
    """Generate optimal lineup recommendation based on analyzed player data.
    
    Returns:
        JSON string containing comprehensive lineup analysis for the AI agent to reason about
    """
    global analyzed_players
    try:
        if not analyzed_players:
            return "Error: No analyzed players available. Please analyze players first."
        
        # Filter available players
        available_players = [p for p in analyzed_players if p.is_playing]
        
        # Validate lineup requirements
        is_valid, error_msg = validate_lineup_requirements(available_players)
        if not is_valid:
            return f"Error: {error_msg}"
        
        # Create comprehensive player summary for the agent to analyze
        player_analysis = []
        for player in available_players:
            trend_info = ""
            if player.past_performance:
                trend = player.past_performance.get('trend', 'Unknown')
                trend_info = f" (Trend: {trend})"
            
            opponent_info = ""
            if player.vs_opponent_games > 0:
                diff = player.vs_opponent_avg - player.season_average
                opponent_info = f" vs {player.opponent}: {player.vs_opponent_avg:.1f} avg in {player.vs_opponent_games} games"
                if diff > 0:
                    opponent_info += f" [+{diff:.1f} above season avg]"
                elif diff < 0:
                    opponent_info += f" [{diff:.1f} below season avg]"
            
            player_summary = (
                f"{player.name} ({player.position}): "
                f"Proj={player.projected_points:.1f}, "
                f"Season={player.season_average:.1f}, "
                f"Recent={player.last_3_weeks_avg:.1f}, "
                f"Consistency={player.consistency_score:.0f}/100"
                f"{trend_info}"
                f"{opponent_info}"
                f" [{player.matchup_rating} matchup]"
            )
            
            if player.injury_status != "Healthy":
                player_summary += f" ({player.injury_status})"
            
            player_analysis.append(player_summary)
        
        # Sort players by position for easier analysis
        qbs = [p for p in available_players if p.position == 'QB']
        rbs = [p for p in available_players if p.position == 'RB']
        wrs = [p for p in available_players if p.position == 'WR']
        tes = [p for p in available_players if p.position == 'TE']
        dsts = [p for p in available_players if p.position == 'DST']
        ks = [p for p in available_players if p.position == 'K']
        
        # Generate smart lineup recommendation for baseline
        baseline_recommendation = _create_smart_lineup_recommendation(qbs, rbs, wrs, tes, dsts, ks)
        
        # Create detailed analysis summary for the AI agent
        analysis_summary = {
            "baseline_lineup": baseline_recommendation,
            "detailed_player_analysis": player_analysis,
            "lineup_requirements": "QB(1), RB(2), WR(2), TE(1), FLEX(1: RB/WR/TE), OP(1: Any offensive), DST(1), K(1)",
            "total_available_players": len(available_players),
            "position_breakdown": {
                "QB": f"{len(qbs)} available - {[p.name for p in sorted(qbs, key=calculate_combined_player_score, reverse=True)[:3]]}",
                "RB": f"{len(rbs)} available - Top 5: {[p.name for p in sorted(rbs, key=calculate_combined_player_score, reverse=True)[:5]]}",
                "WR": f"{len(wrs)} available - Top 5: {[p.name for p in sorted(wrs, key=calculate_combined_player_score, reverse=True)[:5]]}",
                "TE": f"{len(tes)} available - {[p.name for p in sorted(tes, key=calculate_combined_player_score, reverse=True)[:3]]}",
                "DST": f"{len(dsts)} available",
                "K": f"{len(ks)} available"
            },
            "key_insights": _generate_key_insights(available_players),
            "strategy_considerations": {
                "high_floor_plays": [p.name for p in available_players if p.consistency_score > 75 and p.is_playing][:5],
                "high_ceiling_plays": [p.name for p in available_players if p.trend == "Trending up" and p.last_3_weeks_avg > p.season_average * 1.2][:5],
                "favorable_matchups": [p.name for p in available_players if p.vs_opponent_games > 0 and p.vs_opponent_avg > p.season_average * 1.1][:5],
                "injury_concerns": [f"{p.name} ({p.injury_status})" for p in available_players if p.injury_status in ["Questionable", "Probable"]]
            }
        }
        
        return json.dumps(analysis_summary, indent=2)
        
    except Exception as e:
        logger.error(f"Error generating lineup: {str(e)}")
        return f'{{"error": "{str(e)}"}}'



def _calculate_matchup_rating(player: Player, stats: dict) -> str:
    """Calculate matchup rating based on multiple factors"""
    score = 50  # Base score
    
    # Boost for good recent form
    if stats.get('recent_average', 0) > stats.get('season_average', 0) * 1.1:
        score += 15
    
    # Boost for trending up
    if stats.get('trend') == 'Trending up':
        score += 10
    elif stats.get('trend') == 'Trending down':
        score -= 10
    
    # Boost for high consistency
    consistency = stats.get('consistency_score', 0)
    if consistency > 70:
        score += 10
    elif consistency < 40:
        score -= 5
    
    # Boost for good opponent history
    if stats.get('vs_opponent_games', 0) > 0:
        vs_opp_avg = stats.get('vs_opponent_avg', 0)
        season_avg = stats.get('season_average', 0)
        if vs_opp_avg > season_avg * 1.2:
            score += 15
        elif vs_opp_avg < season_avg * 0.8:
            score -= 10
    
    # Convert to rating
    if score >= 75:
        return "Excellent"
    elif score >= 60:
        return "Good"
    elif score <= 35:
        return "Poor"
    else:
        return "Average"

def _create_smart_lineup_recommendation(qbs, rbs, wrs, tes, dsts, ks):
    """Create intelligent lineup recommendation using combined scoring"""
    
    def get_player_score(player):
        """Calculate comprehensive player score"""
        return calculate_combined_player_score(player)
    
    # Sort all position groups by score
    qbs_sorted = sorted(qbs, key=get_player_score, reverse=True)
    rbs_sorted = sorted(rbs, key=get_player_score, reverse=True)
    wrs_sorted = sorted(wrs, key=get_player_score, reverse=True)
    tes_sorted = sorted(tes, key=get_player_score, reverse=True)
    dsts_sorted = sorted(dsts, key=lambda x: x.projected_points, reverse=True)
    ks_sorted = sorted(ks, key=lambda x: x.projected_points, reverse=True)
    
    # Build core lineup
    lineup = {}
    used_players = set()
    
    # Required positions
    lineup["QB"] = qbs_sorted[0].name if qbs_sorted else "None"
    if qbs_sorted:
        used_players.add(qbs_sorted[0].name)
    
    lineup["RB1"] = rbs_sorted[0].name if len(rbs_sorted) > 0 else "None"
    lineup["RB2"] = rbs_sorted[1].name if len(rbs_sorted) > 1 else "None"
    if len(rbs_sorted) > 0:
        used_players.add(rbs_sorted[0].name)
    if len(rbs_sorted) > 1:
        used_players.add(rbs_sorted[1].name)
    
    lineup["WR1"] = wrs_sorted[0].name if len(wrs_sorted) > 0 else "None"
    lineup["WR2"] = wrs_sorted[1].name if len(wrs_sorted) > 1 else "None"
    if len(wrs_sorted) > 0:
        used_players.add(wrs_sorted[0].name)
    if len(wrs_sorted) > 1:
        used_players.add(wrs_sorted[1].name)
    
    lineup["TE"] = tes_sorted[0].name if tes_sorted else "None"
    if tes_sorted:
        used_players.add(tes_sorted[0].name)
    
    # FLEX position (best remaining RB/WR/TE)
    flex_candidates = []
    flex_candidates.extend([p for p in rbs_sorted[2:] if p.name not in used_players])
    flex_candidates.extend([p for p in wrs_sorted[2:] if p.name not in used_players])
    flex_candidates.extend([p for p in tes_sorted[1:] if p.name not in used_players])
    flex_candidates.sort(key=get_player_score, reverse=True)
    
    lineup["FLEX"] = flex_candidates[0].name if flex_candidates else "None"
    if flex_candidates:
        used_players.add(flex_candidates[0].name)
    
    # OP position (any offensive player, including QB)
    op_candidates = []
    op_candidates.extend([p for p in qbs_sorted[1:] if p.name not in used_players])
    op_candidates.extend([p for p in flex_candidates[1:] if p.name not in used_players])
    op_candidates.sort(key=get_player_score, reverse=True)
    
    lineup["OP"] = op_candidates[0].name if op_candidates else "None"
    if op_candidates:
        used_players.add(op_candidates[0].name)
    
    lineup["DST"] = dsts_sorted[0].name if dsts_sorted else "None"
    lineup["K"] = ks_sorted[0].name if ks_sorted else "None"
    
    # Calculate projected total
    all_lineup_players = []
    for pos_group in [qbs_sorted, rbs_sorted, wrs_sorted, tes_sorted, flex_candidates, op_candidates, dsts_sorted, ks_sorted]:
        for player in pos_group:
            if player.name in lineup.values() and player not in all_lineup_players:
                all_lineup_players.append(player)
    
    projected_total = sum([get_player_score(p) for p in all_lineup_players[:10]])
    
    lineup.update({
        "rationale": "Baseline smart lineup using combined projection + historical analysis",
        "projected_total": f"{projected_total:.1f}",
    })
    
    return lineup

def _generate_key_insights(available_players):
    """Generate key insights about the available players"""
    insights = []
    
    # Hot players
    hot_players = [p for p in available_players if p.trend == "Trending up" and p.last_3_weeks_avg > p.season_average * 1.15]
    if hot_players:
        insights.append(f"Hot players to consider: {', '.join([p.name for p in hot_players[:3]])}")
    
    # Favorable matchups
    good_matchups = [p for p in available_players if p.vs_opponent_games > 0 and p.vs_opponent_avg > p.season_average * 1.2]
    if good_matchups:
        insights.append(f"Players with historically strong matchups: {', '.join([p.name for p in good_matchups[:3]])}")
    
    # Consistency plays
    consistent_players = [p for p in available_players if p.consistency_score > 80]
    if consistent_players:
        insights.append(f"Most consistent (safe floor) options: {', '.join([p.name for p in consistent_players[:3]])}")
    
    # Risk factors
    risky_players = [p for p in available_players if p.injury_status == "Questionable" or p.trend == "Trending down"]
    if risky_players:
        risk_descriptions = []
        for p in risky_players[:3]:
            risk_reason = p.injury_status if p.injury_status != "Healthy" else "trending down"
            risk_descriptions.append(f"{p.name} ({risk_reason})")
        insights.append(f"Players with elevated risk: {', '.join(risk_descriptions)}")
    
    return insights if insights else ["Standard lineup optimization based on projections and historical data"]