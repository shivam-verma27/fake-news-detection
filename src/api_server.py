# src/api_server.py
import os
import json
import joblib
import re
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Dict, List
from pathlib import Path
from fastapi.staticfiles import StaticFiles

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
VECT_PATH = MODELS_DIR / "vectorizer.joblib"
CLF_PATH = MODELS_DIR / "classifier.joblib"
METRICS_PATH = MODELS_DIR / "metrics.json"
CONFUSION_MATRIX_IMAGE_PATH = MODELS_DIR / "confusion_matrix.png"
URL_FETCH_VERIFY_SSL = os.getenv("URL_FETCH_VERIFY_SSL", "true").lower() in {"1", "true", "yes", "on"}

if not VECT_PATH.exists() or not CLF_PATH.exists():
    raise RuntimeError("Models not found. Run src/train_tfidf.py first to create models/")

vec = joblib.load(VECT_PATH)
clf = joblib.load(CLF_PATH)
FEATURE_NAMES = vec.get_feature_names_out()
LABEL_MAP = {0: "fake", 1: "real"}

app = FastAPI(title="Fake News Authenticator (TF-IDF baseline)")

origins = [
    "http://localhost:5173",  # Vite dev
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "*",  # for development only — remove in production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NewsText(BaseModel):
    text: str


class UrlRequest(BaseModel):
    url: str


def clean_text(s):
    if s is None:
        return ""
    s = str(s)
    s = re.sub(r'http\S+', '', s)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def split_sentences(text: str) -> List[str]:
    raw_parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in raw_parts if len(p.strip()) > 20]


def fetch_text_from_url(url: str):
    if not re.match(r"^https?://", url.strip(), flags=re.IGNORECASE):
        raise RuntimeError("URL must start with http:// or https://")

    headers = {"User-Agent": "Mozilla/5.0 (compatible; TruthLens/1.0)"}
    ssl_warning = None
    try:
        resp = requests.get(url, timeout=12, headers=headers, verify=URL_FETCH_VERIFY_SSL)
        resp.raise_for_status()
    except requests.exceptions.SSLError as e:
        if URL_FETCH_VERIFY_SSL:
            # Local/dev fallback for environments with custom/intercepted certificates.
            try:
                resp = requests.get(url, timeout=12, headers=headers, verify=False)
                resp.raise_for_status()
                ssl_warning = "SSL verification failed, URL was fetched without certificate validation."
            except requests.RequestException:
                raise RuntimeError(
                    "Could not fetch URL due to SSL verification failure. "
                    "Set URL_FETCH_VERIFY_SSL=false for local development if needed."
                ) from e
        else:
            raise RuntimeError(f"Could not fetch URL due to SSL error: {e}")
    except requests.RequestException as e:
        raise RuntimeError(f"Could not fetch URL: {e}")

    html = resp.text
    html = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", html)
    html = re.sub(r"(?is)<[^>]+>", " ", html)
    html = re.sub(r"\s+", " ", html)
    return clean_text(html), ssl_warning


def make_explainability(row, top_n: int = 8) -> Dict:
    coef = clf.coef_[0]
    indices = row.indices.tolist()
    values = row.data.tolist()

    contributions = []
    for idx, value in zip(indices, values):
        contrib = float(value * coef[idx])
        contributions.append({
            "term": str(FEATURE_NAMES[idx]),
            "contribution": contrib
        })

    positive_class = int(clf.classes_[1])
    negative_class = int(clf.classes_[0])
    positive_label = LABEL_MAP.get(positive_class, str(positive_class))
    negative_label = LABEL_MAP.get(negative_class, str(negative_class))

    pos_terms = [c for c in contributions if c["contribution"] > 0]
    neg_terms = [c for c in contributions if c["contribution"] < 0]
    pos_terms.sort(key=lambda x: x["contribution"], reverse=True)
    neg_terms.sort(key=lambda x: x["contribution"])

    return {
        "positive_label": positive_label,
        "negative_label": negative_label,
        "top_support_positive": pos_terms[:top_n],
        "top_support_negative": [
            {"term": x["term"], "contribution": abs(x["contribution"])}
            for x in neg_terms[:top_n]
        ],
    }


