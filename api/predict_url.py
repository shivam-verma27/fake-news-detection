import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.api_server import analyze_text, fetch_text_from_url


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

    url = (payload.get("url") or "").strip()
    if not url:
        response.status(400)
        return {"detail": "Empty URL provided."}

    try:
        text, ssl_warning = fetch_text_from_url(url)
    except RuntimeError as e:
        response.status(400)
        return {"detail": str(e)}

    if len(text) < 10:
        response.status(400)
        return {"detail": "No usable text extracted from URL."}

    result = analyze_text(text, source="url", source_name=url)
    result["url"] = url
    if ssl_warning:
        result["warning"] = ssl_warning
    return result
