import React, { createContext, useState, useContext, useEffect } from 'react';
import API_ENDPOINTS from '../config/api';

const AuthContext = createContext();

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Centralized fetch wrapper
  const authFetch = async (url, options = {}) => {
    const token = localStorage.getItem("token");
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-Authorization": token } : {}),
        ...(options.headers || {})
      }
    });

    if (res.status === 401) {
      if (token) {
        // Token was present → session expired
        logout();
        throw new Error("Session expired. Please login again.");
      } else {
        // No token → user not logged in
        throw new Error("You must be logged in to access this resource.");
      }
    }

    if (res.status === 403) {
      // User logged in but doesn't have permission
      throw new Error("You do not have permission to access this resource.");
    }

    if (!res.ok) {
      const message = await res.text();
      throw new Error(message || "Something went wrong.");
    }

    return res.json();
  };

  // Login function
  const login = async (username, password) => {
    setError(null);
    setLoading(true);
    try {
      const tokenResponse = await fetch(API_ENDPOINTS.AUTHENTICATE, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user: { name: username }, secret: { password } }),
      });

      if (!tokenResponse.ok) throw new Error("Invalid credentials");

      const token = await tokenResponse.json();
      localStorage.setItem("token", token);

      try {
        const profileData = await authFetch(API_ENDPOINTS.PROFILE);
        setUser(profileData.profile || { name: username });
      } catch {
        setUser({ name: username }); // fallback if profile fails
      }

      return true;
    } catch (err) {
      setError(err.message);
      return false;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem("token");
    setUser(null);
    setLoading(false);
  };

  // Restore user on page load
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return setLoading(false);

    const restore = async () => {
      try {
        const data = await authFetch(API_ENDPOINTS.PROFILE);
        setUser(data.profile);
      } catch (err) {
        setError(err.message); // show session expired message if token invalid
      } finally {
        setLoading(false);
      }
    };

    restore();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout, authFetch }}>
      {children}
    </AuthContext.Provider>
  );
};

// Custom hook
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

export { AuthProvider };
