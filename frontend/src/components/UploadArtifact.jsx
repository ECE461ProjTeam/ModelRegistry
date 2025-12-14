// frontend/src/components/UploadArtifact.jsx

import React, { useState } from "react";
import Navbar from "../components/Navbar.jsx";
import API_ENDPOINTS from "../config/api";
import axios from "axios";
import SuccessBanner from "../components/SuccessBanner.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";

export default function UploadArtifact() {
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [type, setType] = useState("model");
  const [sensitive, setSensitive] = useState(false);
  const [jsProgram, setJsProgram] = useState("");

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

    if (!name.trim()) return setError("Please enter a name.");
    if (sensitive && (!jsProgram || !jsProgram.trim()))
      return setError("Sensitive models require a JS program.");

    try {
      setLoading(true);
      const token = localStorage.getItem("token");

      const res = await axios.post(
        API_ENDPOINTS.ARTIFACT_CREATE(type),
        {
          url,
          name,
          sensitive,
          js_program: sensitive ? jsProgram : null,
        },
        {
          headers: { "X-Authorization": token },
        }
      );

      if (res.status === 201) {
        setSuccess(`${type} uploaded successfully!`);
        setUrl("");
        setName("");
        setSensitive(false);
        setJsProgram("");
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
          {/* Artifact type */}
          <label className="label" htmlFor="artifact-type">
            Artifact Type
          </label>
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

          {/* Name */}
          <label className="label" style={{ marginTop: "1rem" }}>
            Artifact Name
          </label>
          <input
            placeholder="my-model-v1"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />

          {/* URL */}
          <label className="label" style={{ marginTop: "1rem" }}>
            URL
          </label>
          <input
            placeholder="https://example.com/model"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />

          {/* Sensitive toggle */}
          <label className="label" style={{ marginTop: "1rem" }}>
            Sensitive Model?
          </label>
          <select
            className="input-select"
            value={sensitive ? "true" : "false"}
            onChange={(e) => setSensitive(e.target.value === "true")}
          >
            <option value="false">No</option>
            <option value="true">Yes (requires JS program)</option>
          </select>

          {/* JS program box */}
          {sensitive && (
            <>
              <label className="label" style={{ marginTop: "1rem" }}>
                JS Program
              </label>
              <textarea
                value={jsProgram}
                onChange={(e) => setJsProgram(e.target.value)}
                placeholder={`console.log("OK");\nprocess.exit(0);`}
                style={{
                  width: "100%",
                  height: "160px",
                  background: "#111",
                  color: "#0f0",
                  fontFamily: "monospace",
                  padding: "1rem",
                  borderRadius: "8px",
                  marginTop: "0.5rem",
                }}
              />
            </>
          )}

          {/* upload button */}
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





