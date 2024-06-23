import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET() {
  const infoDir = path.join(process.cwd(), "info");
  const files = fs.readdirSync(infoDir);
  const latestFile = files.reduce((latest, file) => {
    const filePath = path.join(infoDir, file);
    const stats = fs.statSync(filePath);
    return !latest ||
      stats.mtime > fs.statSync(path.join(infoDir, latest)).mtime
      ? file
      : latest;
  });

  const infoPath = path.join(infoDir, latestFile);
  const infoData = JSON.parse(fs.readFileSync(infoPath, "utf-8"));

  return NextResponse.json(infoData);
}
