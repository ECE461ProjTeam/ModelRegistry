import React from "react";
import Navbar from "../components/Navbar.jsx";
import { Link } from "react-router-dom";

export default function Dashboard() {
  const cards = [
    {
      title: "Upload Model",
      desc: "Register or update ML artifacts.",
      to: "/upload",
      icon: "📤",
    },
    {
      title: "System Health",
      desc: "Check API uptime & status.",
      to: "/health",
      icon: "💡",
    },
    {
      title: "Browse Artifacts",
      desc: "View all stored artifacts.",
      to: "/artifacts",
      icon: "📦",
    },
  ];

  return (
    <>
      <Navbar />
      <div className="container">
        <h1>Dashboard</h1>

        <div
          style={{
            display: "grid",
            gap: "1.5rem",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            marginTop: "2rem",
          }}
        >
          {cards.map((c) => (
            <Link key={c.title} to={c.to} style={{ textDecoration: "none" }}>
              <div
                className="card"
                style={{
                  transition: "0.2s",
                  cursor: "pointer",
                  minHeight: "150px",
                }}
              >
                <div style={{ fontSize: "2rem" }}>{c.icon}</div>
                <h2 style={{ marginTop: "0.5rem" }}>{c.title}</h2>
                <p style={{ opacity: 0.8 }}>{c.desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}


