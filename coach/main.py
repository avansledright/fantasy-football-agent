import boto3
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
import time
import re
import sys
from strands import Agent, tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class Player:
    """Represents a fantasy football player"""
    player_id: str
    name: str
    position: str
    team: str
    opponent: str = ""
    is_playing: bool = True
    bye_week: bool = False
    injury_status: str = "Healthy"
    projected_points: float = 0.0
    matchup_rating: str = ""
    past_performance: Dict = None

@dataclass
class LineupRecommendation:
    """Represents the recommended starting lineup"""
    qb: Player
    rb1: Player
    rb2: Player
    wr1: Player
    wr2: Player
    te: Player
    flex: Player
    op: Player
    defense: Player
    kicker: Player
    rationale: str

class FantasyDataScraper:
    """Handles all data scraping operations"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.position_urls = {
            'QB': 'qb', 'RB': 'rb', 'WR': 'wr', 'TE': 'te', 'K': 'k', 'DST': 'dst'
        }
        
    def scrape_all_position_projections(self, week: int) -> Dict[str, Dict[str, float]]:
        """Scrape projections for all positions at once"""
        all_projections = {}
        
        for position, url_suffix in self.position_urls.items():
            try:
                url = f"https://www.fantasypros.com/nfl/projections/{url_suffix}.php?week={week}"
                logger.info(f"Scraping {position} projections from: {url}")
                
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'id': 'data'}) or soup.find('table', class_='table')
                
                if not table:
                    logger.warning(f"No projection table found for {position}")
                    continue
                
                projections = self._parse_projection_table(table)
                all_projections[position] = projections
                
                time.sleep(1.5)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error scraping {position} projections: {str(e)}")
                all_projections[position] = {}
        
        return all_projections
    
    def scrape_all_position_stats(self, week: int) -> Dict[str, Dict[str, Dict]]:
        """Scrape historical stats for all positions at once"""
        all_stats = {}
        
        for position, url_suffix in self.position_urls.items():
            try:
                url = f"https://www.fantasypros.com/nfl/stats/{url_suffix}.php?range=week&week={week}"
                logger.info(f"Scraping {position} stats from: {url}")
                
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, 'html.parser')
                table = soup.find('table', {'id': 'data'}) or soup.find('table', class_='table')
                
                if not table:
                    logger.warning(f"No stats table found for {position}")
                    continue
                
                stats = self._parse_stats_table(table)
                all_stats[position] = stats
                
                time.sleep(1.5)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error scraping {position} stats: {str(e)}")
                all_stats[position] = {}
        
        return all_stats
    
    def scrape_injury_report(self) -> Dict[str, str]:
        """Scrape complete injury report"""
        injuries = {}
        
        try:
            url = "https://www.fantasypros.com/nfl/injury-report.php"
            logger.info(f"Scraping injury report from: {url}")
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'id': 'data'}) or soup.find('table', class_='table')
            
            if table:
                tbody = table.find('tbody')
                if tbody:
                    for row in tbody.find_all('tr'):
                        cells = row.find_all('td')
                        if len(cells) >= 3:
                            player_name = self._extract_player_name(cells[0])
                            
                            # Get injury status
                            status = "Healthy"
                            for cell in cells[-3:]:
                                cell_text = cell.get_text(strip=True)
                                if cell_text in ['Out', 'Doubtful', 'Questionable', 'Probable']:
                                    status = cell_text
                                    break
                            
                            injuries[player_name] = status
            
            logger.info(f"Scraped injury status for {len(injuries)} players")
            
        except Exception as e:
            logger.error(f"Error scraping injury report: {str(e)}")
            
        return injuries
    
    def _parse_projection_table(self, table) -> Dict[str, float]:
        """Parse projection table and return player:points mapping"""
        projections = {}
        
        # Get headers
        headers = []
        header_row = table.find('thead')
        if header_row:
            for th in header_row.find('tr').find_all('th'):
                headers.append(th.get_text(strip=True))
        
        # Find fantasy points column
        fpts_col = None
        for i, header in enumerate(headers):
            if any(keyword in header.lower() for keyword in ['fpts', 'fantasy', 'points']):
                fpts_col = i
                break
        
        if fpts_col is None:
            fpts_col = len(headers) - 1  # Use last column as fallback
        
        # Parse data rows
        tbody = table.find('tbody')
        if tbody:
            for row in tbody.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) > fpts_col:
                    player_name = self._extract_player_name(cells[0])
                    
                    try:
                        fpts_text = cells[fpts_col].get_text(strip=True)
                        fpts = float(fpts_text) if fpts_text.replace('.', '').replace('-', '').isdigit() else 0.0
                        projections[player_name] = fpts
                    except (ValueError, IndexError):
                        continue
        
        return projections
    
    def _parse_stats_table(self, table) -> Dict[str, Dict]:
        """Parse stats table and return player:stats mapping"""
        stats = {}
        
        # Get headers
        headers = []
        header_row = table.find('thead')
        if header_row:
            for th in header_row.find('tr').find_all('th'):
                headers.append(th.get_text(strip=True))
        
        # Parse data rows
        tbody = table.find('tbody')
        if tbody:
            for row in tbody.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    player_name = self._extract_player_name(cells[0])
                    
                    player_stats = {}
                    for i, header in enumerate(headers):
                        if i < len(cells):
                            try:
                                stat_value = cells[i].get_text(strip=True)
                                if stat_value.replace('.', '').replace('-', '').isdigit():
                                    player_stats[header] = float(stat_value)
                                else:
                                    player_stats[header] = stat_value
                            except (ValueError, IndexError):
                                player_stats[header] = 0
                    
                    if player_stats:
                        stats[player_name] = player_stats
        
        return stats
    
    def _extract_player_name(self, cell) -> str:
        """Extract and clean player name from table cell"""
        player_link = cell.find('a')
        if player_link:
            player_name = player_link.get_text(strip=True)
        else:
            player_name = cell.get_text(strip=True)
        
        # Clean name
        player_name = re.sub(r'\s+[A-Z]{2,3}$', '', player_name)  # Remove team abbreviation
        player_name = re.sub(r'\s+\([^)]+\)', '', player_name)    # Remove parenthetical info
        
        return player_name


# Global instances for the tools to access
scraper = FantasyDataScraper()
roster_data = {}
weekly_data = {}
analyzed_players = []

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name='us-west-2')
bedrock = boto3.client('bedrock-runtime', region_name='us-west-2')
roster_table = dynamodb.Table('fantasy-football-team-roster')

@tool
def load_roster(team_id: str) -> str:
    """Load team roster from DynamoDB database.
    
    Args:
        team_id: The unique team identifier to load roster for
        
    Returns:
        Status message about roster loading
    """
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
    """Gather all fantasy football data for the specified week.
    
    Args:
        week: The NFL week number to gather data for
        
    Returns:
        Status message about data gathering
    """
    global weekly_data
    try:
        logger.info(f"Gathering data for week {week}")
        
        # Scrape all data
        projections = scraper.scrape_all_position_projections(week)
        injuries = scraper.scrape_injury_report()
        
        # Get historical data (last 3 weeks)
        historical_stats = {}
        for past_week in range(max(1, week-3), week):
            historical_stats[f"week_{past_week}"] = scraper.scrape_all_position_stats(past_week)
        
        bye_weeks_dict = {
            5: ['PIT', 'CHI', 'GB', 'ATL'],
            6: ['HOU', 'MIN'],
            7: ['BAL', 'BUF'],
            8: ['JAX', 'LV', 'DET', 'ARI', 'SEA', 'LAR'],
            9: ['PHI', 'CLE', 'NYJ', 'TB'],
            10: ['KC', 'CIN', 'TEN', 'DAL'],
            11: ['IND', 'NO'],
            12: ['MIA', 'DEN', 'LAC', 'WAS'],
            14: ['NYG', 'NE', 'CAR', 'SF']
        }
        
        weekly_data = {
            'projections': projections,
            'injuries': injuries,
            'historical_stats': historical_stats,
            'bye_weeks': bye_weeks_dict.get(week, [])
        }
        
        total_projections = sum(len(pos_proj) for pos_proj in projections.values())
        return f"Successfully gathered weekly data: {total_projections} player projections, {len(injuries)} injury reports, bye teams: {weekly_data['bye_weeks']}"
        
    except Exception as e:
        error_msg = f"Error gathering weekly data: {str(e)}"
        logger.error(error_msg)
        return error_msg

@tool
def analyze_players(week: int) -> str:
    """Analyze all players for availability and projected performance.
    
    Args:
        week: The NFL week number for analysis
        
    Returns:
        Status message about player analysis
    """
    global analyzed_players, roster_data, weekly_data
    try:
        if not roster_data:
            return "Error: No roster loaded. Please load roster first."
        
        if not weekly_data:
            return "Error: No weekly data available. Please gather weekly data first."
        
        analyzed_players = []
        available_count = 0
        
        for player in roster_data:
            # Check bye week
            player.bye_week = player.team in weekly_data['bye_weeks']
            
            # Check injury status
            player.injury_status = weekly_data['injuries'].get(player.name, "Healthy")
            player.is_playing = not player.bye_week and player.injury_status not in ['Out', 'Doubtful']
            
            # Get projections
            position_projections = weekly_data['projections'].get(player.position, {})
            player.projected_points = find_player_projection(player.name, position_projections)
            
            # Get historical performance
            player.past_performance = get_player_history(player.name, player.position, weekly_data['historical_stats'])
            
            # Set matchup rating
            player.matchup_rating = "Average"
            
            analyzed_players.append(player)
            if player.is_playing:
                available_count += 1
            
            logger.info(f"{player.name}: Playing={player.is_playing}, Projected={player.projected_points:.1f}")
        
        return f"Analyzed {len(analyzed_players)} players. {available_count} available to play in week {week}."
        
    except Exception as e:
        error_msg = f"Error analyzing players: {str(e)}"
        logger.error(error_msg)
        return error_msg

@tool
def generate_optimal_lineup() -> str:
    """Generate the optimal fantasy lineup using AI analysis.
    
    Returns:
        JSON string containing the recommended lineup
    """
    global analyzed_players
    try:
        if not analyzed_players:
            return "Error: No analyzed players available. Please analyze players first."
        
        # Filter available players
        available_players = [p for p in analyzed_players if p.is_playing]
        
        if len(available_players) < 9:  # Need at least 9 players for a lineup
            return f"Error: Only {len(available_players)} available players. Need at least 9 for a complete lineup."
        
        # Prepare data for AI
        player_data = []
        for player in available_players:
            player_info = {
                'name': player.name,
                'position': player.position,
                'projected_points': player.projected_points,
                'injury_status': player.injury_status,
                'past_performance_summary': f"Data from {len(player.past_performance)} recent weeks" if player.past_performance else "No recent data"
            }
            player_data.append(player_info)
        
        # Create AI prompt
        prompt = f"""
