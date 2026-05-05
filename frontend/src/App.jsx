import React, { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "/api";

export default function App() {
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingType, setLoadingType] = useState("");
  const [error, setError] = useState(null);

  function toNumber(value) {
    if (value == null) return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function normalizeResult(data) {
    const probs = data.probabilities || {};
    const probFake = toNumber(probs.fake ?? probs["0"]);
    const probReal = toNumber(probs.real ?? probs["1"]);
    return {
      ...data,
      probabilities: {
        fake: probFake,
        real: probReal,
      },
    };
  }

  async function parseAndSetResult(res) {
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server responded ${res.status}`);
    }
    const data = await res.json();
    setResult(normalizeResult(data));
  }

  async function analyzeText(e) {
    e.preventDefault();
    const trimmed = text.trim();
    setError(null);
    setResult(null);
    if (!trimmed) {
      setError("Please enter some news text.");
      return;
    }

    setLoading(true);
    setLoadingType("text");
    try {
      const res = await fetch(`${API_URL}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmed }),
      });
      await parseAndSetResult(res);
    } catch (err) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
      setLoadingType("");
    }
  }

  async function analyzeUrl(e) {
    e.preventDefault();
    const trimmed = url.trim();
    setError(null);
    setResult(null);
    if (!trimmed) {
      setError("Please enter a URL.");
      return;
    }

    setLoading(true);
    setLoadingType("url");
    try {
      const res = await fetch(`${API_URL}/predict_url`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: trimmed }),
      });
      await parseAndSetResult(res);
    } catch (err) {
      setError(err.message || "Request failed");
    } finally {
      setLoading(false);
      setLoadingType("");
    }
  }

  function percentFrom(prob) {
    if (prob == null) return "-";
    return `${(prob * 100).toFixed(2)}%`;
  }

  function numericPercent(prob) {
    if (prob == null) return 0;
    return Math.max(0, Math.min(100, Number((prob * 100).toFixed(2))));
  }

  return (
    <div className="container">
      <h1>TruthLens-Fake News Detector</h1>

      <form onSubmit={analyzeText}>
        <label>Paste news/article text below</label>
        <textarea
          placeholder="Paste article text here..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
        />
        <div className="controls">
          <button type="submit" disabled={loading}>
            {loading && loadingType === "text"
              ? "Checking text..."
              : "Analyze text"}
          </button>
          <button
            type="button"
            onClick={() => {
              setText("");
              setResult(null);
              setError(null);
            }}
          >
            Clear text
          </button>
        </div>
      </form>

      <form onSubmit={analyzeUrl} className="source-form">
        <label>Analyze an article URL</label>
        <input
          type="url"
          placeholder="https://example.com/article"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <div className="controls">
          <button type="submit" disabled={loading}>
            {loading && loadingType === "url" ? "Fetching URL..." : "Analyze URL"}
          </button>
        </div>
      </form>

      {error && <div className="error">Error: {error}</div>}

      {result && (
        <div className="result-card">
          <h2>Result: {String(result.label).toUpperCase()}</h2>

          <p>
            <strong>Authenticity (percent):</strong>{" "}
            {result.authenticity_percent ??
              percentFrom(result.probabilities?.real)}
          </p>
          {result.credibility_summary && (
            <p>
              <strong>Summary:</strong> {result.credibility_summary}
            </p>
          )}
          <p>
            <strong>Source:</strong> {result.source || "text"}
            {result.source_name ? ` (${result.source_name})` : ""}
          </p>

          <div className="confidence-row">
            <div
              className="confidence-bar"
              role="progressbar"
              aria-valuenow={numericPercent(result.probabilities?.real)}
              aria-valuemin="0"
              aria-valuemax="100"
            >
              <div
                className="confidence-fill"
                style={{
                  width: `${numericPercent(result.probabilities?.real)}%`,
                }}
                aria-hidden="true"
              />
            </div>

            <div className="confidence-meta">
              <div className="meta-item">
                <strong>Real</strong>
              </div>
              <div className="meta-item percent-text">
                {percentFrom(result.probabilities?.real)}
              </div>
            </div>
          </div>

          <div className="probs" style={{ marginTop: 12 }}>
            <div>
              <strong>Prob(fake):</strong>{" "}
              {percentFrom(result.probabilities?.fake)}
            </div>
            <div>
              <strong>Prob(real):</strong>{" "}
              {percentFrom(result.probabilities?.real)}
            </div>
          </div>

          <div className="split-grid">
            <div className="panel">
              <h3>Top terms supporting {result.explainability?.positive_label || "positive class"}</h3>
              <ul className="term-list">
                {(result.explainability?.top_support_positive || []).map((item) => (
                  <li key={`p-${item.term}`}>
                    <span>{item.term}</span>
                    <small>{item.contribution?.toFixed?.(4) ?? item.contribution}</small>
                  </li>
                ))}
              </ul>
            </div>
            <div className="panel">
              <h3>Top terms supporting {result.explainability?.negative_label || "negative class"}</h3>
              <ul className="term-list">
                {(result.explainability?.top_support_negative || []).map((item) => (
                  <li key={`n-${item.term}`}>
                    <span>{item.term}</span>
                    <small>{item.contribution?.toFixed?.(4) ?? item.contribution}</small>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="panel" style={{ marginTop: 12 }}>
            <h3>Risky sentences</h3>
            {(result.risky_sentences || []).length === 0 && (
              <p>No highly risky sentence detected.</p>
            )}
            <ul className="risky-list">
              {(result.risky_sentences || []).map((item, idx) => (
                <li key={`${idx}-${item.sentence.slice(0, 20)}`}>
                  <div className="risk-head">
                    <strong>Risk: {item.risk_percent}% fake</strong>
                  </div>
                  <div>{item.sentence}</div>
                </li>
              ))}
            </ul>
          </div>

          {result.threshold != null && (
            <div style={{ marginTop: 8, color: "var(--muted)" }}>
              <small>Decision threshold: {result.threshold}%</small>
            </div>
          )}

          <details style={{ marginTop: 12 }}>
            <summary>Raw response</summary>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      )}

      <footer>
        <small>
          Backend: <code>{API_URL}/predict</code> and <code>{API_URL}/predict_url</code>
        </small>
      </footer>
    </div>
  );
}
