import React from "react";
import { Link } from "react-router-dom";

export default function HomePage() {
  return (
    <div className="container">
      <h1>Model Registry</h1>
      <p>A simple interface for uploading and managing ML artifacts.</p>

      <Link to="/login">
        <button style={{ marginTop: "2rem" }}>Login</button>
      </Link>
    </div>
  );
}

