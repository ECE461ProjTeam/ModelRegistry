import React from "react";
import { Link } from "react-router-dom";
import { useAuth } from "./AuthProvider.jsx";

export default function Navbar() {
  const { user, logout } = useAuth();

  if (!user) return null; // Hide navbar when logged out

  return (
    <nav className="navbar">
      <div className="nav-links">
        <Link to="/dashboard">Dashboard</Link>
        <Link to="/upload">Upload Artifact</Link>
        <Link to="/health">Health</Link>
        <Link to="/user">Profile</Link>
      </div>

      <button onClick={logout} style={{ background: "#d73c3c" }}>
        Logout
      </button>
    </nav>
  );
}