As a fantasy football expert, analyze this roster and recommend the optimal starting lineup for maximum points.

Available Players:
{json.dumps(player_data, indent=2)}

Lineup Requirements:
- QB (1): Quarterback
- RB (2): Running backs (RB1, RB2) 
- WR (2): Wide receivers (WR1, WR2)
- TE (1): Tight end
- FLEX (1): Additional RB, WR, or TE (highest projected points among remaining)
- OP (1): Offensive player - RB, WR, TE, or QB (can be used for 2nd QB)
- DST (1): Defense/Special Teams
- K (1): Kicker

Prioritize:
1. Highest projected points
2. Recent performance trends
3. Injury status (avoid Questionable if better options exist)

Return your recommendation as JSON:
{{
  "QB": "Player Name",
  "RB1": "Player Name", 
  "RB2": "Player Name",
  "WR1": "Player Name",
  "WR2": "Player Name", 
  "TE": "Player Name",
  "FLEX": "Player Name",
  "OP": "Player Name",
  "DST": "Player Name",
  "K": "Player Name",
  "rationale": "Brief explanation of key decisions",
  "projected_total": "estimated total points"
}}
        """
        
        # Call Bedrock
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-5-haiku-20240620-v1:0',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 2000,
                'messages': [{'role': 'user', 'content': prompt}]
            })
        )
        
        response_body = json.loads(response['body'].read())
        ai_recommendation = response_body['content'][0]['text']
        
        # Parse and return the AI recommendation
        start_idx = ai_recommendation.find('{')
        end_idx = ai_recommendation.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_recommendation = ai_recommendation[start_idx:end_idx]
            return json_recommendation
        else:
            # Fallback recommendation
            return create_fallback_lineup_json(available_players)
        
    except Exception as e:
        error_msg = f"Error generating lineup: {str(e)}"
        logger.error(error_msg)
        # Return fallback recommendation
        if analyzed_players:
            available_players = [p for p in analyzed_players if p.is_playing]
            return create_fallback_lineup_json(available_players)
        return f'{{"error": "{error_msg}"}}'

# Helper functions
def find_player_projection(player_name: str, projections: Dict[str, float]) -> float:
    """Find player projection with fuzzy name matching"""
    # Direct match
    if player_name in projections:
        return projections[player_name]
    
    # Fuzzy match
    for proj_name, points in projections.items():
        if names_match(player_name, proj_name):
            return points
    
    return 0.0

def names_match(name1: str, name2: str) -> bool:
    """Check if two player names match"""
    name1_clean = re.sub(r'[^\w\s]', '', name1.lower()).strip()
    name2_clean = re.sub(r'[^\w\s]', '', name2.lower()).strip()
    
    if name1_clean == name2_clean:
        return True
    
    words1 = set(name1_clean.split())
    words2 = set(name2_clean.split())
    
    return len(words1.intersection(words2)) >= 2

def get_player_history(player_name: str, position: str, historical_stats: Dict) -> Dict:
    """Get player's historical performance"""
    history = {}
    
    for week_key, week_data in historical_stats.items():
        position_stats = week_data.get(position, {})
        for stat_name, stats in position_stats.items():
            if names_match(player_name, stat_name):
                history[week_key] = stats
                break
    
    return history

