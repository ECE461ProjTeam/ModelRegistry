import React, { createContext, useState, useContext, useMemo } from 'react';
import API_ENDPOINTS from '../config/api';

const AuthContext = createContext();

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Login
  const login = async (username, password) => {
    setError(null);
    setLoading(true);
    try {
      const res = await fetch(API_ENDPOINTS.AUTHENTICATE, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user: { name: username }, secret: { password } }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || errData.message || 'Login failed');
      }

      const data = await res.json();
      localStorage.setItem('token', data.token);
      // Backend returns only a token on successful authenticate; set a minimal user object
      setUser({ name: username });
      return true;
    } catch (err) {
      console.error('Login error:', err);
      setError(err.message);
      return false;
    } finally {
      setLoading(false);
    }
  };

  // Logout
  const logout = async () => {
    localStorage.removeItem('token');
    setUser(null);
    setLoading(false);
  };

  // TODO: Register Users (with permissions
  
  // TODO: Profile (fetch/update)


  // Memoize context value
  const contextValue = useMemo(
    () => ({ user, loading, error, logout, login }),
    [user, loading, error]
  );

  return (
    <AuthContext.Provider value={contextValue}>
      {children}
    </AuthContext.Provider>
  );
};

function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}

export { AuthProvider, useAuth };
