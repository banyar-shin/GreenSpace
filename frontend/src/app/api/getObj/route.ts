import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export async function GET() {
  const objDir = path.join(process.cwd(), "obj"); // Adjust this path as needed
  const files = fs.readdirSync(objDir).filter((file) => file.endsWith(".obj"));
  const latestFile = files.reduce((latest, file) => {
    const filePath = path.join(objDir, file);
    const stats = fs.statSync(filePath);
    return !latest || stats.mtime > fs.statSync(path.join(objDir, latest)).mtime
      ? file
      : latest;
  });

  const objPath = path.join(objDir, latestFile);
  const objBuffer = fs.readFileSync(objPath);

  return new NextResponse(objBuffer, {
    headers: {
      "Content-Type": "application/octet-stream",
      "Content-Disposition": `attachment; filename="${latestFile}"`,
    },
  });
}
