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
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const token = localStorage.getItem("token");

  // Pretty print any JSON object into a readable list
function renderJsonObject(obj) {
  if (!obj || typeof obj !== "object") return String(obj);

  return (
    <div style={{
      background: "#111",
      padding: "1rem",
      borderRadius: "8px",
      marginTop: "1rem",
      whiteSpace: "pre-wrap",
      fontFamily: "monospace",
      color: "#0f0"
    }}>
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

      // backend returns { metadata: {...}, data: {...} }
      setMetadata(res.data.metadata);
      setDataBlock(res.data.data);

    } catch (err) {
      setError("Failed to load artifact details.");
      setMetadata(null);
    }
  };

  useEffect(() => {
    fetchArtifact();
  }, []);


  // --------------------------
  // ACTION HANDLERS (NO CHANGE)
  // --------------------------

  const run = async (fn) => {
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const msg = await fn();
      setSuccess(msg);
    } catch (err) {
      const msg =
        err.response?.data?.description ||
        err.response?.data?.message ||
        err.message ||
        "Action failed.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () =>
    run(async () => {
      if (!dataBlock?.url)
        throw new Error("Backend did not provide a download URL.");

      // trigger real download without navigating away
      const link = document.createElement('a');
      link.href = dataBlock.url;
      // Try to extract a filename from the URL, fallback to 'download'
      const urlParts = dataBlock.url.split('/');
      link.download = urlParts[urlParts.length - 1] || 'download';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      return "Downloading...";
    });

  const handleCost = () =>
    run(async () => {
      const res = await axios.get(API_ENDPOINTS.ARTIFACT_COST(type, id), {
        headers: { "X-Authorization": token },
      });

      return res.data;  // return the pure object for pretty printing

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

  return (
    <>
      <Navbar />
      <div className="container">
        <h1>Artifact Details</h1>

        {!metadata ? (
          <LoadingSpinner />
        ) : (
          <div className="card">
            <p><strong>Name:</strong> {metadata.name}</p>
            <p><strong>ID:</strong> {metadata.id}</p>
            <p><strong>Type:</strong> {metadata.type}</p>

            <button onClick={handleDownload} disabled={loading}>
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
    {/* If success is JSON, show pretty box */}
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