def create_fallback_lineup_json(available_players: List[Player]) -> str:
    """Create basic recommendation JSON based on projected points"""
    # Sort players by position and points
    qbs = sorted([p for p in available_players if p.position == 'QB'], 
                key=lambda x: x.projected_points, reverse=True)
    rbs = sorted([p for p in available_players if p.position == 'RB'], 
                key=lambda x: x.projected_points, reverse=True)
    wrs = sorted([p for p in available_players if p.position == 'WR'], 
                key=lambda x: x.projected_points, reverse=True)
    tes = sorted([p for p in available_players if p.position == 'TE'], 
                key=lambda x: x.projected_points, reverse=True)
    dsts = sorted([p for p in available_players if p.position == 'DST'], 
                 key=lambda x: x.projected_points, reverse=True)
    ks = sorted([p for p in available_players if p.position == 'K'], 
               key=lambda x: x.projected_points, reverse=True)
    
    recommendation = {
        "QB": qbs[0].name if qbs else "None",
        "RB1": rbs[0].name if len(rbs) > 0 else "None",
        "RB2": rbs[1].name if len(rbs) > 1 else "None",
        "WR1": wrs[0].name if len(wrs) > 0 else "None",
        "WR2": wrs[1].name if len(wrs) > 1 else "None",
        "TE": tes[0].name if tes else "None",
        "FLEX": rbs[2].name if len(rbs) > 2 else (wrs[2].name if len(wrs) > 2 else (tes[1].name if len(tes) > 1 else "None")),
        "OP": qbs[1].name if len(qbs) > 1 else (rbs[3].name if len(rbs) > 3 else "None"),
        "DST": dsts[0].name if dsts else "None",
        "K": ks[0].name if ks else "None",
        "rationale": "Fallback recommendation based on projected points",
        "projected_total": str(sum([p.projected_points for p in available_players[:10]]))
    }
    
    return json.dumps(recommendation)

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
            description="AI-powered fantasy football coaching assistant that analyzes player data and generates optimal lineups",
            tools=[load_roster, gather_weekly_data, analyze_players, generate_optimal_lineup]
        )
        
        print(f"Starting Fantasy Football Agent for team '{team_id}', week {week}...")
        
        # Use the agent with a natural language workflow
        workflow_prompt = f"""
I need you to generate an optimal fantasy football lineup for team '{team_id}' for week {week}.

Please follow this exact workflow:
1. First, use the load_roster tool with team_id '{team_id}'
2. Then, use the gather_weekly_data tool for week {week}
3. Next, use the analyze_players tool for week {week}
4. Finally, use the generate_optimal_lineup tool

Execute each step in order and provide the final lineup recommendation in JSON format.
        """
        
        # Execute the workflow using the agent
        result = agent(workflow_prompt)
        
        # Extract text from AgentResult object
        result_text = str(result) if hasattr(result, '__str__') else result
        
        print(f"\n=== Fantasy Football Agent Response ===")
        print(result_text)
        
        # Try to extract JSON from the response
        try:
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                lineup_json = json.loads(json_match.group())
                
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
                        print(f"{pos_name:5}: {player_name:20}")
                    else:
                        print(f"{pos_name:5}: {'None':20}")
                
                if lineup_json.get("projected_total"):
                    print(f"\nProjected Total: {lineup_json.get('projected_total')} points")
                
                if lineup_json.get("rationale"):
                    print(f"\nAgent Rationale: {lineup_json.get('rationale')}")
                
        except (json.JSONDecodeError, AttributeError):
            # If we can't parse JSON, just show the raw response
            print("Could not parse structured lineup from agent response.")
        
    except Exception as e:
        logger.error(f"Agent execution failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()