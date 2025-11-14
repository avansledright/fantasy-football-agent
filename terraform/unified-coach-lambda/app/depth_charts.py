import os
import requests
from strands import tool
from typing import Dict, Any, Optional

def get_api_url():
    """Get the depth chart API URL from environment or construct from API Gateway components"""
    api_url = os.environ.get("DEPTH_CHART_API_URL")
    if not api_url:
        # Construct URL from individual components to avoid Terraform circular dependency
        api_id = os.environ.get("API_GATEWAY_ID", "")
        region = os.environ.get("API_GATEWAY_REGION", "")
        stage = os.environ.get("API_GATEWAY_STAGE", "")
        if api_id and region and stage:
            api_url = f"https://{api_id}.execute-api.{region}.amazonaws.com/{stage}/depth-chart"
    return api_url

def fetch_depth_chart(team: str, source: str = "ourlads") -> Optional[Dict[str, Any]]:
    """Call depth chart API to get team depth chart"""
    api_url = get_api_url()

    if not api_url:
        print("Depth chart API URL not configured")
        return None

    try:
        response = requests.get(
            api_url,
            params={"team": team.upper(), "source": source},
            timeout=20
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching depth chart for {team}: {str(e)}")
        return None

@tool
def get_team_depth_chart(team: str, position: Optional[str] = None) -> Dict[str, Any]:
    """Get current NFL team depth chart to understand player roles and QB relationships.

    Essential for:
    - Verifying starting QB for WR/TE projections (WR value tied to QB quality)
    - Finding backup RB handcuffs when starters injured (backup becomes instant RB1)
    - Understanding target share competition at WR/TE
    - Identifying starter vs backup (snap count expectations)

    Args:
        team: NFL team code (DET, BUF, IND, SF, KC, etc.)
        position: Optional filter by position (QB, RB, WR, TE, etc.)

    Returns:
        Depth chart with starters and backups ranked by depth

    Example:
        get_team_depth_chart("IND", "QB") returns Colts QB depth chart
        get_team_depth_chart("SF", "RB") returns 49ers RB depth chart
    """

    depth_chart = fetch_depth_chart(team, source="ourlads")

    if not depth_chart:
        return {
            "error": f"Could not fetch depth chart for {team}",
            "team": team,
            "note": "Depth chart API unavailable - proceed with projection data only"
        }

    if position:
        positions_data = depth_chart.get("positions", {})
        position_players = positions_data.get(position.upper(), [])

        if not position_players:
            return {
                "team": team,
                "position": position,
                "players": [],
                "note": f"No {position} depth chart data available for {team}"
            }

        return {
            "team": team,
            "position": position,
            "players": position_players,
            "starter": position_players[0]["name"] if position_players else "Unknown"
        }

    return depth_chart
