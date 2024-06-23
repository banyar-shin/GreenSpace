import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET() {
  const imgDir = path.join(process.cwd(), "img");
  const files = fs.readdirSync(imgDir);
  const latestFile = files.reduce((latest, file) => {
    const filePath = path.join(imgDir, file);
    const stats = fs.statSync(filePath);
    return !latest || stats.mtime > fs.statSync(path.join(imgDir, latest)).mtime
      ? file
      : latest;
  });

  const imagePath = path.join(imgDir, latestFile);
  const imageBuffer = fs.readFileSync(imagePath);

  return new NextResponse(imageBuffer, {
    headers: { "Content-Type": "image/jpeg" }, // Adjust content type if necessary
  });
}
