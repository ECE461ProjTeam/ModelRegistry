import React, { useState } from "react";
import Navbar from "../components/Navbar.jsx";
import API_ENDPOINTS from "../config/api";
import axios from "axios";
import SuccessBanner from "../components/SuccessBanner.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";

export default function UploadArtifact() {
  const [url, setUrl] = useState("");
  const [type, setType] = useState("model");
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setSuccess("");
    setError("");

    if (!url.trim()) return setError("Please enter a valid URL.");

    try {
      new URL(url);
    } catch {
      return setError("Invalid URL format.");
    }

    let name;
    try {
      const parsed = new URL(url);
      name = parsed.pathname.split("/").filter(Boolean).pop() || type;
    } catch {
      name = type;
    }

    try {
      setLoading(true);
      const token = localStorage.getItem("token");

      const res = await axios.post(
        API_ENDPOINTS.ARTIFACT_CREATE(type),
        { url, name },
        { headers: { "X-Authorization": token } }
      );

      if (res.status === 201) {
        setSuccess(`${type} uploaded successfully!`);
        setUrl("");
      }
    } catch (err) {
      setError(err.response?.data?.message || "Upload failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />
      <div className="container narrow">
        <h1>Upload Artifact</h1>

        <div className="card">
          <label className="label" htmlFor="artifact-type">Artifact Type</label>
          <select
            id="artifact-type"
            className="input-select"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
          <option value="model">Model</option>
          <option value="dataset">Dataset</option>
          <option value="code">Code</option>
          </select>

          <label className="label" style={{ marginTop: "1rem" }}>URL</label>
          <input
            placeholder="https://example.com/model"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />

          {loading ? (
            <LoadingSpinner />
          ) : (
            <button onClick={submit} style={{ marginTop: "1.3rem" }}>
              Upload
            </button>
          )}

          <SuccessBanner message={success} />
          <ErrorBanner message={error} />
        </div>
      </div>
    </>
  );
}


