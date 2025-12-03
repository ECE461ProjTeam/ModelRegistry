import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../components/AuthProvider.jsx";

export default function LoginPage() {
  const { login } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [localError, setLocalError] = useState("");
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo = location.state?.from || "/dashboard";
  const accessMessage = location.state?.message || null;

  useEffect(() => {
    if (accessMessage) {
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setLocalError("");

    const ok = await login(username, password);
    if (ok) navigate(redirectTo);
    else setLocalError("Invalid username or password.");
  };

  return (
    <div className="container narrow">
      <div className="card">
        <h1>Login</h1>

        {accessMessage && <p className="status-error">{accessMessage}</p>}

        <form onSubmit={submit}>
          <input
            placeholder="Username"
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
              setLocalError("");
            }}
            required
          />

          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setLocalError("");
            }}
            required
            style={{ marginTop: "1rem" }}
          />

          <button type="submit" style={{ marginTop: "1.5rem", width: "100%" }}>
            Sign In
          </button>

          {localError && <p className="status-error">{localError}</p>}
        </form>
      </div>
    </div>
  );
}



