import type { Metadata } from "next";
import "./globals.css";
import { Toaster } from "react-hot-toast";

export const metadata: Metadata = {
  title: "Ginie — Canton Smart Contract Generator",
  description: "Describe your contract in plain English. Ginie generates, compiles, and deploys it to Canton Network automatically.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <nav className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4" style={{ background: "rgba(10, 13, 26, 0.85)", backdropFilter: "blur(12px)", borderBottom: "1px solid rgba(30, 42, 74, 0.6)" }}>
          <a href="/" className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "linear-gradient(135deg, #5a6bff, #3d4df5)" }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="16 18 22 12 16 6" />
                <polyline points="8 6 2 12 8 18" />
              </svg>
            </div>
            <span className="font-bold text-lg" style={{ color: "#e8eaf6" }}>Ginie</span>
            <span className="text-xs px-2 py-0.5 rounded-full font-medium" style={{ background: "rgba(90, 107, 255, 0.15)", color: "#818cf8", border: "1px solid rgba(90, 107, 255, 0.3)" }}>Canton Network</span>
          </a>
          <div className="flex items-center gap-4">
            <a href="https://docs.daml.com" target="_blank" rel="noopener noreferrer" className="text-sm transition-colors" style={{ color: "#6b7280" }}>
              Daml Docs
            </a>
            <a href="https://canton.network" target="_blank" rel="noopener noreferrer" className="text-sm transition-colors" style={{ color: "#6b7280" }}>
              Canton Network
            </a>
          </div>
        </nav>
        <main className="pt-16">
          {children}
        </main>
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "#0f1429",
              color: "#e8eaf6",
              border: "1px solid rgba(30, 42, 74, 0.8)",
              borderRadius: "12px",
            },
          }}
        />
      </body>
    </html>
  );
}
