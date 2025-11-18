import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthProvider.jsx';

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const ok = await login(username, password);
      setLoading(false);
      if (ok) {
        const redirectTo = location.state?.from ?? '/dashboard';
        navigate(redirectTo);
      } else {
        setError('Invalid username or password');
      }
    } catch (err) {
      setLoading(false);
      setError('Login failed');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-50 via-white to-slate-50 p-6">
      <div className="w-full max-w-md bg-white rounded-xl shadow-xl p-8 border border-gray-100">
        <h2 className="text-2xl font-semibold text-center text-indigo-700 mb-4">Sign in to Model Registry</h2>
        <p className="text-sm text-gray-500 text-center mb-6">Enter your credentials to continue:</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">Username</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              className="w-full px-3 py-2 border rounded-md focus:ring-indigo-200 focus:border-indigo-300"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-600 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2 border rounded-md focus:ring-indigo-200 focus:border-indigo-300"
            />
          </div>

          {error && <div className="text-sm text-red-600">{error}</div>}

          <div className="flex items-center justify-between gap-4">
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-md shadow hover:bg-indigo-700 disabled:opacity-60"
              disabled={loading}
            >
              {loading ? 'Signing in...' : 'Sign in'}
            </button>
            <button
              type="button"
              onClick={() => navigate('/')}
              className="px-4 py-2 rounded-md border"
            >
              Back
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
