"use client";

import { motion, AnimatePresence } from "motion/react";
import {
  Key,
  User,
  Shield,
  Rocket,
  Loader2,
  Download,
  Upload,
  Check,
  AlertCircle,
  Copy,
  RefreshCw,
} from "lucide-react";
import { useState, useRef, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import {
  generateKeyPair,
  signChallenge,
  exportKeyFile,
  downloadKeyFile,
  importKeyFile,
  readKeyFileFromInput,
  type KeyPair,
} from "@/lib/crypto";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

type StepStatus = "idle" | "loading" | "success" | "error";

interface StepState {
  status: StepStatus;
  error: string;
}

const STEPS = [
  { icon: Key, title: "Generate Your Identity", description: "Create an Ed25519 key pair" },
  { icon: User, title: "Name Your Party", description: "Choose a display name" },
  { icon: Shield, title: "Register & Authenticate", description: "Sign challenge + register on Canton" },
  { icon: Rocket, title: "Ready to Build", description: "Start deploying contracts" },
];

export function SetupWizard(): ReactNode {
  const router = useRouter();
  const { login } = useAuth();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [currentStep, setCurrentStep] = useState(0);
  const [stepStates, setStepStates] = useState<StepState[]>(
    STEPS.map(() => ({ status: "idle" as StepStatus, error: "" })),
  );

  // Step 1 state
  const [keyPair, setKeyPair] = useState<KeyPair | null>(null);
  const [keyFileDownloaded, setKeyFileDownloaded] = useState(false);
  const [keyPassword, setKeyPassword] = useState("");
  const [importMode, setImportMode] = useState(false);
  const [importPassword, setImportPassword] = useState("");

  // Step 2 state
  const [partyName, setPartyName] = useState("");
  const [partyNameError, setPartyNameError] = useState("");

  // Step 3 state
  const [authSubStep, setAuthSubStep] = useState("");
  const [registeredPartyId, setRegisteredPartyId] = useState("");

  const updateStep = (index: number, update: Partial<StepState>) => {
    setStepStates((prev) => {
      const next = [...prev];
      const current = next[index] ?? { status: "idle" as StepStatus, error: "" };
      next[index] = {
        status: update.status ?? current.status,
        error: update.error ?? current.error,
      };
      return next;
    });
  };

  // ── Step 1: Generate or Import Key ──────────────────────────
  const handleGenerateKey = () => {
    updateStep(0, { status: "loading" });
    try {
      const kp = generateKeyPair();
      setKeyPair(kp);
      updateStep(0, { status: "success" });
    } catch (e) {
      updateStep(0, { status: "error", error: String(e) });
    }
  };

  const handleDownloadKey = () => {
    if (!keyPair || !keyPassword) return;
    const kf = exportKeyFile(keyPair, keyPassword);
    downloadKeyFile(kf);
    setKeyFileDownloaded(true);
  };

  const handleImportKey = async (file: File) => {
    updateStep(0, { status: "loading" });
    try {
      const kf = await readKeyFileFromInput(file);
      const kp = importKeyFile(kf, importPassword);
      if (!kp) {
        updateStep(0, { status: "error", error: "Wrong password for key file" });
        return;
      }
      setKeyPair(kp);
      setKeyFileDownloaded(true); // Already has a backup
      updateStep(0, { status: "success" });
    } catch (e) {
      updateStep(0, { status: "error", error: `Invalid key file: ${e}` });
    }
  };

  // ── Step 2: Party Name ──────────────────────────────────────
  const validatePartyName = (name: string): boolean => {
    if (name.length < 3) {
      setPartyNameError("Name must be at least 3 characters");
      return false;
    }
    if (name.length > 30) {
      setPartyNameError("Name must be 30 characters or less");
      return false;
    }
    if (!/^[a-zA-Z0-9_-]+$/.test(name)) {
      setPartyNameError("Only letters, numbers, hyphens, and underscores");
      return false;
    }
    setPartyNameError("");
    return true;
  };

  const handlePartyNameConfirm = () => {
    if (validatePartyName(partyName)) {
      updateStep(1, { status: "success" });
      setCurrentStep(2);
    }
  };

  // ── Step 3: Register & Authenticate ─────────────────────────
  const handleRegister = async () => {
    if (!keyPair) return;
    updateStep(2, { status: "loading" });

    try {
      // Sub-step 1: Get challenge
      setAuthSubStep("Requesting challenge...");
      const challengeResp = await fetch(`${API_URL}/auth/challenge`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!challengeResp.ok) {
        throw new Error(`Challenge request failed: ${challengeResp.status}`);
      }
      const { challenge } = await challengeResp.json();

      // Sub-step 2: Sign challenge
      setAuthSubStep("Signing challenge...");
      const signature = signChallenge(challenge, keyPair.secretKey);

      // Sub-step 3: Verify signature
      setAuthSubStep("Verifying signature...");
      const verifyResp = await fetch(`${API_URL}/auth/verify`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          challenge,
          signature,
          public_key: keyPair.publicKey,
        }),
      });
      if (!verifyResp.ok) {
        const data = await verifyResp.json().catch(() => ({}));
        throw new Error(data.detail || "Signature verification failed");
      }

      // Sub-step 4: Register party
      setAuthSubStep("Registering party on Canton...");
      const registerResp = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          public_key: keyPair.publicKey,
          party_name: partyName,
        }),
      });
      if (!registerResp.ok) {
        const data = await registerResp.json().catch(() => ({}));
        const detail = data.detail || "Party registration failed";
        if (registerResp.status === 502) {
          throw new Error(
            `Cannot connect to Canton sandbox. Is it running?\n${detail}`,
          );
        }
        throw new Error(detail);
      }

      const { token, party_id } = await registerResp.json();
      setRegisteredPartyId(party_id);
      setAuthSubStep("");
      updateStep(2, { status: "success" });
      setCurrentStep(3);

      // Set auth context
      login(token, party_id, partyName, keyPair.fingerprint);
    } catch (e) {
      setAuthSubStep("");
      updateStep(2, { status: "error", error: String(e) });
    }
  };

  const handleStartBuilding = () => {
    router.push("/");
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).catch(() => {});
  };

  // ── Render ──────────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      {/* Step indicators */}
      <div className="mb-12 flex items-center justify-center gap-2">
        {STEPS.map((step, i) => {
          const Icon = step.icon;
          const isActive = i === currentStep;
          const stepState = stepStates[i];
          const isDone = stepState?.status === "success";
          return (
            <div key={i} className="flex items-center gap-2">
              <div
                className={`flex h-10 w-10 items-center justify-center rounded-full border transition-all ${
                  isDone
                    ? "border-green-500/50 bg-green-500/20 text-green-400"
                    : isActive
                      ? "border-purple-500/50 bg-purple-500/20 text-purple-400"
                      : "border-white/10 bg-white/5 text-white/30"
                }`}
              >
                {isDone ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
              </div>
              {i < STEPS.length - 1 && (
                <div
                  className={`h-px w-8 transition-colors ${
                    isDone ? "bg-green-500/50" : "bg-white/10"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>

      {/* Step title */}
      <AnimatePresence mode="wait">
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.3 }}
          className="mb-8 text-center"
        >
          <h2 className="text-2xl font-bold text-white">{STEPS[currentStep]!.title}</h2>
          <p className="mt-1 text-sm text-white/50">{STEPS[currentStep]!.description}</p>
        </motion.div>
      </AnimatePresence>

      {/* Step content */}
      <AnimatePresence mode="wait">
        {/* ── STEP 1: Generate Identity ── */}
        {currentStep === 0 && (
          <motion.div
            key="step1"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="space-y-6"
          >
            {!keyPair ? (
              <div className="space-y-4">
                <div className="flex gap-3">
                  <button
                    onClick={handleGenerateKey}
                    disabled={stepStates[0]!.status === "loading"}
                    className="flex-1 rounded-xl border border-purple-500/30 bg-purple-500/10 px-6 py-4 text-left transition-all hover:border-purple-500/50 hover:bg-purple-500/20"
                  >
                    <Key className="mb-2 h-5 w-5 text-purple-400" />
                    <div className="font-semibold text-white">Generate New Key</div>
                    <div className="text-xs text-white/50">Create a fresh Ed25519 key pair</div>
                  </button>

                  <button
                    onClick={() => setImportMode(true)}
                    className="flex-1 rounded-xl border border-white/10 bg-white/5 px-6 py-4 text-left transition-all hover:border-white/20 hover:bg-white/10"
                  >
                    <Upload className="mb-2 h-5 w-5 text-white/60" />
                    <div className="font-semibold text-white">Import Key File</div>
                    <div className="text-xs text-white/50">Load an existing key file</div>
                  </button>
                </div>

                {importMode && (
                  <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
                    <input
                      type="password"
                      placeholder="Key file password"
                      value={importPassword}
                      onChange={(e) => setImportPassword(e.target.value)}
                      className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/30 focus:border-purple-500/50 focus:outline-none"
                    />
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".json"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleImportKey(file);
                      }}
                      className="w-full text-sm text-white/50 file:mr-3 file:rounded-lg file:border-0 file:bg-purple-500/20 file:px-3 file:py-1.5 file:text-sm file:text-purple-300"
                    />
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-4">
                {/* Key info */}
                <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-4">
                  <div className="flex items-center gap-2 text-sm font-medium text-green-400">
                    <Check className="h-4 w-4" />
                    Key pair generated
                  </div>
                  <div className="mt-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-white/40">Fingerprint</span>
                      <button
                        onClick={() => copyToClipboard(keyPair.fingerprint)}
                        className="flex items-center gap-1 text-xs font-mono text-white/70 hover:text-white"
                      >
                        {keyPair.fingerprint.slice(0, 20)}...
                        <Copy className="h-3 w-3" />
                      </button>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-white/40">Public Key</span>
                      <span className="text-xs font-mono text-white/50">
                        {keyPair.publicKey.slice(0, 20)}...
                      </span>
                    </div>
                  </div>
                </div>

                {/* Download key file */}
                {!keyFileDownloaded && (
                  <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
                    <div className="flex items-center gap-2 text-sm font-medium text-amber-400">
                      <AlertCircle className="h-4 w-4" />
                      Download your key file (required)
                    </div>
                    <p className="mt-1 text-xs text-white/40">
                      This is your only backup. Store it somewhere safe.
                    </p>
                    <div className="mt-3 flex gap-2">
                      <input
                        type="password"
                        placeholder="Set a password"
                        value={keyPassword}
                        onChange={(e) => setKeyPassword(e.target.value)}
                        className="flex-1 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm text-white placeholder:text-white/30 focus:border-purple-500/50 focus:outline-none"
                      />
                      <button
                        onClick={handleDownloadKey}
                        disabled={!keyPassword}
                        className="flex items-center gap-2 rounded-lg bg-amber-500/20 px-4 py-2 text-sm font-medium text-amber-300 transition-all hover:bg-amber-500/30 disabled:opacity-40"
                      >
                        <Download className="h-4 w-4" />
                        Download
                      </button>
                    </div>
                  </div>
                )}

                {keyFileDownloaded && (
                  <button
                    onClick={() => {
                      updateStep(0, { status: "success" });
                      setCurrentStep(1);
                    }}
                    className="w-full rounded-xl bg-gradient-to-r from-purple-600 to-fuchsia-600 px-6 py-3 font-semibold text-white transition-all hover:from-purple-500 hover:to-fuchsia-500"
                  >
                    Continue
                  </button>
                )}
              </div>
            )}

            {stepStates[0]!.status === "error" && (
              <div className="rounded-lg border border-red-500/20 bg-red-500/5 p-3 text-sm text-red-400">
                {stepStates[0]!.error}
              </div>
            )}
          </motion.div>
        )}

        {/* ── STEP 2: Name Your Party ── */}
        {currentStep === 1 && (
          <motion.div
            key="step2"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="space-y-6"
          >
            <div className="space-y-3">
              <label className="block text-sm text-white/60">Party Display Name</label>
              <input
                type="text"
                placeholder="e.g., my-ginie-dev"
                value={partyName}
                onChange={(e) => {
                  setPartyName(e.target.value);
                  if (partyNameError) validatePartyName(e.target.value);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handlePartyNameConfirm();
                }}
                className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-lg text-white placeholder:text-white/30 focus:border-purple-500/50 focus:outline-none"
                autoFocus
              />
              {partyNameError && (
                <p className="text-sm text-red-400">{partyNameError}</p>
              )}
              {partyName && !partyNameError && keyPair && (
                <p className="text-xs text-white/30">
                  Full ID: {partyName.toLowerCase()}::{keyPair.fingerprint.slice(0, 16)}...
                </p>
              )}
            </div>

            <button
              onClick={handlePartyNameConfirm}
              disabled={!partyName || !!partyNameError}
              className="w-full rounded-xl bg-gradient-to-r from-purple-600 to-fuchsia-600 px-6 py-3 font-semibold text-white transition-all hover:from-purple-500 hover:to-fuchsia-500 disabled:opacity-40"
            >
              Continue
            </button>
          </motion.div>
        )}

        {/* ── STEP 3: Register & Authenticate ── */}
        {currentStep === 2 && (
          <motion.div
            key="step3"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -20 }}
            className="space-y-6"
          >
            {stepStates[2]!.status === "idle" && (
              <div className="space-y-4">
                <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-2">
                  <div className="flex justify-between text-sm">
                    <span className="text-white/40">Party Name</span>
                    <span className="text-white">{partyName}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-white/40">Fingerprint</span>
                    <span className="font-mono text-xs text-white/60">
                      {keyPair?.fingerprint.slice(0, 24)}...
                    </span>
                  </div>
                </div>

                <button
                  onClick={handleRegister}
                  className="w-full rounded-xl bg-gradient-to-r from-purple-600 to-fuchsia-600 px-6 py-3 font-semibold text-white transition-all hover:from-purple-500 hover:to-fuchsia-500"
                >
                  Register on Canton
                </button>
              </div>
            )}

            {stepStates[2]!.status === "loading" && (
              <div className="flex flex-col items-center gap-4 py-8">
                <Loader2 className="h-8 w-8 animate-spin text-purple-400" />
                <p className="text-sm text-white/60">{authSubStep}</p>
              </div>
            )}

            {stepStates[2]!.status === "error" && (
              <div className="space-y-4">
                <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-4">
                  <div className="flex items-center gap-2 text-sm font-medium text-red-400">
                    <AlertCircle className="h-4 w-4" />
                    Registration failed
                  </div>
                  <p className="mt-2 text-xs text-white/50 whitespace-pre-line">
                    {stepStates[2]!.error}
                  </p>
                </div>
                <button
                  onClick={handleRegister}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-6 py-3 font-semibold text-white transition-all hover:bg-white/10"
                >
                  <RefreshCw className="h-4 w-4" />
                  Retry
                </button>
              </div>
            )}
          </motion.div>
        )}

        {/* ── STEP 4: Ready ── */}
        {currentStep === 3 && (
          <motion.div
            key="step4"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="space-y-6"
          >
            <div className="rounded-xl border border-green-500/20 bg-green-500/5 p-6 text-center">
              <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-500/20">
                <Check className="h-8 w-8 text-green-400" />
              </div>
              <h3 className="text-lg font-bold text-white">You&apos;re all set!</h3>
              <p className="mt-1 text-sm text-white/50">
                Your identity is registered on Canton sandbox.
              </p>
            </div>

            <div className="rounded-xl border border-white/10 bg-white/5 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-white/40">Party ID</span>
                <button
                  onClick={() => copyToClipboard(registeredPartyId)}
                  className="flex items-center gap-1 text-xs font-mono text-white/70 hover:text-white"
                >
                  {registeredPartyId.length > 30
                    ? `${registeredPartyId.slice(0, 30)}...`
                    : registeredPartyId}
                  <Copy className="h-3 w-3" />
                </button>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-white/40">Display Name</span>
                <span className="text-sm text-white">{partyName}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-white/40">Session</span>
                <span className="text-sm text-green-400">Active (7 days)</span>
              </div>
            </div>

            <button
              onClick={handleStartBuilding}
              className="w-full rounded-xl bg-gradient-to-r from-purple-600 to-fuchsia-600 px-6 py-4 text-lg font-bold text-white transition-all hover:from-purple-500 hover:to-fuchsia-500 hover:shadow-[0_0_24px_rgba(168,85,247,0.4)]"
            >
              <span className="flex items-center justify-center gap-2">
                <Rocket className="h-5 w-5" />
                Start Building
              </span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
