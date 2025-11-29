import React from "react";

export default function SuccessBanner({ message }) {
  if (!message) return null;

  return (
    <div
  className="px-4 py-3 rounded-md mt-4"
  role="status"
  style={{
    background: "#1e3a1e",
    border: "1px solid #22c55e",
    color: "#bbf7d0",
  }}
>
      {message}
    </div>
  );
}
