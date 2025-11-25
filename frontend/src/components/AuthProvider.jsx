import React, { createContext, useState, useContext, useMemo, useEffect } from 'react';
import API_ENDPOINTS from '../config/api';

const AuthContext = createContext();

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const login = async (username, password) => {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(API_ENDPOINTS.AUTHENTICATE, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user: { name: username }, secret: { password } }),
      });

      if (!res.ok) throw new Error("Invalid credentials");

      const token = await res.json();
      localStorage.setItem("token", token);

      const profileRes = await fetch(API_ENDPOINTS.PROFILE, {
        headers: { "X-Authorization": token }
      });

      const profileData = await profileRes.json();
      setUser(profileData.profile || { name: username });

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
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return setLoading(false);

    const restore = async () => {
      try {
        const res = await fetch(API_ENDPOINTS.PROFILE, {
          headers: { "X-Authorization": token }
        });
        if (!res.ok) throw new Error();

        const data = await res.json();
        setUser(data.profile);
      } catch {
        localStorage.removeItem("token");
      }
      setLoading(false);
    };

    restore();
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth() {
  return useContext(AuthContext);
}

export { AuthProvider };

