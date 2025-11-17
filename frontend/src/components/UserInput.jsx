import React, { useState } from "react";
import axios from "axios";

export default function UserInput() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:5000";

  const handleSubmit = async () => {
    if (!url.trim()) {
      return setStatus({ type: "error", text: "Please enter a valid URL." });
    }

    try {
      new URL(url);
    } catch (_) {
      return setStatus({ type: "error", text: "Please enter a valid URL format." });
    }

    setLoading(true);
    setStatus({ type: "info", text: "Submitting..." });

    try {
      const response = await axios.post(`${BACKEND_URL}/artifacts/`, { url });
      if (response.status >= 200 && response.status < 300) {
        setStatus({ type: "success", text: "✅ URL submitted successfully!" });
        setUrl("");
      } else {
        setStatus({ type: "error", text: "⚠️ Unexpected response from server." });
      }
    } catch (error) {
      if (error.response) {
        setStatus({
          type: "error",
          text: `❌ ${error.response.status}: ${error.response.data.message || "Server error"}`,
        });
      } else if (error.request) {
        setStatus({ type: "error", text: "❌ No response from server." });
      } else {
        setStatus({ type: "error", text: `❌ ${error.message}` });
      }
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (type) => {
    switch (type) {
      case "success":
        return "limegreen";
      case "error":
        return "crimson";
      case "info":
        return "orange";
      default:
        return "white";
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "1rem",
      }}
    >
      <h1 style={{ fontSize: "2em", marginBottom: "1rem" }}>Submit Model URL</h1>

      <input
        id="url-input"
        type="text"
        aria-label="Model URL"
        placeholder="Enter model URL"
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        style={{
          width: "320px",
          padding: "0.6em 1em",
          borderRadius: "8px",
          border: "1px solid #888",
          marginBottom: "1rem",
          backgroundColor: "var(--button-bg, #1a1a1a)",
          color: "var(--text-color, white)",
        }}
      />

      <button
        id="submit-btn"
        onClick={handleSubmit}
        disabled={loading}
        aria-label="Submit URL"
        style={{
          borderRadius: "8px",
          border: "1px solid transparent",
          padding: "0.6em 1.2em",
          fontSize: "1em",
          fontWeight: "500",
          fontFamily: "inherit",
          backgroundColor: "#1a1a1a",
          color: "white",
          cursor: loading ? "not-allowed" : "pointer",
          opacity: loading ? 0.6 : 1,
          position: "relative",
        }}
      >
        {loading ? (
          <>
            <span
              className="spinner"
              style={{
                width: "12px",
                height: "12px",
                border: "2px solid white",
                borderTopColor: "transparent",
                borderRadius: "50%",
                display: "inline-block",
                marginRight: "8px",
                animation: "spin 1s linear infinite",
              }}
            ></span>
            Uploading...
          </>
        ) : (
          "Submit"
        )}
      </button>

      {status && (
        <p
          id="status-text"
          style={{
            marginTop: "1rem",
            fontSize: "1.1em",
            color: getStatusColor(status.type),
          }}
        >
          {status.text}
        </p>
      )}

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

