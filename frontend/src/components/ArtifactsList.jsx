// frontend/src/components/ArtifactsList.jsx

import React, { useEffect, useState } from "react";
import Navbar from "../components/Navbar.jsx";
import API_ENDPOINTS from "../config/api";
import axios from "axios";
import LoadingSpinner from "../components/LoadingSpinner.jsx";
import { useNavigate } from "react-router-dom";

export default function ArtifactsList() {
  const navigate = useNavigate();

  const [list, setList] = useState(null);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");
  const [loading, setLoading] = useState(false);

  const selectedTypes =
    typeFilter === "all" ? ["model", "dataset", "code"] : [typeFilter];

  const fetchArtifacts = async () => {
    const token = localStorage.getItem("token");
    setLoading(true);

    const trimmed = search.trim();
    const isRegex =
      trimmed.startsWith("/") && trimmed.endsWith("/") && trimmed.length > 2;

    try {
      if (isRegex) {
        const pattern = trimmed.slice(1, -1);

        const res = await axios.post(
          API_ENDPOINTS.ARTIFACT_BY_REGEX,
          { regex: pattern },
          { headers: { "X-Authorization": token } }
        );

        setList(res.data);
        return;
      }

      const body = [
        {
          name: trimmed === "" ? "*" : trimmed,
          types: selectedTypes,
        },
      ];

      const res = await axios.post(API_ENDPOINTS.ARTIFACTS, body, {
        headers: { "X-Authorization": token },
      });

      setList(res.data);
    } catch (err) {
      console.error("Failed to fetch artifacts:", err);
      setList([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchArtifacts();
  }, []);

  const openArtifact = (a) => {
    navigate(`/artifacts/${a.type}/${a.id}`);
  };

  return (
    <>
      <Navbar />
      <div className="container">
        <h1>Artifacts</h1>

        <div className="card">
          <label className="label" htmlFor="artifact-search">Search</label>
          <input
            id="artifact-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name, ID, or /regex/"
            style={{ marginBottom: "1rem", width: "100%" }}
          />

          <label className="label" htmlFor="artifact-type-filter">Type Filter</label>
          <select
            id="artifact-type-filter"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            style={{ marginBottom: "1rem", width: "100%" }}
          >
            <option value="all">All Types</option>
            <option value="model">Models</option>
            <option value="dataset">Datasets</option>
            <option value="code">Code</option>
          </select>

          <button onClick={fetchArtifacts} style={{ width: "100%" }}>
            Refresh
          </button>

          <div style={{ marginTop: "1.5rem" }}>
            {loading || list === null ? (
              <LoadingSpinner />
            ) : list.length === 0 ? (
              <p>No artifacts found.</p>
            ) : (
              <table style={{ width: "100%", marginTop: "1rem" }}>
                <thead>
                  <tr
                    style={{
                      textAlign: "left",
                      borderBottom: "1px solid #444",
                    }}
                  >
                    <th>Name</th>
                    <th>Type</th>
                    <th>ID</th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((a) => (
                    <tr
                      key={a.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => openArtifact(a)}
                      onKeyDown={(e) => e.key === "Enter" && openArtifact(a)}
                      style={{
                        borderBottom: "1px solid #333",
                        cursor: "pointer",
                      }}
                    >
                      <td>{a.name}</td>
                      <td>{a.type}</td>
                      <td>{a.id}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <p style={{ marginTop: "1rem", opacity: 0.7, fontSize: "0.9rem" }}>
            Tip: use <code>/regex/</code> format for regex search. Example: <code>/bert.*/</code>
          </p>
        </div>
      </div>
    </>
  );
}

