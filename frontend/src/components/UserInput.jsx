import React, { useState } from "react";
import axios from "axios";

export default function UserInput() {
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState("");

  // Replace with your Flask backend URL
  const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:5000";

  const handleSubmit = async () => {
    if (!url.trim()) return setStatus("Please enter a valid URL.");

    try {
      const response = await axios.post(`${BACKEND_URL}/artifacts/`, { url });
      if (response.status === 200 || response.status === 201) {
        setStatus("✅ URL submitted successfully!");
        setUrl("");
      } else {
        setStatus("⚠️ Unexpected response from server.");
      }
    } catch (error) {
      console.error(error);
      setStatus("❌ Submission failed. Please try again.");
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
      }}
    >
      <h1 style={{ fontSize: "2em", marginBottom: "1rem" }}>Submit Model URL</h1>

      <input
        type="text"
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
        onClick={handleSubmit}
        style={{
          borderRadius: "8px",
          border: "1px solid transparent",
          padding: "0.6em 1.2em",
          fontSize: "1em",
          fontWeight: "500",
          fontFamily: "inherit",
          backgroundColor: "var(--button-bg, #1a1a1a)",
          color: "var(--text-color, white)",
          cursor: "pointer",
          transition: "border-color 0.25s",
        }}
        onMouseOver={(e) => (e.target.style.borderColor = "#646cff")}
        onMouseOut={(e) => (e.target.style.borderColor = "transparent")}
      >
        Submit
      </button>

      {status && <p style={{ marginTop: "1rem" }}>{status}</p>}
    </div>
  );
}
