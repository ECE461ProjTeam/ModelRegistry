import React, { useState } from "react";
import Navbar from "../components/Navbar.jsx";
import API_ENDPOINTS from "../config/api";
import axios from "axios";
import SuccessBanner from "../components/SuccessBanner.jsx";
import ErrorBanner from "../components/ErrorBanner.jsx";
import LoadingSpinner from "../components/LoadingSpinner.jsx";

export default function UploadModel() {
  const [url, setUrl] = useState("");
  const [success, setSuccess] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setSuccess("");
    setError("");

    if (!url.trim()) return setError("Please enter a model URL.");
    try {
      new URL(url);
    } catch {
      return setError("Please enter a valid URL format.");
    }

    let name = url.split("/").pop() || "model";

    try {
      setLoading(true);

      const token = localStorage.getItem("token");

      const res = await axios.post(
        API_ENDPOINTS.ARTIFACT_CREATE("model"),
        { url, name },
        { headers: { "X-Authorization": token } }
      );

      if (res.status === 201) {
        setSuccess("Model uploaded successfully!");
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
      <div className="container">
        <h1>Upload Model</h1>
        <div className="card">
          <input
            placeholder="Model URL"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />

          {loading ? (
            <LoadingSpinner />
          ) : (
            <button onClick={submit} style={{ marginTop: "1rem" }}>
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

