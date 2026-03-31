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
    <html lang="en">
      <body className="bg-white text-[#1f2328] min-h-screen flex" style={{ fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif' }}>
        <Sidebar />
        <main className="flex-1 ml-56 p-6 max-w-[1280px]">{children}</main>
      </body>
    </html>
  );
}
