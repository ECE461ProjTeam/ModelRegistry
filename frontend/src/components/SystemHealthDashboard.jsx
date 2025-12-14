import React, { useEffect, useState, useCallback } from "react";
import Navbar from "../components/Navbar.jsx";
import API_ENDPOINTS from "../config/api";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

export default function SystemHealthDashboard() {
  const [status, setStatus] = useState(null);
  const [components, setComponents] = useState(null);
  const [componentsError, setComponentsError] = useState(null);
  const [windowMinutes, setWindowMinutes] = useState(60);
  const [loading, setLoading] = useState(false);

  const fetchHealth = useCallback(async () => {
    try {
      setLoading(true);
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
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchComponents = useCallback(async () => {
    try {
      setLoading(true);
      setComponentsError(null);

      const token = localStorage.getItem("token");

      const url = new URL(API_ENDPOINTS.HEALTH_COMPONENTS);
      url.searchParams.append("windowMinutes", windowMinutes);
      url.searchParams.append("includeTimeline", "true");

      const res = await fetch(url.toString(), {
        headers: { "X-Authorization": token || "" },
      });

      if (!res.ok) {
        let errMsg = `Server returned ${res.status}: ${res.statusText}`;

        try {
          const errData = await res.json();
          if (errData?.message) errMsg = errData.message;
        } catch {}

        setComponentsError(errMsg);
        setComponents([]);
        return;
      }

      const data = await res.json();
      setComponents(data?.components || []);
      setComponentsError(null);
    } catch (err) {
      setComponentsError(err?.message || "Unable to fetch components");
      setComponents([]);
    } finally {
      setLoading(false);
    }
  }, [windowMinutes]);

  const fetchAll = useCallback(() => {
    fetchHealth();
    fetchComponents();
  }, [fetchHealth, fetchComponents]);

  useEffect(() => {
    fetchAll();
  }, []); // only run once

  const renderMetricChart = (timeline, metric) => {
    if (!timeline?.[metric]?.length) return null;

    const chartData = timeline[metric].map((point) => ({
      Timestamp: point.Timestamp,
      Value: Number(point.Average ?? point.Sum ?? 0),
    }));

    const COLORS = ["#22c55e", "#f59e0b", "#326ed1", "#ef4444", "#8b5cf6", "#14b8a6"];
    const color = COLORS[Math.floor(Math.random() * COLORS.length)];

    return (
      <div key={metric} style={{ marginBottom: "1.5rem" }}>
        <h5>{metric}</h5>
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="Timestamp" tick={{ fontSize: 12 }} />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="Value" stroke={color} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  };

  return (
    <>
      <Navbar />
      <div className="container">
        <h1>System Health</h1>

        <div className="card" style={{ marginBottom: "1.5rem", padding: "1rem" }}>
          <label htmlFor="windowMinutes" style={{ fontWeight: "bold" }}>
            Window Minutes:
          </label>

          <input
            type="number"
            id="windowMinutes"
            value={windowMinutes}
            min={1}
            onChange={(e) => {
              const v = Number(e.target.value);
              setWindowMinutes(v < 1 || Number.isNaN(v) ? 1 : v);
            }}
            style={{
              padding: "0.5rem",
              borderRadius: "5px",
              border: "1px solid #ccc",
              width: "100px",
            }}
          />

          <button
            onClick={fetchAll}
            disabled={loading}
            style={{
              marginTop: "0.5rem",
              padding: "0.6rem 1rem",
              backgroundColor: loading ? "#94a3b8" : "#326ed1",
              color: "white",
              border: "none",
              borderRadius: "5px",
              cursor: loading ? "not-allowed" : "pointer",
            }}
          >
            {loading ? "Fetching..." : "Fetch"}
          </button>
        </div>

        <h2>Health Status</h2>
        <div className="card" style={{ marginBottom: "1.5rem" }}>
          {!status || loading ? (
            <LoadingSpinner />
          ) : (
            <>
              <p>
                Status:{" "}
                <span style={{ color: status.ok ? "#22c55e" : "#ef4444" }}>
                  {status.message}
                </span>
              </p>
              <p>Latency: {status.ms !== null ? `${status.ms} ms` : "N/A"}</p>
              <p>HTTP Code: {status.code ?? "N/A"}</p>
            </>
          )}
        </div>

        <h2>Component Health</h2>
        <ErrorBanner message={componentsError} />

        {!components || loading ? (
          <LoadingSpinner />
        ) : components.length === 0 ? (
          <p>No components available</p>
        ) : (
          components.map((component) => (
            <div key={component.id} className="card" style={{ marginBottom: "1.5rem" }}>
              <h3>{component.display_name}</h3>

              <p>
                Status:{" "}
                <span
                  style={{
                    color:
                      component.status === "OK" || component.status === "Ready"
                        ? "#22c55e"
                        : component.status === "degraded"
                        ? "#facc15"
                        : "#ef4444",
                  }}
                >
                  {component.status}
                </span>
              </p>

              <p>Observed At: {new Date(component.observed_at).toLocaleString()}</p>

              {/* Metrics */}
              {component.metrics && (
                <>
                  <h4>Metrics:</h4>
                  <ul>
                    {Object.entries(component.metrics).map(([k, v]) => (
                      <li key={k}>
                        {k}: {v}
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {/* Charts */}
              {component.timeline &&
                Object.keys(component.timeline).map((metric) =>
                  renderMetricChart(component.timeline, metric)
                )}

              {/* Logs - ADA compliant */}
              {component.logs?.length > 0 && (
                <>
                  <h4>Logs:</h4>
                  <ul
                    className="scrollable-logs"
                    tabIndex="0"
                    style={{
                      maxHeight: "300px",
                      overflowY: "auto",
                      padding: "0",
                      margin: "0",
                      outline: "none",
                    }}
                  >
                    {component.logs.map((log, idx) => (
                      <li key={idx}>
                        <strong>{new Date(log.timestamp).toLocaleString()}:</strong>{" "}
                        {log.message}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          ))
        )}
      </div>
    </>
  );
}

