from typing import TypedDict, Any, Dict, List

class LambdaResponse(TypedDict, total=False):
    statusCode: int
    headers: Dict[str, str]
    isBase64Encoded: bool
    body: str