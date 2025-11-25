import React, { useEffect, useState } from "react";
import Navbar from "../components/Navbar.jsx";
import API_ENDPOINTS from "../config/api";
import LoadingSpinner from "../components/LoadingSpinner.jsx";

export default function SystemHealthDashboard() {
  const [status, setStatus] = useState(null);

  const fetchHealth = async () => {
    try {
      const start = performance.now();
      const res = await fetch(API_ENDPOINTS.HEALTH);
      const end = performance.now();

      const data = await res.json();

      setStatus({
        ok: res.ok,
        message: data.message,
        ms: Math.round(end - start),
        code: res.status,
      });
    } catch {
      setStatus({
        ok: false,
        message: "API unreachable",
        ms: null,
        code: null,
      });
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <>
      <Navbar />
      <div className="container">
        <h1>System Health</h1>

        <div className="card">
          {!status ? (
            <LoadingSpinner />
          ) : (
            <>
              <p>
                Status:{" "}
                <span
                  style={{ color: status.ok ? "#22c55e" : "#ef4444" }}
                >
                  {status.message}
                </span>
              </p>
              <p>Latency: {status.ms} ms</p>
              <p>HTTP Code: {status.code}</p>

              <button onClick={fetchHealth} style={{ marginTop: "1rem" }}>
                Refresh
              </button>
            </>
          )}
        </div>
      </div>
    </>
  );
}

