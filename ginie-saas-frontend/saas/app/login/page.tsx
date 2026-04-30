"use client";

import { useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Eye, EyeOff, Loader2, Lock, Mail, ArrowRight } from "lucide-react";
import { useAuth } from "@/lib/auth-context";

type Mode = "signin" | "signup";

export default function LoginPage(): ReactNode {
  const router = useRouter();
  const { loginEmail, signupEmail } = useAuth();

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!email.includes("@")) {
      setError("Please enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (mode === "signup" && !inviteCode) {
      setError("Invite code is required for signup.");
      return;
    }
    if (mode === "signup" && !/^GS-[A-Z0-9]{4}-[A-Z0-9]{4}$/i.test(inviteCode)) {
      setError("Invalid invite code format. Use: GS-XXXX-XXXX");
      return;
    }

    setSubmitting(true);
    try {
      const result =
        mode === "signin"
          ? await loginEmail(email, password)
          : await signupEmail(email, password, displayName || undefined, inviteCode);

      if (result.needsParty) {
        router.push("/setup");
      } else {
        router.push("/");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Authentication failed";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="relative min-h-dvh bg-background">
      <div className="mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-6 pt-28 pb-16">
        <div className="mb-8 flex flex-col items-center gap-3">
          <img
            src="/ginie-logo.ico"
            alt="Ginie"
            className="h-12 w-12 rounded-xl"
          />
          <span
            style={{ fontFamily: "EB Garamond, serif" }}
            className="text-3xl font-semibold text-accent leading-none"
          >
            Ginie
          </span>
          <span className="text-xs uppercase tracking-[0.2em] text-muted-foreground">
            Canton Network
          </span>
        </div>

        <div className="w-full rounded-2xl border border-border bg-frame p-7 shadow-xl">
          <h1 className="text-xl font-semibold text-foreground">
            {mode === "signin" ? "Sign In" : "Create Account"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === "signin"
              ? "Welcome back to Ginie"
              : "Sign up to deploy Daml contracts on Canton"}
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            {mode === "signup" && (
              <>
                <div>
                  <label className="text-sm font-medium text-foreground">
                    Display Name <span className="text-muted-foreground">(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder="Your name"
                    className="mt-1.5 w-full rounded-xl border border-border bg-muted px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                    maxLength={60}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">
                    Invite Code <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={inviteCode}
                    onChange={(e) => setInviteCode(e.target.value.toUpperCase())}
                    placeholder="GS-XXXX-XXXX"
                    required
                    pattern="GS-[A-Z0-9]{4}-[A-Z0-9]{4}"
                    className="mt-1.5 w-full rounded-xl border border-border bg-muted px-4 py-2.5 text-sm font-mono text-foreground placeholder:text-muted-foreground/60 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                    maxLength={13}
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    Enter your invite code to create an account
                  </p>
                </div>
              </>
            )}

            <div>
              <label className="text-sm font-medium text-foreground">Email</label>
              <div className="relative mt-1.5">
                <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoComplete="email"
                  className="w-full rounded-xl border border-border bg-muted pl-10 pr-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                />
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-foreground">Password</label>
              <div className="relative mt-1.5">
                <Lock className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password"
                  required
                  minLength={8}
                  autoComplete={mode === "signin" ? "current-password" : "new-password"}
                  className="w-full rounded-xl border border-border bg-muted pl-10 pr-10 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                </button>
              </div>
              {mode === "signin" && (
                <div className="mt-1.5 text-right">
                  <button
                    type="button"
                    className="text-xs text-muted-foreground hover:text-foreground transition-colors"
                    onClick={() =>
                      alert(
                        "Password reset isn't available yet. Contact support@ginie.dev to recover access.",
                      )
                    }
                  >
                    Forgot password?
                  </button>
                </div>
              )}
            </div>

            {error && (
              <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-500 dark:text-red-300">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-accent px-5 py-3 text-sm font-semibold text-black shadow-lg shadow-accent/30 hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60 transition-colors"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {mode === "signin" ? "Signing in..." : "Creating account..."}
                </>
              ) : (
                <>
                  {mode === "signin" ? "Sign In" : "Create Account"}
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center text-sm text-muted-foreground">
            {mode === "signin" ? (
              <>
                No account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setMode("signup");
                    setError("");
                  }}
                  className="font-semibold text-accent hover:underline"
                >
                  Create one
                </button>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => {
                    setMode("signin");
                    setError("");
                  }}
                  className="font-semibold text-accent hover:underline"
                >
                  Sign in
                </button>
              </>
            )}
          </div>
        </div>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          Prefer key-based auth?{" "}
          <Link href="/setup" className="text-foreground hover:underline">
            Use Ed25519 party identity
          </Link>
        </p>
      </div>
    </main>
  );
}
