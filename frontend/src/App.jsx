import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider, useAuth } from "./components/AuthProvider.jsx";

import HomePage from "./components/HomePage.jsx";
import LoginPage from "./components/LoginPage.jsx";
import Dashboard from "./components/Dashboard.jsx";
import UploadModel from "./components/UploadModel.jsx";
import SystemHealthDashboard from "./components/SystemHealthDashboard.jsx";
import ArtifactsList from "./components/ArtifactsList.jsx";
import AdminReset from "./components/AdminReset.jsx";

function PrivateRoute({ element }) {
  const { user, loading } = useAuth();
  if (loading) return <p>Loading...</p>;
  return user ? element : <HomePage />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<PrivateRoute element={<Dashboard />} />} />
          <Route path="/upload" element={<PrivateRoute element={<UploadModel />} />} />
          <Route path="/health" element={<PrivateRoute element={<SystemHealthDashboard />} />} />
          <Route path="/artifacts" element={<PrivateRoute element={<ArtifactsList />} />} />
          <Route path="/admin/reset" element={<PrivateRoute element={<AdminReset />} />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}


