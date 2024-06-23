// app/page.tsx
"use client";

import { useState, useEffect } from "react";
import Image from "next/image";

export default function Home() {
  const [prompt, setPrompt] = useState("");
  const [image, setImage] = useState<string | null>(null);
  const [info, setInfo] = useState<any>(null);
  const [objFile, setObjFile] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // Send prompt to Flask server
      const response = await fetch("http://127.0.0.1:5000/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      console.log(response);
      if (!response.ok) throw new Error("Failed to generate");

      // Trigger fetching of results
      fetchResults();
    } catch (error) {
      console.error("Error:", error);
    }
  };

  const fetchResults = async () => {
    // Fetch image
    const imageResponse = await fetch("/api/getImage");
    if (imageResponse.ok) {
      const imageBlob = await imageResponse.blob();
      setImage(URL.createObjectURL(imageBlob));
    }

    // Fetch info JSON
    const infoResponse = await fetch("/api/getInfo");
    if (infoResponse.ok) {
      const infoData = await infoResponse.json();
      setInfo(infoData);
    }

    // Fetch OBJ file
    const objResponse = await fetch("/api/getObj");
    if (objResponse.ok) {
      const objBlob = await objResponse.blob();
      setObjFile(URL.createObjectURL(objBlob));
    }
  };

  return (
    <div>
      <form
        onSubmit={handleSubmit}
        className="flex justify-center items-center h-[70vh] w-full"
      >
        <input
          type="text"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Enter your prompt"
          className="w-[400px] h-12 pl-2 text-lg font-medium"
        />
        <button
          type="submit"
          className=" ml-4 px-6 py-3 rounded-xl text-black bg-sky-400"
        >
          Generate
        </button>
      </form>

      {image && (
        <Image src={image} alt="Generated Image" width={300} height={300} />
      )}

      {info && (
        <div>
          <h2>Generated Info:</h2>
          <pre>{JSON.stringify(info, null, 2)}</pre>
        </div>
      )}

      {objFile && (
        <div>
          <h2>OBJ File:</h2>
          <a href={objFile} download="model.obj">
            Download OBJ File
          </a>
        </div>
      )}
    </div>
  );
}