def find_risky_sentences(cleaned_text: str, top_n: int = 5) -> List[Dict]:
    sentences = split_sentences(cleaned_text)[:30]
    if not sentences:
        return []

    X_sent = vec.transform(sentences)
    probs = clf.predict_proba(X_sent)
    risky = []

    for sent, proba in zip(sentences, probs):
        class_proba = {LABEL_MAP[int(c)]: float(p) for c, p in zip(clf.classes_, proba)}
        fake_prob = class_proba.get("fake", 0.0)
        real_prob = class_proba.get("real", 0.0)
        if fake_prob >= 0.55:
            risky.append({
                "sentence": sent,
                "risk_percent": round(fake_prob * 100, 2),
                "probabilities": {
                    "fake": fake_prob,
                    "real": real_prob,
                },
            })

    risky.sort(key=lambda x: x["risk_percent"], reverse=True)
    return risky[:top_n]


def analyze_text(text: str, source: str = "text", source_name: str = None) -> Dict:
    cleaned = clean_text(text)
    if not cleaned:
        raise HTTPException(status_code=400, detail="Empty text provided.")
    if len(cleaned) < 10:
        raise HTTPException(status_code=400, detail="Text too short after cleaning.")

    X = vec.transform([cleaned])
    proba = clf.predict_proba(X)[0]
    proba_map = {LABEL_MAP[int(c)]: float(p) for c, p in zip(clf.classes_, proba)}

    authenticity_percent = round(proba_map.get("real", 0.0) * 100, 2)
    label = "real" if authenticity_percent >= 50 else "fake"
    risky_sentences = find_risky_sentences(cleaned)
    explanation = make_explainability(X[0])

    if label == "real":
        credibility_summary = f"Mostly credible signal ({authenticity_percent}%), but verify with trusted sources."
    else:
        credibility_summary = f"Likely misleading signal ({round(100 - authenticity_percent, 2)}% fake probability)."

    return {
        "authenticity_percent": authenticity_percent,
        "label": label,
        "probabilities": proba_map,
        "source": source,
        "source_name": source_name,
        "credibility_summary": credibility_summary,
        "explainability": explanation,
        "risky_sentences": risky_sentences,
    }


def load_metrics() -> Dict:
    if not METRICS_PATH.exists():
        raise HTTPException(status_code=404, detail="metrics.json not found. Run src/train_tfidf.py first.")
    with open(METRICS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/confusion_matrix")
def get_confusion_matrix() -> Dict:
    metrics = load_metrics()
    classes = metrics.get("classes", [])
    matrix = metrics.get("confusion_matrix")

    if not classes or matrix is None:
        raise HTTPException(status_code=404, detail="Confusion matrix not found in metrics.json. Retrain the model first.")

    labels = [LABEL_MAP.get(int(label), str(label)) for label in classes]
    return {
        "classes": classes,
        "labels": labels,
        "matrix": matrix,
        "readable": {
            f"actual_{labels[i]}": {
                f"predicted_{labels[j]}": matrix[i][j]
                for j in range(len(labels))
            }
            for i in range(len(labels))
        },
    }


@app.get("/confusion_matrix_image")
def get_confusion_matrix_image():
    if not CONFUSION_MATRIX_IMAGE_PATH.exists():
        raise HTTPException(status_code=404, detail="confusion_matrix.png not found. Run src/train_tfidf.py first.")
    return FileResponse(CONFUSION_MATRIX_IMAGE_PATH, media_type="image/png")

@app.post("/predict")
def predict(payload: NewsText) -> Dict:
    return analyze_text(payload.text, source="text")


@app.post("/predict_url")
def predict_url(payload: UrlRequest) -> Dict:
    url = (payload.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="Empty URL provided.")

    try:
        text, ssl_warning = fetch_text_from_url(url)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(text) < 10:
        raise HTTPException(status_code=400, detail="No usable text extracted from URL.")

    result = analyze_text(text, source="url", source_name=url)
    result["url"] = url
    result["extracted_chars"] = len(text)
    if ssl_warning:
        result["warning"] = ssl_warning
    return result


# serve frontend build if present
DIST_DIR = BASE_DIR / "frontend" / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=str(DIST_DIR), html=True), name="frontend")
