import React, { useState } from "react";
import Navbar from "../components/Navbar.jsx";
import API_ENDPOINTS from "../config/api";
import axios from "axios";
import SuccessBanner from "../components/SuccessBanner.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";

export default function AdminReset() {
  const [success, setSuccess] = useState("");
  const [error, setError] =
  useState("");

  const reset = async () => {
    setSuccess("");
    setError("");

    try {
      const token = localStorage.getItem("token");

      const res = await axios.delete(API_ENDPOINTS.RESET, {
        headers: { "X-Authorization": token },
      });

      if (res.status === 200) setSuccess("Registry reset successfully.");
    } catch (err) {
      setError(err.response?.data?.message || "Failed to reset. Please try again.");
    }
  };

  return (
    <>
      <Navbar />
      <div className="container">
        <h1>Admin Reset</h1>

        <div className="card">
          <p style={{ color: "#f87171" }}>
            ⚠️ This action cannot be undone.
          </p>

          <button
            onClick={reset}
            style={{
              background: "#dc2626",
              marginTop: "1rem",
            }}
          >
            Reset Registry
          </button>

          <SuccessBanner message={success} />
          <ErrorBanner message={error} />
        </div>
      </div>
    </>
  );
}
