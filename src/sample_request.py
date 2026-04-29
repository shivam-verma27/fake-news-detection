# src/sample_request.py
import requests

TEXT_URL = "http://127.0.0.1:8000/predict"
URL_CHECK_URL = "http://127.0.0.1:8000/predict_url"

sample_text = """
Breaking reports claim a miracle cure was discovered overnight and every doctor is hiding it.
The article cites no verified sources and urges readers to share immediately.
""".strip()

sample_url = "https://example.com/article"

for name, endpoint, payload in [
    ("text", TEXT_URL, {"text": sample_text}),
    ("url", URL_CHECK_URL, {"url": sample_url}),
]:
    resp = requests.post(endpoint, json=payload)
    print(f"{name} status:", resp.status_code)
    try:
        print(resp.json())
    except Exception:
        print(resp.text)
