import React, { useEffect, useState } from "react";
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
  Legend,
  ResponsiveContainer,
} from "recharts";

export default function SystemHealthDashboard() {
  const [status, setStatus] = useState(null);
  const [components, setComponents] = useState(null);
  const [componentsError, setComponentsError] = useState(null);
  const [windowMinutes, setWindowMinutes] = useState(60); // Default value 60
  const [loading, setLoading] = useState(false);

  const fetchHealth = async () => {
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
  };

  const fetchComponents = async () => {
    try {
      setLoading(true);
      setComponentsError(null);
      const token = localStorage.getItem("token");

      const url = new URL(API_ENDPOINTS.HEALTH_COMPONENTS);
      url.searchParams.append("windowMinutes", windowMinutes);
      url.searchParams.append("includeTimeline", "true");

      const res = await fetch(url.toString(), {
        headers: {
          "X-Authorization": token || "",
        },
      });

      // If server returned an error status (e.g. 403), try to extract message
      if (!res.ok) {
        let errMsg = `Server returned ${res.status}: ${res.statusText} - unable to fetch components. Please ensure you have the necessary permissions. If you do, please login again.`;
        try {
          const errData = await res.json();
          if (errData && errData.message) errMsg = errData.message;
        } catch (e) {
          // ignore json parse errors
        }
        setComponentsError(errMsg);
        setComponents([]);
        return;
      }

      const data = await res.json();
      setComponents(data && data.components ? data.components : []);
      setComponentsError(null);
    } catch (err) {
      console.error("Error fetching components:", err);
      setComponentsError(err && err.message ? err.message : "Unable to fetch components");
      setComponents([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchAll = () => {
    fetchHealth();
    fetchComponents();
  };

  useEffect(() => {
    fetchAll(); // Initial fetch with default 60
  }, []);

  const renderMetricChart = (timeline, metric) => {
    if (!timeline || !timeline[metric] || timeline[metric].length === 0) return null;

    const chartData = timeline[metric].map((point) => ({
      Timestamp: point.Timestamp,
      Value: Number(point.Average || 0),
    }));

    const COLORS = ["#22c55e", "#f59e0b", "#3b82f6", "#ef4444", "#8b5cf6", "#14b8a6"];
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

        {/* Window Minutes Input and Fetch Button */}
        <div
          className="card"
          style={{
            marginBottom: "1.5rem",
            padding: "1rem",
            display: "flex",
            flexDirection: "column",
            gap: "0.5rem",
          }}
        >
          <label htmlFor="windowMinutes" style={{ fontWeight: "bold" }}>
            Window Minutes:
          </label>
          <input
            type="number"
            id="windowMinutes"
            value={windowMinutes}
            min={1}
            onChange={(e) => setWindowMinutes(Number(e.target.value))}
            style={{
              padding: "0.5rem",
              borderRadius: "5px",
              border: "1px solid #ccc",
              width: "100px",
              fontSize: "1rem",
            }}
          />
          <button
            onClick={fetchAll}
            style={{
              padding: "0.6rem 1rem",
              marginTop: "0.5rem",
              width: "100%",
              backgroundColor: "#3b82f6",
              color: "white",
              border: "none",
              borderRadius: "5px",
              cursor: "pointer",
              fontSize: "1rem",
            }}
          >
            Fetch
          </button>
        </div>

        {/* Health Status */}
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
              <p>
                HTTP Code:{" "}
                {status.code !== null && status.code !== undefined ? status.code : "N/A"}
              </p>
            </>
          )}
        </div>

        {/* Component Health */}
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

              {component.metrics && (
                <div>
                  <h4>Metrics:</h4>
                  <ul>
                    {Object.entries(component.metrics).map(([key, value]) => (
                      <li key={key}>
                        {key}: {value}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Render each metric as its own chart */}
              {component.timeline &&
                Object.keys(component.timeline).length > 0 &&
                Object.keys(component.timeline).map((metric) =>
                  renderMetricChart(component.timeline, metric)
                )}

              {component.logs && component.logs.length > 0 && (
                <div>
                  <h4>Logs:</h4>
                  <ul
                    style={{ maxHeight: "300px", overflowY: "auto", paddingLeft: "1rem" }}
                  >
                    {component.logs.map((log, idx) => (
                      <li key={idx} style={{ marginBottom: "0.5rem" }}>
                        <strong>{new Date(log.timestamp).toLocaleString()}:</strong>{" "}
                        {log.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </>
  );
}
