"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  ArrowLeft,
  Loader2,
  CheckCircle2,
  XCircle,
  Code2,
  Copy,
  Check,
  ArrowRight,
  Package,
  FileText,
  Sparkles,
} from "lucide-react";
import Link from "next/link";

interface JobStatus {
  job_id: string;
  status: "queued" | "running" | "complete" | "failed";
  current_step: string;
  progress: number;
  error_message?: string;
}

interface JobResult {
  job_id: string;
  status: string;
  contract_id?: string;
  package_id?: string;
  generated_code?: string;
  error_message?: string;
  compile_errors?: string[];
  fallback_used?: boolean;
  template?: string;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="ml-2 shrink-0 rounded-md p-1.5 text-white/30 transition-colors hover:bg-white/10 hover:text-white/60"
      title="Copy"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-green-400" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
}

const pipelineSteps = [
  { label: "Analyzing", minProgress: 0 },
  { label: "Generating", minProgress: 20 },
  { label: "Compiling", minProgress: 45 },
  { label: "Deploying", minProgress: 75 },
  { label: "Verifying", minProgress: 90 },
];

export default function SandboxPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.jobId as string;

  const [status, setStatus] = useState<JobStatus | null>(null);
  const [result, setResult] = useState<JobResult | null>(null);
  const [showCode, setShowCode] = useState(false);

  const API_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  useEffect(() => {
    if (!jobId) return;

    const pollStatus = async () => {
      try {
        const response = await fetch(`${API_URL}/status/${jobId}`, {
          headers: { "ngrok-skip-browser-warning": "true" },
        });
        if (!response.ok) {
          if (response.status === 404) {
            router.push("/");
          }
          return;
        }

        const statusData: JobStatus = await response.json();
        setStatus(statusData);

        if (
          statusData.status === "complete" ||
          statusData.status === "failed"
        ) {
          fetchResult();
        } else {
          setTimeout(pollStatus, 2000);
        }
      } catch (error) {
        console.error("Polling error:", error);
        setTimeout(pollStatus, 2000);
      }
    };

    const fetchResult = async () => {
      try {
        const response = await fetch(`${API_URL}/result/${jobId}`, {
          headers: { "ngrok-skip-browser-warning": "true" },
        });
        if (!response.ok) return;

        const resultData: JobResult = await response.json();
        setResult(resultData);
      } catch (error) {
        console.error("Error fetching result:", error);
      }
    };

    pollStatus();
  }, [jobId, API_URL, router]);

  const isProcessing =
    status?.status === "queued" || status?.status === "running";

  return (
    <div className="min-h-screen bg-[#03040A]">
      {/* Subtle grid background */}
      <div
        className="pointer-events-none fixed inset-0"
        style={{
          backgroundImage:
            "radial-gradient(rgba(168,85,247,0.03) 1px, transparent 1px)",
          backgroundSize: "32px 32px",
        }}
      />

      <div className="relative mx-auto max-w-3xl px-4 py-8 sm:px-6 sm:py-12">
        {/* Back nav */}
        <Link
          href="/"
          className="group mb-8 inline-flex items-center gap-2 text-sm text-white/40 transition-colors hover:text-white/70"
        >
          <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
          Back to Home
        </Link>

        {/* Page header */}
        <div className="mb-10">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-purple-500/20 bg-purple-500/10 px-3 py-1 text-xs font-medium text-purple-300">
            <Sparkles className="h-3 w-3" />
            Canton Sandbox
          </div>
          <h1 className="text-3xl font-bold text-white sm:text-4xl">
            {status?.status === "complete"
              ? "Contract Deployed"
              : status?.status === "failed"
                ? "Deployment Failed"
                : "Deploying Contract"}
          </h1>
          <p className="mt-2 text-sm text-white/40">
            Job {jobId.substring(0, 8)}...
          </p>
        </div>

        {/* Pipeline Steps */}
        {status && (
          <div className="mb-8">
            <div className="flex items-center justify-between gap-1">
              {pipelineSteps.map((step, i) => {
                const active = (status.progress ?? 0) >= step.minProgress;
                const nextStep = pipelineSteps[i + 1];
                const current =
                  active &&
                  (i === pipelineSteps.length - 1 ||
                    (status.progress ?? 0) < (nextStep?.minProgress ?? 100));
                return (
                  <div key={step.label} className="flex flex-1 flex-col items-center gap-1.5">
                    <div
                      className={`flex h-8 w-8 items-center justify-center rounded-full border text-xs font-bold transition-all duration-500 ${
                        status.status === "complete"
                          ? "border-green-500/50 bg-green-500/20 text-green-400"
                          : status.status === "failed" && active && !current
                            ? "border-red-500/30 bg-red-500/10 text-red-400"
                            : current && isProcessing
                              ? "border-purple-400 bg-purple-500/20 text-purple-300 shadow-[0_0_12px_rgba(168,85,247,0.3)]"
                              : active
                                ? "border-purple-500/40 bg-purple-500/15 text-purple-400"
                                : "border-white/8 bg-white/3 text-white/20"
                      }`}
                    >
                      {status.status === "complete" ? (
                        <Check className="h-3.5 w-3.5" />
                      ) : current && isProcessing ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        i + 1
                      )}
                    </div>
                    <span
                      className={`text-[10px] font-medium transition-colors ${
                        current && isProcessing
                          ? "text-purple-300"
                          : active
                            ? "text-white/50"
                            : "text-white/15"
                      }`}
                    >
                      {step.label}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Progress bar */}
            <div className="mt-6">
              <div className="mb-2 flex justify-between text-xs">
                <span className="text-white/40">{status.current_step}</span>
                <span className="font-mono text-white/50">
                  {status.progress}%
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/5">
                <div
                  className={`h-full rounded-full transition-all duration-700 ease-out ${
                    status.status === "complete"
                      ? "bg-gradient-to-r from-green-500 to-emerald-400"
                      : status.status === "failed"
                        ? "bg-gradient-to-r from-red-600 to-red-400"
                        : "bg-gradient-to-r from-purple-600 via-fuchsia-500 to-purple-600 bg-[length:200%_100%] animate-[shimmer_2s_linear_infinite]"
                  }`}
                  style={{ width: `${status.progress}%` }}
                />
              </div>
            </div>

            {status.error_message && (
              <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/5 p-4">
                <p className="text-sm text-red-300">{status.error_message}</p>
              </div>
            )}
          </div>
        )}

        {/* Success Result */}
        {result && result.status === "complete" && (
          <div className="space-y-6">
            {/* Success banner */}
            <div className="overflow-hidden rounded-2xl border border-green-500/20 bg-green-500/5 p-6">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-green-500/20">
                  <CheckCircle2 className="h-5 w-5 text-green-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-green-100">
                    Successfully Deployed to Canton
                  </h3>
                  <p className="mt-1 text-sm text-green-300/60">
                    Your contract is live on the Canton ledger
                    {result.fallback_used && (
                      <span className="ml-2 rounded-full bg-yellow-500/10 px-2 py-0.5 text-xs text-yellow-300">
                        Fallback template used
                      </span>
                    )}
                  </p>
                </div>
              </div>
            </div>

            {/* IDs */}
            <div className="space-y-3">
              {result.contract_id && (
                <div className="rounded-xl border border-white/8 bg-white/3 p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <FileText className="h-3.5 w-3.5 text-purple-400" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-white/40">
                      Contract ID
                    </span>
                  </div>
                  <div className="flex items-start justify-between">
                    <p className="break-all font-mono text-xs leading-relaxed text-white/70">
                      {result.contract_id}
                    </p>
                    <CopyButton text={result.contract_id} />
                  </div>
                </div>
              )}
              {result.package_id && (
                <div className="rounded-xl border border-white/8 bg-white/3 p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <Package className="h-3.5 w-3.5 text-fuchsia-400" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-white/40">
                      Package ID
                    </span>
                  </div>
                  <div className="flex items-start justify-between">
                    <p className="break-all font-mono text-xs leading-relaxed text-white/70">
                      {result.package_id}
                    </p>
                    <CopyButton text={result.package_id} />
                  </div>
                </div>
              )}
            </div>

            {/* Generated Code */}
            {result.generated_code && (
              <div>
                <button
                  onClick={() => setShowCode(!showCode)}
                  className="mb-3 flex items-center gap-2 text-sm font-medium text-white/50 transition-colors hover:text-white/80"
                >
                  <Code2 className="h-4 w-4" />
                  {showCode ? "Hide" : "View"} Generated DAML Code
                </button>

                {showCode && (
                  <div className="relative">
                    <pre className="scrollbar-hide overflow-x-auto rounded-xl border border-white/8 bg-[#0a0b14] p-5 text-sm leading-relaxed text-purple-200/80">
                      <code>{result.generated_code}</code>
                    </pre>
                    <div className="absolute right-3 top-3">
                      <CopyButton text={result.generated_code} />
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-3 border-t border-white/8 pt-6">
              <Link
                href="/"
                className="group inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-fuchsia-600 px-6 py-3 text-sm font-semibold text-white transition-all hover:from-purple-500 hover:to-fuchsia-500 hover:shadow-[0_0_24px_rgba(168,85,247,0.3)]"
              >
                Generate Another
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
            </div>
          </div>
        )}

        {/* Failure Result */}
        {result && result.status === "failed" && (
          <div className="space-y-6">
            <div className="overflow-hidden rounded-2xl border border-red-500/20 bg-red-500/5 p-6">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-red-500/20">
                  <XCircle className="h-5 w-5 text-red-400" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-red-100">
                    Generation Failed
                  </h3>
                  {result.error_message && (
                    <p className="mt-2 text-sm text-red-300/70">
                      {result.error_message}
                    </p>
                  )}
                </div>
              </div>

              {result.compile_errors && result.compile_errors.length > 0 && (
                <div className="mt-4 rounded-xl border border-red-500/10 bg-[#0a0b14] p-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-red-400/60">
                    Compilation Errors
                  </p>
                  <div className="space-y-1">
                    {result.compile_errors.map((error, i) => (
                      <p
                        key={i}
                        className="font-mono text-xs text-red-300/60"
                      >
                        {typeof error === "string"
                          ? error
                          : JSON.stringify(error)}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </div>

            <Link
              href="/"
              className="group inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-fuchsia-600 px-6 py-3 text-sm font-semibold text-white transition-all hover:from-purple-500 hover:to-fuchsia-500 hover:shadow-[0_0_24px_rgba(168,85,247,0.3)]"
            >
              Try Again
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
          </div>
        )}

        {/* Loading state */}
        {!status && (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-white/8 bg-white/3 py-16">
            <Loader2 className="mb-4 h-10 w-10 animate-spin text-purple-400" />
            <p className="text-sm text-white/40">Loading job status...</p>
          </div>
        )}
      </div>
    </div>
  );
}
