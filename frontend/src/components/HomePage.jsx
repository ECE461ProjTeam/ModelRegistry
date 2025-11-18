import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from './AuthProvider.jsx';

export default function HomePage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useAuth();
  const [flashError, setFlashError] = useState(location.state?.error ?? null);

  useEffect(() => {
    if (flashError) {
      // clear the navigation state so the message is shown only once
      navigate(location.pathname, { replace: true, state: {} });
    }
  }, [flashError, navigate, location.pathname]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-indigo-50 via-white to-slate-50 flex items-center justify-center p-6">
      <div className="w-full max-w-4xl bg-white/80 backdrop-blur-md rounded-2xl shadow-2xl border border-gray-100 p-12 text-center transform transition-all duration-500 hover:scale-[1.01]">
        <h1 className="text-5xl font-extrabold text-indigo-700 leading-tight mb-4">Model Registry</h1>
        <p className="text-gray-700 text-lg mb-8">Register, evaluate, and operationalize machine learning models with confidence.</p>

        {flashError && (
          <div className="mb-6 max-w-xl mx-auto bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
            <div className="flex items-center justify-between gap-4">
              <div>{flashError}</div>
              <button
                className="text-red-600 underline text-sm"
                onClick={() => setFlashError(null)}
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {!user ? (
          <div className="space-y-4">
            <p className="text-gray-600">Start by signing in to access dashboards and submissions.</p>
            <div className="flex items-center justify-center gap-4">
              <button
                onClick={() => navigate('/login')}
                className="inline-flex items-center gap-2 px-8 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-full shadow-lg focus:outline-none"
              >
                Login
              </button>
              <button
                onClick={() => navigate('/login', { state: { from: '/dashboard' } })}
                className="inline-flex items-center gap-2 px-6 py-2 bg-white text-indigo-700 border border-indigo-200 rounded-full shadow-sm hover:bg-indigo-50"
              >
                Explore Models
              </button>
            </div>
          </div>
        ) : (
          <div>
            <p className="text-green-600 font-medium mb-4">Signed in as <span className="font-semibold">{user.username || user.name || user.email}</span></p>
            <button
              onClick={() => navigate('/dashboard')}
              className="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md shadow-md focus:outline-none"
            >
              Go to Dashboard
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
