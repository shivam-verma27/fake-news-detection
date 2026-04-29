# src/train_tfidf.py
import os
import glob
import json
import re
import pandas as pd
import numpy as np
MPL_CONFIG_DIR = os.path.join(os.getcwd(), ".matplotlib")
os.makedirs(MPL_CONFIG_DIR, exist_ok=True)
os.environ["MPLCONFIGDIR"] = MPL_CONFIG_DIR
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
import joblib

DATA_DIR = os.path.join(os.getcwd(), "data")
MODELS_DIR = os.path.join(os.getcwd(), "models")
os.makedirs(MODELS_DIR, exist_ok=True)


# -------- helpers --------
def find_csv_files(data_dir=DATA_DIR):
    print("CSV FOUND")
    return sorted(glob.glob(os.path.join(data_dir, "*.csv")))


def read_csv_safe(path):
    try:
        return pd.read_csv(path, encoding='utf-8', low_memory=False)
    except Exception:
        return pd.read_csv(path, encoding='latin1', low_memory=False)


def map_label_value(v):
    if pd.isna(v):
        return None
    # numeric-like
    try:
        iv = int(float(v))
        if iv == 1:
            return 1
        if iv == 0:
            return 0
    except Exception:
        pass
    s = str(v).strip().lower()
    if "fake" in s or "false" in s or "fabric" in s:
        return 0
    if "true" in s or "real" in s or "genuine" in s or "legit" in s or "reliable" in s:
        return 1
    return None


def pick_text_column(df):
    candidates = ['text', 'article', 'content', 'body', 'title', 'headline']
    for c in candidates:
        if c in df.columns:
            return c
    # fallback: choose string column with largest average length
    str_cols = [c for c in df.select_dtypes(include='object').columns]
    if not str_cols:
        raise RuntimeError("No text-like column found in your CSVs.")
    lengths = {c: df[c].fillna("").astype(str).map(len).mean() for c in str_cols}
    return max(lengths, key=lengths.get)


def clean_text(s):
    if pd.isna(s):
        return ""
    s = str(s)
    s = re.sub(r'http\S+', '', s)          # remove urls
    s = re.sub(r'<[^>]+>', '', s)          # remove html
    s = re.sub(r'\s+', ' ', s)             # collapse whitespace
    return s.strip()


# -------- main loader --------
def load_and_prepare(data_dir=DATA_DIR):
    csvs = find_csv_files(data_dir)
    if not csvs:
        raise FileNotFoundError(f"No CSV files found in {data_dir}. Place your CSV(s) there.")
    # common two-file pattern: Fake.csv + True.csv
    names = [os.path.basename(p).lower() for p in csvs]
    if any('fake' in n for n in names) and any(('true' in n or 'real' in n) for n in names) and len(csvs) >= 2:
        # try to pick true+fake by name
        fake_paths = [p for p in csvs if 'fake' in os.path.basename(p).lower()]
        true_paths = [p for p in csvs if ('true' in os.path.basename(p).lower() or 'real' in os.path.basename(p).lower())]
        dfs = []
        for p in fake_paths:
            df = read_csv_safe(p)
            df['__inferred_label__'] = 0
            dfs.append(df)
        for p in true_paths:
            df = read_csv_safe(p)
            df['__inferred_label__'] = 1
            dfs.append(df)
        df = pd.concat(dfs, ignore_index=True)
        # prefer provided label column if exists, else use inferred
        if 'label' not in df.columns and '__inferred_label__' in df.columns:
            df['label'] = df['__inferred_label__']
        df.drop(columns=['__inferred_label__'], inplace=True, errors=True)
    else:
        # generic: combine all CSVs into one, expect a label column or infer from filename
        dfs = []
        for p in csvs:
            df = read_csv_safe(p)
            if 'label' not in df.columns:
                fname = os.path.basename(p).lower()
                if 'fake' in fname:
                    df['label'] = 0
                elif 'true' in fname or 'real' in fname:
                    df['label'] = 1
            dfs.append(df)
        df = pd.concat(dfs, ignore_index=True)
    # pick text column
    text_col = pick_text_column(df)
    # normalize label column
        # pick text column
    if "title" in df.columns and "text" in df.columns:
        df["__combined__"] = (df["title"].fillna("") + " " + df["text"].fillna("")).map(clean_text)
        text_col = "__combined__"
    else:
        text_col = pick_text_column(df)

    # normalize label column
    if 'label' not in df.columns:
        raise RuntimeError("No 'label' column found and couldn't infer labels. Make sure your CSV has a label column or file names contain 'fake'/'true'.")
    df['label_mapped'] = df['label'].apply(map_label_value)
    df = df.dropna(subset=['label_mapped'])
    df['label_mapped'] = df['label_mapped'].astype(int)

    # keep only text and label_mapped
    df = df[[text_col, 'label_mapped']].rename(columns={text_col: 'text', 'label_mapped': 'label'})

    # clean text
    df['text'] = df['text'].astype(str).map(clean_text)
    df = df[df['text'].map(len) > 5].reset_index(drop=True)
    return df


def train_and_save(df, models_dir=MODELS_DIR):
    X = df['text'].values
    y = df['label'].values
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    vec = TfidfVectorizer(max_features=20000, ngram_range=(1, 2))
    X_train_tf = vec.fit_transform(X_train)
    X_val_tf = vec.transform(X_val)

    clf = LogisticRegression(max_iter=1000, class_weight='balanced', random_state=42)
    clf.fit(X_train_tf, y_train)

    # evaluate
    preds = clf.predict(X_val_tf)
    probs = clf.predict_proba(X_val_tf)
    report = classification_report(y_val, preds, output_dict=True)
    acc = accuracy_score(y_val, preds)
    cm = confusion_matrix(y_val, preds, labels=clf.classes_)

    # save
    joblib.dump(vec, os.path.join(models_dir, "vectorizer.joblib"))
    joblib.dump(clf, os.path.join(models_dir, "classifier.joblib"))

    metrics = {
        "accuracy": float(acc),
        "report": report,
        "classes": clf.classes_.tolist(),
        "confusion_matrix": cm.tolist()
    }
    with open(os.path.join(models_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    cm_df = pd.DataFrame(
        cm,
        index=[f"actual_{label}" for label in clf.classes_],
        columns=[f"predicted_{label}" for label in clf.classes_]
    )
    cm_df.to_csv(os.path.join(models_dir, "confusion_matrix.csv"), encoding="utf-8")

    plt.figure(figsize=(6, 5))
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=["Fake", "Real"],
        yticklabels=["Fake", "Real"],
    )
    plt.xlabel("Predicted Label")
    plt.ylabel("Actual Label")
    plt.title("Confusion Matrix for TruthLens Model")
    plt.tight_layout()
    plt.savefig(os.path.join(models_dir, "confusion_matrix.png"), dpi=200)
    plt.close()

    print("Training complete.")
    print(json.dumps(metrics, indent=2))
    print("\nConfusion Matrix:")
    print(cm_df.to_string())
    print(f"Saved vectorizer and classifier in {models_dir}")


if __name__ == "__main__":
    print("Loading data from ./data ...")
    df = load_and_prepare(DATA_DIR)
    print(f"Loaded {len(df)} rows. Example:\n", df.head(3).to_dict(orient='records'))
    train_and_save(df, MODELS_DIR)
