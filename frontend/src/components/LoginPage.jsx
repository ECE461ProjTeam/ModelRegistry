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

  // Extract redirect info from PrivateRoute
  const redirectTo = location.state?.from || "/dashboard";
  const accessMessage = location.state?.message || null;

  // Clear one-time "Please sign in…" message on load
  useEffect(() => {
    if (accessMessage) {
      // Clear state so the message isn't shown if user revisits login manually
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setLocalError("");

    const ok = await login(username, password);

    if (ok) {
      navigate(redirectTo); // go back to intended route
    } else {
      setLocalError("Invalid username or password.");
    }
  };

  return (
    <div className="container">
      <div className="card" style={{ marginTop: "5rem" }}>
        <h1>Login</h1>

        {/* Show redirect message */}
        {accessMessage && (
          <p className="status-error" style={{ marginBottom: "1rem" }}>
            {accessMessage}
          </p>
        )}

        <form onSubmit={submit}>
          <input
            placeholder="Username"
            value={username}
            onChange={(e) => {
              setUsername(e.target.value);
              setLocalError("");
            }}
            required
            style={{ marginBottom: "1rem" }}
          />

          <input
            placeholder="Password"
            type="password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setLocalError("");
            }}
            required
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


