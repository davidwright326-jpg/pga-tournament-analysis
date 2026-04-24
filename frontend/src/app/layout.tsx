import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PGA Tournament Analysis",
  description: "Identify key stats and top players for the current PGA Tour event",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 min-h-screen">
        <nav className="bg-green-800 text-white px-6 py-3 flex items-center gap-6" role="navigation" aria-label="Main navigation">
          <a href="/" className="text-lg font-bold">PGA Analysis</a>
          <a href="/" className="hover:underline">Dashboard</a>
          <a href="/history" className="hover:underline">Course History</a>
          <a href="/season" className="hover:underline">Season Results</a>
        </nav>
        <main className="max-w-7xl mx-auto px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
