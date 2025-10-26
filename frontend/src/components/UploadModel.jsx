import React, { useState } from "react";
import axios from "axios";

export default function UploadModel() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState("");

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile && selectedFile.name.endsWith(".zip")) {
      setFile(selectedFile);
      setStatus("");
    } else {
      setFile(null);
      setStatus("Please select a .zip file");
    }
  };

  const handleUpload = async () => {
    if (!file) return setStatus("No file selected");

    const formData = new FormData();
    formData.append("file", file);

    try {
      await axios.post("https://placeholder-endpoint.com/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setStatus("Upload successful!");
    } catch (error) {
      console.error(error);
      setStatus("Upload failed");
    }
  };

  return (
    <div className="flex flex-col items-center justify-center h-screen bg-gray-900 text-gray-100">
      <h1 className="text-3xl font-bold mb-6">Upload .zip File</h1>
      <input
        type="file"
        accept=".zip"
        onChange={handleFileChange}
        className="mb-4 text-gray-900"
      />
      <button
        onClick={handleUpload}
        className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
      >
        Upload
      </button>
      {status && <p className="mt-4">{status}</p>}
    </div>
  );
}
