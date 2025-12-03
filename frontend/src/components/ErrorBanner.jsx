import React from "react";

export default function ErrorBanner({ message }) {
  if (!message) return null;

  return (
    <div
  className="px-4 py-3 rounded-md mt-4"
  role="alert"
  style={{
    background: "#3a1e1e",
    border: "1px solid #ef4444",
    color: "#fecaca",
  }}
>
      {message}
    </div>
  );
}
