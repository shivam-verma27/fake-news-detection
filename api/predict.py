import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.api_server import analyze_text


import inspect

async def parse_json_body(request):
    if hasattr(request, "json"):
        body = request.json()
        if inspect.isawaitable(body):
            body = await body
        return body
    if hasattr(request, "body"):
        body = request.body
        if isinstance(body, (bytes, bytearray)):
            body = body.decode("utf-8")
        try:
            import json
            return json.loads(body)
        except Exception:
            return None
    return None


async def handler(request, response):
    if request.method != "POST":
        response.status(405)
        return {"detail": "Method not allowed"}

    payload = parse_json_body(request)
    if not isinstance(payload, dict):
        response.status(400)
        return {"detail": "Invalid JSON payload"}

    text = (payload.get("text") or "").strip()
    if not text:
        response.status(400)
        return {"detail": "Empty text provided."}

    try:
        result = analyze_text(text, source="text")
    except Exception as exc:
        response.status(500)
        return {"detail": str(exc)}

    return result
