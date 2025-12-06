import React from "react";
import Navbar from "../components/Navbar.jsx";
import { Link } from "react-router-dom";

export default function Dashboard() {
  const cards = [
    { title: "Upload Artifact", desc: "Upload models, datasets, or code.", to: "/upload", icon: "📤" },
    { title: "System Health", desc: "API uptime & diagnostics.", to: "/health", icon: "💡" },
    { title: "Browse Artifacts", desc: "View all stored artifacts.", to: "/artifacts", icon: "📦" },
    { title: "User Profile", desc: "View and manage your account.", to: "/user", icon: "👤" }
  ];

  return (
    <>
      <Navbar />
      <div className="container">
        <h1>Dashboard</h1>

        <div className="tiles">
          {cards.map((card) => (
            <Link key={card.title} to={card.to} className="tile-link">
              <div className="tile">
                <div className="tile-icon">{card.icon}</div>
                <h2>{card.title}</h2>
                <p>{card.desc}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}
