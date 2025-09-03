from typing import TypedDict, Any, Dict, List

class LambdaResponse(TypedDict, total=False):
    statusCode: int
    headers: Dict[str, str]
    isBase64Encoded: bool
    body: str

class AgentRequest(TypedDict, total=False):
    week: int
    team_id: str
    scoring: str
    lineup_slots: List[str]
