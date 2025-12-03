import React from "react";

export default function LoadingSpinner() {
  return (
    <div
  role="status"
  aria-label="Loading"
  style={{
    border: "4px solid #4b5563",
    borderTop: "4px solid white",
    borderRadius: "50%",
    width: "28px",
    height: "28px",
    animation: "spin 0.8s linear infinite",
    margin: "1rem auto",
  }}
/>
  );
}
