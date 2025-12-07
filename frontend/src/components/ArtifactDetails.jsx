import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import Navbar from "../components/Navbar.jsx";
import API_ENDPOINTS from "../config/api";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import SuccessBanner from "../components/SuccessBanner.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import axios from "axios";

export default function ArtifactDetails() {
  const { type, id } = useParams();

  const [metadata, setMetadata] = useState(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const token = localStorage.getItem("token");


  const fetchArtifact = async () => {
    try {
      const res = await axios.get(
        API_ENDPOINTS.ARTIFACT_BY_TYPE_ID(type, id),
        { headers: { "X-Authorization": token } }
      );

      setMetadata(res.data);
    } catch (err) {
      setError("Failed to load artifact details.");
      setMetadata(null);
    }
  };

  useEffect(() => {
    fetchArtifact();
  }, [type, id]);

  const run = async (action, fn) => {
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
    run("download", async () => {
      const res = await axios.get(
        API_ENDPOINTS.ARTIFACT_BY_TYPE_ID(type, id),
        { headers: { "X-Authorization": token } }
      );

      // backend does not store files, so we show metadata
      return "Metadata retrieved (download placeholder).";
    });

  const handleCost = () =>
    run("cost", async () => {
      const res = await axios.get(API_ENDPOINTS.ARTIFACT_COST(type, id), {
        headers: { "X-Authorization": token },
      });

      return `Cost: ${JSON.stringify(res.data)}`;
    });

  const handleRate = () =>
    run("rate", async () => {
      if (type !== "model") throw new Error("Only models can be rated.");

      const res = await axios.get(API_ENDPOINTS.ARTIFACT_RATE(id), {
        headers: { "X-Authorization": token },
      });

      return `Rating: ${JSON.stringify(res.data)}`;
    });

  const handleLicense = () =>
    run("license", async () => {
      const res = await axios.post(
        API_ENDPOINTS.ARTIFACT_LICENSE_CHECK(id),
        {},
        { headers: { "X-Authorization": token } }
      );

      return `License check result: ${JSON.stringify(res.data)}`;
    });

  const handleAudit = () =>
    run("audit", async () => {
      const res = await axios.get(
        API_ENDPOINTS.ARTIFACT_AUDIT(type, id),
        { headers: { "X-Authorization": token } }
      );

      return `Audit log: ${JSON.stringify(res.data)}`;
    });

  const handleLineage = () =>
    run("lineage", async () => {
      const res = await axios.get(API_ENDPOINTS.ARTIFACT_LINEAGE(id), {
        headers: { "X-Authorization": token },
      });

      return `Lineage: ${JSON.stringify(res.data)}`;
    });

  return (
    <>
      <Navbar />
      <div className="container">
        <h1>Artifact Details</h1>

        <div className="card">
          {!metadata ? (
            <LoadingSpinner />
          ) : (
            <>
              <p><strong>Name:</strong> {metadata.name || "N/A"}</p>
              <p><strong>ID:</strong> {metadata.id || id}</p>
              <p><strong>Type:</strong> {metadata.type || type}</p>
              <p><strong>Version:</strong> {metadata.version || "N/A"}</p>

              {/* Buttons */}
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

              <button onClick={handleAudit} disabled={loading} style={{ marginTop: "1rem" }}>
                View Audit
              </button>

              <button onClick={handleLineage} disabled={loading} style={{ marginTop: "1rem" }}>
                View Lineage
              </button>

              {/* Status Messages */}
              <SuccessBanner message={success} />
              <ErrorBanner message={error} />
            </>
          )}
        </div>
      </div>
    </>
  );
}

