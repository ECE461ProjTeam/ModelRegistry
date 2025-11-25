import React, { useEffect, useState } from "react";
import Navbar from "../components/Navbar.jsx";
import API_ENDPOINTS from "../config/api";
import axios from "axios";
import LoadingSpinner from "../components/LoadingSpinner.jsx";

export default function ArtifactsList() {
  const [list, setList] = useState(null);

  const fetchArtifacts = async () => {
    const token = localStorage.getItem("token");

    const body = [{ name: "*", types: ["model", "dataset", "code"] }];

    const res = await axios.post(API_ENDPOINTS.ARTIFACTS, body, {
      headers: { "X-Authorization": token },
    });

    setList(res.data);
  };

  useEffect(() => {
    fetchArtifacts();
  }, []);

  return (
    <>
      <Navbar />
      <div className="container">
        <h1>Artifacts</h1>

        <div className="card">
          {!list ? (
            <LoadingSpinner />
          ) : list.length === 0 ? (
            <p>No artifacts found.</p>
          ) : (
            <table style={{ width: "100%", marginTop: "1rem" }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "1px solid #444" }}>
                  <th>Name</th>
                  <th>Type</th>
                  <th>ID</th>
                </tr>
              </thead>
              <tbody>
                {list.map((a) => (
                  <tr key={a.id} style={{ borderBottom: "1px solid #333" }}>
                    <td>{a.name}</td>
                    <td>{a.type}</td>
                    <td>{a.id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <button onClick={fetchArtifacts} style={{ marginTop: "1rem" }}>
            Refresh
          </button>
        </div>
      </div>
    </>
  );
}
