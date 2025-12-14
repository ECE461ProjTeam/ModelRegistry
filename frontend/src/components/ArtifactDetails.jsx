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
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const token = localStorage.getItem("token");

  // Pretty-print JSON
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

      // Handle sensitive-model JS execution messages
if (res.data.message === "JS program returned non-zero exit code") {
  // JS failed: show only clean message
  setError("JS program returned non-zero exit code");
}
else if (res.data.stdout) {
  // JS succeeded: show stdout
  setSuccess(res.data.stdout);
}
else if (res.data.message && (!res.data.data?.download_url || res.data.data.download_url === "")) {
  // Other backend messages
  setError(res.data.message);
}


    } catch (err) {
      setError("Failed to load artifact details.");
      setMetadata(null);
    }
  };

  useEffect(() => {
    fetchArtifact();
  }, []);

  // ------------------------------------------------------------
  // ACTION HANDLERS
  // ------------------------------------------------------------

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

  // DOWNLOAD
  const handleDownload = () =>
    run(async () => {
      if (!dataBlock?.download_url)
        throw new Error(
          "Download blocked: Missing download URL. (Sensitive model may have failed JS validation.)"
        );

      const link = document.createElement("a");
      link.href = dataBlock.download_url;
      const urlParts = dataBlock.download_url.split("/");
      link.download = urlParts[urlParts.length - 1] || "download";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      return "Downloading...";
    });

  // GET COST
  const handleCost = () =>
    run(async () => {
      const res = await axios.get(API_ENDPOINTS.ARTIFACT_COST(type, id), {
        headers: { "X-Authorization": token },
      });
      return res.data;
    });

  // RATE MODEL
  const handleRate = () =>
    run(async () => {
      if (type !== "model") throw new Error("Only models can be rated.");
      const res = await axios.get(API_ENDPOINTS.ARTIFACT_RATE(id), {
        headers: { "X-Authorization": token },
      });
      return res.data;
    });

  // LICENSE CHECK
  const handleLicense = () =>
    run(async () => {
      const githubUrl = window.prompt("Enter a GitHub repository URL:");
      if (!githubUrl) throw new Error("GitHub URL is required.");

      const regex = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/?$/i;
      if (!regex.test(githubUrl.trim())) {
        throw new Error(
          "Please enter a valid GitHub repository URL (e.g., https://github.com/owner/repo)."
        );
      }

      const res = await axios.post(
        API_ENDPOINTS.ARTIFACT_LICENSE_CHECK(id),
        { github_url: githubUrl },
        { headers: { "X-Authorization": token } }
      );

      return res.data;
    });

  // LINEAGE
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

  // OPEN ORIGINAL SOURCE LINK (HUGGING FACE / GITHUB)
  const handleOpenSourceLink = () =>
    run(async () => {
      if (!dataBlock?.url)
        throw new Error("No source URL available for this artifact.");

      window.open(dataBlock.url, "_blank", "noopener,noreferrer");
      return "Opening source link...";
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
            <p>
              <strong>Name:</strong> {metadata.name}
            </p>
            <p>
              <strong>ID:</strong> {metadata.id}
            </p>
            <p>
              <strong>Type:</strong> {metadata.type}
            </p>

            {/* ACTION BUTTONS */}
            <button onClick={handleDownload} disabled={loading}>
              Download
            </button>

            <button
              onClick={handleCost}
              disabled={loading}
              style={{ marginTop: "1rem" }}
            >
              Get Cost
            </button>

            <button
              onClick={handleRate}
              disabled={loading}
              style={{ marginTop: "1rem" }}
            >
              Rate
            </button>

            <button
              onClick={handleLicense}
              disabled={loading}
              style={{ marginTop: "1rem" }}
            >
              Run License Check
            </button>

            <button
              onClick={handleLineage}
              disabled={loading}
              style={{ marginTop: "1rem" }}
            >
              View Lineage
            </button>

            {/* NEW BUTTON — OPEN ORIGINAL SOURCE */}
            <button
              onClick={handleOpenSourceLink}
              disabled={loading}
              style={{
                marginTop: "1rem",
                backgroundColor: "#326ed1",
              }}
            >
              Get Link
            </button>

            {/* OUTPUTS */}
            {success && (
              <div style={{ marginTop: "1rem" }}>
                <SuccessBanner
                  message={typeof success === "string" ? success : ""}
                />
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

