import type { Metadata } from "next";
import Navbar from "./components/navbar";
import { Darker_Grotesque } from "next/font/google";
import "./globals.css";

const darker = Darker_Grotesque({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "GreenSpace",
  description: "Combining XR and AI to create a better world",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`bg-orange-100 min-h-screen ${darker.className}`}>
        <Navbar />
        {children}
      </body>
    </html>
  );
}
