import React, { useState } from "react";
import axios from "axios";

export default function UserInput() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);

  // Backend URL
  const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:5000";

  const handleSubmit = async () => {
    if (!url.trim()) {
      return setStatus("Please enter a valid URL.");
    }

    // Validate URL format
    try {
      new URL(url);
    } catch (_) {
      return setStatus("Please enter a valid URL format.");
    }

    setLoading(true);
    setStatus("");

    try {
      const response = await axios.post(`${BACKEND_URL}/artifacts/`, { url });
      if (response.status >= 200 && response.status < 300) {
        setStatus("✅ URL submitted successfully!");
        setUrl("");
      } else {
        setStatus("⚠️ Unexpected response from server.");
      }
    } catch (error) {
      if (error.response) {
        setStatus(
          `❌ ${error.response.status}: ${error.response.data.message || "Server error"}`
        );
      } else if (error.request) {
        setStatus("❌ No response from server.");
      } else {
        setStatus(`❌ ${error.message}`);
      }
      console.error(error);
    } finally {
      setLoading(false);
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
          backgroundColor: "var(--button-bg, #1a1a1a)",
          color: "var(--text-color, white)",
          cursor: loading ? "not-allowed" : "pointer",
          transition: "border-color 0.25s",
          opacity: loading ? 0.6 : 1,
        }}
        onMouseOver={(e) => !loading && (e.target.style.borderColor = "#646cff")}
        onMouseOut={(e) => (e.target.style.borderColor = "transparent")}
      >
        {loading ? "Submitting..." : "Submit"}
      </button>

      {status && <p id="status-text" style={{ marginTop: "1rem" }}>{status}</p>}
    </div>
  );
}
