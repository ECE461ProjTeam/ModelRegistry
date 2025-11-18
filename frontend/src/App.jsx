import React from "react";
import Dashboard from "./components/Dashboard.jsx";
import SystemHealthDashboard from "./components/SystemHealthDashboard.jsx";
import HomePage from "./components/HomePage.jsx";
import LoginPage from "./components/LoginPage.jsx";
import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./components/AuthProvider.jsx";

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/dashboard"
            element={<PrivateRoute element={<Dashboard />} />}
          />
          <Route
            path="/health"
            element={<PrivateRoute element={<SystemHealthDashboard />} />}
          />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

function PrivateRoute({ element }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <div>Loading...</div>;
  if (user) return element;
  const message = location.pathname === '/dashboard'
    ? 'Please log in to access the model registry'
    : 'Please sign in to access the Model Registry.';
  return <Navigate to="/" replace state={{ error: message }} />;
}

export default App;
