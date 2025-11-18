import React, { createContext, useState, useContext, useMemo, useEffect } from 'react';
import API_ENDPOINTS from '../config/api';

const AuthContext = createContext();

const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  // `loading` starts true to indicate app initialization (session restore)
  const [loading, setLoading] = useState(true);
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
      // Backend returns only a token on successful authenticate; fetch profile to populate user
      try {
        const profileRes = await fetch(API_ENDPOINTS.PROFILE, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'X-Authorization': `${data.token}`,
          },
        });

        if (profileRes.ok) {
          const profileData = await profileRes.json();
          setUser(profileData.profile || { name: username });
        } else {
          setUser({ name: username });
        }
      } catch (err) {
        console.error('Failed to fetch profile after login:', err);
        setUser({ name: username });
      }
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

  // Restore session on app load if a token exists
  useEffect(() => {
    let mounted = true;

    const restoreSession = async () => {
      try {
        const token = localStorage.getItem('token');
        if (!token) return;

        const res = await fetch(API_ENDPOINTS.PROFILE, {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
            'X-Authorization': `${token}`,
          },
        });

        if (!mounted) return;

        if (res.ok) {
          const data = await res.json();
          // Backend returns { profile: { name, is_admin, permissions, ... } }
          setUser(data.profile || { name: data.name });
        } else {
          // Token invalid or expired — clear it
          localStorage.removeItem('token');
        }
      } catch (err) {
        console.error('Failed to restore session:', err);
        localStorage.removeItem('token');
      } finally {
        if (mounted) setLoading(false);
      }
    };

    restoreSession();

    return () => {
      mounted = false;
    };
  }, []);

  // TODO: Register Users (with permissions)
  
  // TODO: Profile (fetch/update)


  // Memoize context value
  const contextValue = useMemo(
    () => ({ user, loading, error, logout, login }),
    [user, loading, error, logout, login]
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
