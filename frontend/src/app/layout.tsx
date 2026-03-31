import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "Claude Context Manager",
  description: "Browse, clone, and manage Claude Code session memory",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-zinc-950 text-zinc-300 min-h-screen flex">
        <Sidebar />
        <main className="flex-1 ml-56 p-6">{children}</main>
      </body>
    </html>
  );
}
