import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../components/AuthProvider.jsx";

export default function LoginPage() {
  const { login, error } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const navigate = useNavigate();

  const submit = async (e) => {
    e.preventDefault();
    const ok = await login(username, password);
    if (ok) navigate("/dashboard");
  };

  return (
    <div className="container">
      <div className="card" style={{ marginTop: "5rem" }}>
        <h1>Login</h1>

        <form onSubmit={submit}>
          <input
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            style={{ marginBottom: "1rem" }}
          />

          <input
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />

          <button type="submit" style={{ marginTop: "1.5rem", width: "100%" }}>
            Sign In
          </button>

          {error && <p className="status-error">{error}</p>}
        </form>
      </div>
    </div>
  );
}

