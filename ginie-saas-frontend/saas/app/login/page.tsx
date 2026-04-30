"use client";

import { useState, useEffect, useRef, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Mail,
  ArrowRight,
  ArrowLeft,
  Ticket,
  RefreshCw,
  CheckCircle2,
} from "lucide-react";

import { useAuth } from "@/lib/auth-context";
import { OTPInput } from "@/components/auth/OTPInput";
import { ProfilePicturePicker } from "@/components/auth/ProfilePicturePicker";
import { SignupStepper, type SignupStepIndex } from "@/components/auth/SignupStepper";

type Mode = "signin" | "signup";
type SignupStep = "email" | "verify" | "details";

const OTP_LENGTH = 6;
const RESEND_COOLDOWN_SECONDS = 30;
const INVITE_PATTERN = /^GS-[A-Z0-9]{4}-[A-Z0-9]{4}$/i;

export default function LoginPage(): ReactNode {
  const router = useRouter();
  const {
    loginEmail,
    signupEmail,
    sendOTP,
    verifyOTP,
    uploadProfilePictureSignup,
  } = useAuth();

  const [mode, setMode] = useState<Mode>("signin");

  // Sign-in state
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  // Sign-up state
  const [signupStep, setSignupStep] = useState<SignupStep>("email");
  const [otp, setOTP] = useState("");
  const [otpError, setOtpError] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [displayName, setDisplayName] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [profileBlob, setProfileBlob] = useState<Blob | null>(null);
  const [profilePreviewUrl, setProfilePreviewUrl] = useState<string | null>(null);

  // Reset signup flow when switching modes
  const switchMode = (next: Mode) => {
    setMode(next);
    setError("");
    setOtpError(false);
    if (next === "signup") {
      setSignupStep("email");
      setOTP("");
    }
  };

  // Resend cooldown ticker
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const t = setInterval(() => setResendCooldown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(t);
  }, [resendCooldown]);

  // Cleanup blob URL
  const lastBlobUrlRef = useRef<string | null>(null);
  useEffect(() => {
    if (lastBlobUrlRef.current && lastBlobUrlRef.current !== profilePreviewUrl) {
      URL.revokeObjectURL(lastBlobUrlRef.current);
    }
    lastBlobUrlRef.current = profilePreviewUrl;
  }, [profilePreviewUrl]);

  const handleProfileChange = (blob: Blob | null) => {
    setProfileBlob(blob);
    if (blob) {
      setProfilePreviewUrl(URL.createObjectURL(blob));
    } else {
      setProfilePreviewUrl(null);
    }
  };

  // ── Sign-in submit ───────────────────────────────────────────
  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!email.includes("@")) return setError("Please enter a valid email address.");
    if (password.length < 8) return setError("Password must be at least 8 characters.");

    setSubmitting(true);
    try {
      const result = await loginEmail(email, password);
      router.push(result.needsParty ? "/setup" : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
    } finally {
      setSubmitting(false);
    }
  };

  // ── Sign-up: Step 1 - send OTP ───────────────────────────────
  const handleSendOTP = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setError("");
    if (!email.includes("@") || email.length < 5) {
      return setError("Please enter a valid email address.");
    }
    setSubmitting(true);
    try {
      await sendOTP(email, displayName || undefined);
      setSignupStep("verify");
      setResendCooldown(RESEND_COOLDOWN_SECONDS);
      setOTP("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send code");
    } finally {
      setSubmitting(false);
    }
  };

  // ── Sign-up: Step 2 - verify OTP ─────────────────────────────
  const handleVerifyOTP = async (code?: string) => {
    const value = code ?? otp;
    setError("");
    setOtpError(false);
    if (value.length !== OTP_LENGTH) {
      setOtpError(true);
      return setError("Please enter the 6-digit code");
    }
    setSubmitting(true);
    try {
      await verifyOTP(email, value);
      setSignupStep("details");
    } catch (err) {
      setOtpError(true);
      setError(err instanceof Error ? err.message : "Invalid code");
    } finally {
      setSubmitting(false);
    }
  };

  const handleResendOTP = async () => {
    if (resendCooldown > 0 || submitting) return;
    setOTP("");
    setOtpError(false);
    await handleSendOTP();
  };

  // ── Sign-up: Step 3 - finalize signup ────────────────────────
  const handleCompleteSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (password.length < 8) return setError("Password must be at least 8 characters.");
    if (!inviteCode) return setError("Invite code is required.");
    if (!INVITE_PATTERN.test(inviteCode)) {
      return setError("Invalid invite code format. Use: GS-XXXX-XXXX");
    }

    setSubmitting(true);
    try {
      // Upload profile picture first (optional)
      if (profileBlob) {
        try {
          await uploadProfilePictureSignup(email, profileBlob);
        } catch (uploadErr) {
          // Non-fatal: continue with signup, log warning
          console.warn("Profile picture upload failed", uploadErr);
        }
      }

      const result = await signupEmail(email, password, displayName || undefined, inviteCode);
      router.push(result.needsParty ? "/setup" : "/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setSubmitting(false);
    }
  };

  const stepIndex: SignupStepIndex =
    signupStep === "email" ? 0 : signupStep === "verify" ? 1 : 2;

  return (
    <main className="relative min-h-dvh bg-background overflow-hidden">
      {/* Decorative background */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 opacity-60"
        style={{
          backgroundImage:
            "radial-gradient(ellipse 60% 50% at 50% -10%, rgba(168, 217, 70, 0.15), transparent 60%), radial-gradient(ellipse 40% 30% at 80% 110%, rgba(168, 217, 70, 0.08), transparent 60%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(255,255,255,0.04) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.04) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
          maskImage: "radial-gradient(ellipse at center, black 30%, transparent 80%)",
          WebkitMaskImage:
            "radial-gradient(ellipse at center, black 30%, transparent 80%)",
        }}
      />

      <div className="relative mx-auto flex min-h-dvh max-w-md flex-col items-center justify-center px-6 pt-20 pb-16">
        {/* Brand */}
        <div className="mb-7 flex flex-col items-center gap-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/ginie-logo.ico"
            alt="Ginie"
            className="h-12 w-12 rounded-xl shadow-lg shadow-accent/20"
          />
          <span
            style={{ fontFamily: "EB Garamond, serif" }}
            className="text-3xl font-semibold text-accent leading-none"
          >
            Ginie
          </span>
          <span className="text-[10px] uppercase tracking-[0.25em] text-muted-foreground">
            Canton Network
          </span>
        </div>

        {/* Card */}
        <div className="w-full rounded-2xl border border-border bg-frame/80 backdrop-blur-xl p-7 sm:p-8 shadow-2xl shadow-black/30">
          {/* Header */}
          <div className="mb-6 text-center">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground">
              {mode === "signin" ? "Welcome back" : "Create your account"}
            </h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              {mode === "signin"
                ? "Sign in to continue building on Canton."
                : signupStep === "email"
                  ? "Start by entering your email — we'll send a verification code."
                  : signupStep === "verify"
                    ? "Check your inbox for the 6-digit code."
                    : "Almost done — set up your profile and password."}
            </p>
          </div>

          {/* Stepper for signup */}
          {mode === "signup" && <SignupStepper current={stepIndex} />}

          {/* ─── SIGN IN ─── */}
          {mode === "signin" && (
            <form onSubmit={handleSignIn} className="space-y-4">
              <Field label="Email">
                <InputWithIcon
                  icon={Mail}
                  type="email"
                  value={email}
                  onChange={setEmail}
                  placeholder="you@example.com"
                  required
                  autoComplete="email"
                />
              </Field>
              <Field label="Password" rightHint="Forgot password?" onRightHintClick={() => alert("Contact support@ginie.dev for password recovery.")}>
                <InputWithIcon
                  icon={Lock}
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={setPassword}
                  placeholder="Enter your password"
                  required
                  minLength={8}
                  autoComplete="current-password"
                  rightAdornment={
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  }
                />
              </Field>

              <ErrorBanner message={error} />
              <SubmitButton submitting={submitting} label="Sign In" />
            </form>
          )}

          {/* ─── SIGN UP - STEP 1: EMAIL ─── */}
          {mode === "signup" && signupStep === "email" && (
            <form onSubmit={handleSendOTP} className="space-y-4">
              <Field label="Display Name" hint="(optional)">
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Your name"
                  className={inputClass}
                  maxLength={60}
                />
              </Field>
              <Field label="Email">
                <InputWithIcon
                  icon={Mail}
                  type="email"
                  value={email}
                  onChange={setEmail}
                  placeholder="you@example.com"
                  required
                  autoComplete="email"
                />
              </Field>

              <ErrorBanner message={error} />
              <SubmitButton submitting={submitting} label="Send verification code" />
            </form>
          )}

          {/* ─── SIGN UP - STEP 2: OTP VERIFY ─── */}
          {mode === "signup" && signupStep === "verify" && (
            <div className="space-y-5">
              <div className="text-center text-xs text-muted-foreground">
                Sent to <span className="text-foreground font-medium">{email}</span>
              </div>

              <OTPInput
                length={OTP_LENGTH}
                value={otp}
                onChange={(v) => {
                  setOTP(v);
                  setOtpError(false);
                  if (error) setError("");
                }}
                onComplete={(v) => handleVerifyOTP(v)}
                disabled={submitting}
                error={otpError}
              />

              <ErrorBanner message={error} />

              <button
                type="button"
                onClick={() => handleVerifyOTP()}
                disabled={submitting || otp.length !== OTP_LENGTH}
                className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-accent px-5 py-3 text-sm font-semibold text-black shadow-lg shadow-accent/30 hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60 transition-colors"
              >
                {submitting ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Verifying...
                  </>
                ) : (
                  <>
                    Verify code <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>

              <div className="flex items-center justify-between text-xs">
                <button
                  type="button"
                  onClick={() => {
                    setSignupStep("email");
                    setOTP("");
                    setError("");
                    setOtpError(false);
                  }}
                  className="text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
                >
                  <ArrowLeft className="h-3 w-3" /> Change email
                </button>
                <button
                  type="button"
                  onClick={handleResendOTP}
                  disabled={resendCooldown > 0 || submitting}
                  className="text-muted-foreground hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1"
                >
                  <RefreshCw className="h-3 w-3" />
                  {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : "Resend code"}
                </button>
              </div>
            </div>
          )}

          {/* ─── SIGN UP - STEP 3: PROFILE + PASSWORD + INVITE ─── */}
          {mode === "signup" && signupStep === "details" && (
            <form onSubmit={handleCompleteSignup} className="space-y-5">
              <div className="flex justify-center">
                <ProfilePicturePicker
                  value={profilePreviewUrl}
                  onChange={handleProfileChange}
                  email={email}
                />
              </div>

              <Field label="Invite Code" required>
                <InputWithIcon
                  icon={Ticket}
                  type="text"
                  value={inviteCode}
                  onChange={(v) => setInviteCode(v.toUpperCase())}
                  placeholder="GS-XXXX-XXXX"
                  required
                  maxLength={13}
                  pattern="GS-[A-Z0-9]{4}-[A-Z0-9]{4}"
                  className="font-mono tracking-wider"
                />
              </Field>

              <Field label="Password">
                <InputWithIcon
                  icon={Lock}
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={setPassword}
                  placeholder="Create a strong password"
                  required
                  minLength={8}
                  autoComplete="new-password"
                  rightAdornment={
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  }
                />
              </Field>

              <div className="flex items-center gap-2 text-xs text-accent">
                <CheckCircle2 className="h-3.5 w-3.5" /> Email verified
              </div>

              <ErrorBanner message={error} />

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setSignupStep("verify");
                    setError("");
                  }}
                  className="px-4 py-3 rounded-full border border-border bg-muted text-sm text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
                >
                  <ArrowLeft className="h-4 w-4" />
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 inline-flex items-center justify-center gap-2 rounded-full bg-accent px-5 py-3 text-sm font-semibold text-black shadow-lg shadow-accent/30 hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60 transition-colors"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" /> Creating account...
                    </>
                  ) : (
                    <>
                      Create account <ArrowRight className="h-4 w-4" />
                    </>
                  )}
                </button>
              </div>
            </form>
          )}

          {/* Mode switch */}
          <div className="mt-6 text-center text-sm text-muted-foreground">
            {mode === "signin" ? (
              <>
                No account?{" "}
                <button
                  type="button"
                  onClick={() => switchMode("signup")}
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
                  onClick={() => switchMode("signin")}
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

// ─────────────────────────────────────────────────────────────
// Reusable form primitives
// ─────────────────────────────────────────────────────────────

const inputClass =
  "w-full rounded-xl border border-border bg-muted px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20 transition-colors";

function Field({
  label,
  hint,
  required,
  rightHint,
  onRightHintClick,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  rightHint?: string;
  onRightHintClick?: () => void;
  children: ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <label className="text-sm font-medium text-foreground">
          {label}
          {required && <span className="text-red-500 ml-0.5">*</span>}
          {hint && <span className="text-muted-foreground ml-1.5 font-normal">{hint}</span>}
        </label>
        {rightHint && (
          <button
            type="button"
            onClick={onRightHintClick}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            {rightHint}
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

interface InputWithIconProps {
  icon: React.ComponentType<{ className?: string }>;
  type: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
  minLength?: number;
  maxLength?: number;
  pattern?: string;
  autoComplete?: string;
  className?: string;
  rightAdornment?: ReactNode;
}

function InputWithIcon({
  icon: Icon,
  type,
  value,
  onChange,
  placeholder,
  required,
  minLength,
  maxLength,
  pattern,
  autoComplete,
  className,
  rightAdornment,
}: InputWithIconProps) {
  return (
    <div className="relative">
      <Icon className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        required={required}
        minLength={minLength}
        maxLength={maxLength}
        pattern={pattern}
        autoComplete={autoComplete}
        className={`${inputClass} pl-10 ${rightAdornment ? "pr-10" : ""} ${className ?? ""}`}
      />
      {rightAdornment && (
        <div className="absolute right-3 top-1/2 -translate-y-1/2">{rightAdornment}</div>
      )}
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  if (!message) return null;
  return (
    <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-500 dark:text-red-300">
      {message}
    </div>
  );
}

function SubmitButton({ submitting, label }: { submitting: boolean; label: string }) {
  return (
    <button
      type="submit"
      disabled={submitting}
      className="inline-flex w-full items-center justify-center gap-2 rounded-full bg-accent px-5 py-3 text-sm font-semibold text-black shadow-lg shadow-accent/30 hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-60 transition-colors"
    >
      {submitting ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" /> Working...
        </>
      ) : (
        <>
          {label} <ArrowRight className="h-4 w-4" />
        </>
      )}
    </button>
  );
}
