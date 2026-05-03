"use client";

import { Lock, Loader2, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export default function AdminLoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // If already authenticated, jump straight to analytics
  useEffect(() => {
    if (typeof window !== "undefined") {
      const cached = sessionStorage.getItem("ginie_admin_password");
      if (cached) {
        router.replace("/admin/analytics");
      }
    }
  }, [router]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!password.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_URL}/admin/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: password.trim() }),
      });
      if (resp.status === 401) {
        setError("Incorrect password.");
        return;
      }
      if (!resp.ok) {
        setError("Unable to verify password. Please try again.");
        return;
      }
      sessionStorage.setItem("ginie_admin_password", password.trim());
      router.push("/admin/analytics");
    } catch {
      setError("Network error. Please check your connection.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-neutral-50 via-white to-accent/5 px-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-xl border border-neutral-200 overflow-hidden">
          <div className="bg-gradient-to-br from-neutral-900 to-neutral-800 px-8 py-10 text-center">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-accent/20 mb-4">
              <ShieldCheck className="w-7 h-7 text-accent" />
            </div>
            <h1 className="text-2xl font-semibold text-white mb-1">
              Admin Access
            </h1>
            <p className="text-sm text-neutral-300">
              Enter your password to view the analytics dashboard.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="p-8 space-y-5">
            <div>
              <label
                htmlFor="admin-password"
                className="block text-xs font-medium text-neutral-700 uppercase tracking-wider mb-2"
              >
                Password
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
                <input
                  id="admin-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter admin password"
                  autoFocus
                  className="w-full pl-10 pr-4 py-3 rounded-xl border border-neutral-200 bg-white text-neutral-900 placeholder:text-neutral-400 focus:outline-none focus:ring-2 focus:ring-accent/50 focus:border-accent text-sm"
                />
              </div>
            </div>

            {error && (
              <div className="rounded-lg border border-red-300/60 bg-red-50 px-3 py-2 text-[13px] text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !password.trim()}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl bg-black text-white font-medium text-sm transition-all hover:bg-neutral-800 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Verifying...
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  Access Dashboard
                </>
              )}
            </button>

            <p className="text-[11px] text-neutral-400 text-center">
              Unauthorized access is logged and monitored.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
