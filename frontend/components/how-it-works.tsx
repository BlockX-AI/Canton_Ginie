"use client";

import { ArrowUpRight, Loader2 } from "lucide-react";
import HlsVideo from "./HlsVideo";
import { useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

const HLS_SRC = "https://stream.mux.com/9JXDljEVWYwWu01PUkAemafDugK89o01BR6zqJ3aS9u00A.m3u8";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export function HowItWorks(): ReactNode {
  const router = useRouter();
  const { token, isAuthenticated } = useAuth();
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleGenerate = async () => {
    const text = prompt.trim();
    if (!text) {
      setError("Please describe the contract you want to generate.");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (isAuthenticated && token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
      const resp = await fetch(`${API_URL}/generate`, {
        method: "POST",
        headers,
        body: JSON.stringify({ prompt: text }),
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({})) as Record<string, unknown>;
        throw new Error((data["detail"] as string) ?? `Server error ${resp.status}`);
      }
      const data = await resp.json() as { job_id: string };
      router.push(`/sandbox/${data.job_id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start generation");
      setLoading(false);
    }
  };

  return (
    <section
      id="process"
      className="relative w-full overflow-hidden"
      style={{ minHeight: "700px" }}
    >
      {/* HLS Background Video */}
      <HlsVideo
        src={HLS_SRC}
        className="absolute inset-0 w-full h-full object-cover z-0"
      />

      {/* Top fade */}
      <div
        className="absolute top-0 left-0 right-0 z-[1]"
        style={{
          height: "200px",
          background: "linear-gradient(to bottom, black, transparent)",
        }}
      />

      {/* Bottom fade */}
      <div
        className="absolute bottom-0 left-0 right-0 z-[1]"
        style={{
          height: "200px",
          background: "linear-gradient(to top, black, transparent)",
        }}
      />

      {/* Content */}
      <div className="relative z-10 flex flex-col items-center text-center px-6 pt-24 pb-16">
        
        <div className="w-full max-w-6xl mx-auto mt-4">
          <div className="bg-white/6 backdrop-blur-md border-t border-b border-white/20 rounded-2xl p-6 flex flex-col md:flex-row gap-6 items-start">
            {/* Left: big prompt area */}
            <div className="md:flex-1">
              <div className="flex items-center gap-3 mb-3">
              
                <div className="w-full text-center">
                  <div
                    className="text-3xl md:text-4xl text-white font-medium"
                    style={{ fontFamily: "EB Garamond, serif" }}
                  >
                    Describe your contract
                  </div>
                </div>
              </div>

              <textarea
                id="prompt"
                placeholder="e.g. Create a bond contract between an issuer and investor with a fixed coupon rate, maturity date, and early redemption option..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                    void handleGenerate();
                  }
                }}
                className="w-full h-48 md:h-36 rounded-lg bg-transparent border border-white/10 p-4 placeholder-white/60 text-white resize-none focus:border-accent/50 focus:outline-none"
              />

              {error && (
                <p className="mt-2 text-sm text-red-400">{error}</p>
              )}

              <div className="mt-6">
                <button
                  type="button"
                  onClick={() => void handleGenerate()}
                  disabled={loading || !prompt.trim()}
                  className="rounded-full px-5 py-3 hover:bg-white/20 text-white font-medium inline-flex items-center gap-3 border-t border-b border-white/20 disabled:opacity-40 disabled:cursor-not-allowed transition-all"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <ArrowUpRight className="w-4 h-4" />
                  )}
                  {loading ? "Starting pipeline..." : "Generate & Deploy"}
                </button>
              </div>
            </div>

            {/* Right: pipeline */}
            <aside className="md:w-80">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-white font-semibold">Pipeline</h3>
              </div>

              <ol className="space-y-3">
                {[
                  'Intent Analysis',
                  'Pattern Search',
                  'Code Generation',
                  'Compilation',
                  'Security Audit',
                  'Deploy to Canton',
                ].map((step, i) => (
                  <li key={step} className="bg-white/5 rounded-lg p-3 flex items-start gap-3">
                    <div className="w-7 h-7 rounded-full bg-white/10 text-white flex items-center justify-center text-sm font-semibold">{i + 1}</div>
                    <div className="text-left">
                      <div className="text-sm text-white font-medium">{step}</div>
                      <div className="text-xs text-white/60">{i === 0 ? 'Understand your requirements' : i === 1 ? 'Find matching DAML patterns' : i === 2 ? 'AI writes production DAML' : i === 3 ? 'Verify with DAML SDK' : i === 4 ? 'Automated vulnerability checks' : 'Live on the ledger'}</div>
                    </div>
                  </li>
                ))}
              </ol>
            </aside>
          </div>
        </div>
      </div>
    </section>
  );
}
