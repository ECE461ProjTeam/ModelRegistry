import React from "react";
import UserInput from "./components/UserInput.jsx";
import SystemHealthDashboard from "./components/SystemHealthDashboard.jsx";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<UserInput />} />
        <Route path="/health" element={<SystemHealthDashboard/>} />
      </Routes>
    </Router>
  );
}

export default App;
