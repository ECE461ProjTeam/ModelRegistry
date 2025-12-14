// frontend/src/components/ArtifactDetails.jsx

import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Navbar from "./Navbar.jsx";
import API_ENDPOINTS from "../config/api.js";
import axios from "axios";
import LoadingSpinner from "./LoadingSpinner.jsx";
import SuccessBanner from "./SuccessBanner.jsx";
import ErrorBanner from "./ErrorBanner.jsx";

export default function ArtifactDetails() {
  const { type, id } = useParams();

  const [metadata, setMetadata] = useState(null);
  const [dataBlock, setDataBlock] = useState(null);
  const [backendMsg, setBackendMsg] = useState(""); // sensitive model response message
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const token = localStorage.getItem("token");

  function renderJsonObject(obj) {
    if (!obj || typeof obj !== "object") return String(obj);

    return (
      <div
        style={{
          background: "#111",
          padding: "1rem",
          borderRadius: "8px",
          marginTop: "1rem",
          whiteSpace: "pre-wrap",
          fontFamily: "monospace",
          color: "#0f0",
        }}
      >
        {Object.entries(obj).map(([key, value]) => (
          <div key={key}>
            <strong>{key}:</strong> {JSON.stringify(value, null, 2)}
          </div>
        ))}
      </div>
    );
  }

  const fetchArtifact = async () => {
    try {
      const res = await axios.get(
        API_ENDPOINTS.ARTIFACT_BY_TYPE_ID(type, id),
        { headers: { "X-Authorization": token } }
      );

      setMetadata(res.data.metadata);
      setDataBlock(res.data.data);
      setBackendMsg(res.data.message || "");
    } catch (err) {
      setError("Failed to load artifact details.");
    }
  };

  useEffect(() => {
    fetchArtifact();
  }, []);


  // Generic helper for action buttons (Cost, Rate, Lineage, License...)
  const run = async (fn) => {
    setLoading(true);
    setError("");
    setSuccess("");

    try {
      const msg = await fn();
      setSuccess(msg);
    } catch (err) {
      let msg =
        err.response?.data?.description ||
        err.response?.data?.message ||
        err.message ||
        "Action failed.";

      if (msg.includes("AccessDenied") || msg.includes("Access Denied")) {
        msg = "S3 file exists, but access is restricted (private bucket).";
      }

      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // Download button logic
  // Sensitive models: backend may return empty URL
  // Normal models: backend gives direct download_url

  const handleDownload = () =>
  run(async () => {
    if (!dataBlock) throw new Error("No artifact data available.");

    // Fetch fresh metadata from backend to check JS status
    const res = await axios.get(
      API_ENDPOINTS.ARTIFACT_BY_TYPE_ID(type, id),
      { headers: { "X-Authorization": token } }
    );

    const payload = res.data;

    // If backend says JS failed → show error message instead of downloading
    if (res.status === 202 || res.status === 203) {
      throw new Error(payload.message || "Download blocked by JS policy.");
    }

    // If no download URL → error
    if (!payload.data?.download_url) {
      throw new Error("Download URL not available.");
    }

    // Perform real download
    const url = payload.data.download_url;
    const a = document.createElement("a");
    a.href = url;
    a.download = url.split("/").pop();
    document.body.appendChild(a);
    a.click();
    a.remove();

    return "Downloading...";
  });


  const handleCost = () =>
    run(async () => {
      const res = await axios.get(API_ENDPOINTS.ARTIFACT_COST(type, id), {
        headers: { "X-Authorization": token },
      });
      return res.data;
    });

  const handleRate = () =>
    run(async () => {
      if (type !== "model") throw new Error("Only models can be rated.");
      const res = await axios.get(API_ENDPOINTS.ARTIFACT_RATE(id), {
        headers: { "X-Authorization": token },
      });
      return res.data;
    });

  const handleLicense = () =>
    run(async () => {
      const githubUrl = window.prompt("Enter a GitHub repository URL:");
      if (!githubUrl) throw new Error("GitHub URL is required.");
      const re = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/i;
      if (!re.test(githubUrl.trim()))
        throw new Error("Please enter a valid GitHub repository URL.");

      const res = await axios.post(
        API_ENDPOINTS.ARTIFACT_LICENSE_CHECK(id),
        { github_url: githubUrl },
        { headers: { "X-Authorization": token } }
      );
      return res.data;
    });

  const handleLineage = () =>
    run(async () => {
      const res = await axios.get(API_ENDPOINTS.ARTIFACT_LINEAGE(id), {
        headers: { "X-Authorization": token },
      });
      const graph = res.data;
      if (!graph?.nodes || graph.nodes.length === 0)
        return "No lineage available.";
      if (graph.nodes.length === 1)
        return "This model has no lineage relationships.";
      return graph;
    });

  // Download button enabled only if URL exists
  const isDownloadAllowed = dataBlock?.download_url;

  return (
    <>
      <Navbar />
      <div className="container">
        <h1>Artifact Details</h1>

        {!metadata ? (
          <LoadingSpinner />
        ) : (
          <div className="card">
            <p>
              <strong>Name:</strong> {metadata.name}
            </p>
            <p>
              <strong>ID:</strong> {metadata.id}
            </p>
            <p>
              <strong>Type:</strong> {metadata.type}
            </p>

            {backendMsg && (
              <p style={{ color: "#60a5fa", marginTop: "0.5rem" }}>
                <strong>Backend: </strong>
                {backendMsg}
              </p>
            )}

            <button
              onClick={handleDownload}
              disabled={loading || !isDownloadAllowed}
            >
              Download
            </button>

            <button onClick={handleCost} disabled={loading} style={{ marginTop: "1rem" }}>
              Get Cost
            </button>

            <button onClick={handleRate} disabled={loading} style={{ marginTop: "1rem" }}>
              Rate
            </button>

            <button onClick={handleLicense} disabled={loading} style={{ marginTop: "1rem" }}>
              Run License Check
            </button>

            <button onClick={handleLineage} disabled={loading} style={{ marginTop: "1rem" }}>
              View Lineage
            </button>

            {success && (
              <div style={{ marginTop: "1rem" }}>
                <SuccessBanner message={typeof success === "string" ? success : ""} />
                {typeof success === "object" && renderJsonObject(success)}
              </div>
            )}

            <ErrorBanner message={error} />
          </div>
        )}
      </div>
    </>
  );
}
