"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { useJobStatus } from "@/lib/use-job-status";
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
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Workflow,
  FolderTree,
  ExternalLink,
  Database,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";
import { MermaidDiagram } from "@/components/mermaid-diagram";

interface AuditFinding {
  id?: string;
  severity: string;
  category?: string;
  title: string;
  description?: string;
  recommendation?: string;
  references?: string[];
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
  security_score?: number | null;
  compliance_score?: number | null;
  enterprise_score?: number | null;
  deploy_gate?: boolean | null;
  deployment_note?: string;
  diagram_mermaid?: string;
  project_files?: Record<string, string>;
  audit_reports?: {
    json?: string;
    markdown?: string;
    html?: string;
  };
}

function CopyButton({ text }: { text: string }): ReactNode {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="ml-2 shrink-0 rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      title="Copy"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-green-500" />
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
  { label: "Auditing", minProgress: 75 },
  { label: "Deploying", minProgress: 85 },
];

function ScoreRing({ score, label, size = 80 }: { score: number; label: string; size?: number }): ReactNode {
  const radius = (size - 8) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 85 ? "#22c55e" : score >= 70 ? "#eab308" : score >= 50 ? "#f97316" : "#ef4444";

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative">
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="currentColor" className="text-border" strokeWidth={4} />
          <circle
            cx={size / 2} cy={size / 2} r={radius} fill="none"
            stroke={color} strokeWidth={4} strokeLinecap="round"
            strokeDasharray={circumference} strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-lg font-bold text-foreground">{score}</span>
        </div>
      </div>
      <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">{label}</span>
    </div>
  );
}

function SeverityBadge({ severity }: { severity: string }): ReactNode {
  const colors: Record<string, string> = {
    CRITICAL: "bg-red-500/15 text-red-600 dark:text-red-400 border-red-500/30",
    HIGH: "bg-orange-500/15 text-orange-600 dark:text-orange-400 border-orange-500/30",
    MEDIUM: "bg-yellow-500/15 text-yellow-600 dark:text-yellow-400 border-yellow-500/30",
    LOW: "bg-blue-500/15 text-blue-600 dark:text-blue-400 border-blue-500/30",
    INFO: "bg-gray-500/15 text-gray-600 dark:text-gray-400 border-gray-500/30",
    OPT: "bg-purple-500/15 text-purple-600 dark:text-purple-400 border-purple-500/30",
  };
  return (
    <span className={`inline-flex rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase ${colors[severity] || colors.INFO}`}>
      {severity}
    </span>
  );
}

export default function SandboxPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.jobId as string;

  const { status, transport } = useJobStatus(jobId);
  const [result, setResult] = useState<JobResult | null>(null);
  const [activeTab, setActiveTab] = useState<"code" | "diagram" | "files">("code");
  const [showFindings, setShowFindings] = useState(false);
  const [auditFindings, setAuditFindings] = useState<AuditFinding[]>([]);
  const [resultLoading, setResultLoading] = useState(false);
  const [resultError, setResultError] = useState<string | null>(null);

  const API_URL =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  const fetchResult = useCallback(async () => {
    if (!jobId) return;
    setResultLoading(true);
    setResultError(null);
    // Retry with backoff: the /result endpoint may not be populated the
    // instant the status flips to "complete" (the indexer / DB write can
    // lag the WS broadcast by a few hundred ms). Without retrying the user
    // sees a green "Contract Deployed" bar but no code / IDs / audit panel.
    const delays = [0, 500, 1000, 2000, 3000, 5000, 8000];
    let lastErr = "";
    for (const delay of delays) {
      if (delay > 0) await new Promise((r) => setTimeout(r, delay));
      try {
        const response = await fetch(`${API_URL}/result/${jobId}`);
        if (!response.ok) {
          lastErr = `HTTP ${response.status}`;
          continue;
        }
        const resultData: JobResult = await response.json();
        // Treat anything other than a populated terminal record as not ready.
        if (resultData.status !== "complete" && resultData.status !== "failed") {
          lastErr = `status=${resultData.status ?? "unknown"}`;
          continue;
        }
        setResult(resultData);
        if (resultData.audit_reports?.json) {
          try {
            const parsed = JSON.parse(resultData.audit_reports.json);
            const findings = parsed?.securityAudit?.report?.findings || [];
            setAuditFindings(findings);
          } catch { /* ignore parse errors */ }
        }
        setResultLoading(false);
        return;
      } catch (error) {
        lastErr = String(error);
        console.error("Error fetching result (will retry):", error);
      }
    }
    setResultError(lastErr || "Result not available");
    setResultLoading(false);
  }, [jobId, API_URL]);

  useEffect(() => {
    if (
      status &&
      (status.status === "complete" || status.status === "failed") &&
      !result &&
      !resultLoading
    ) {
      fetchResult();
    }
  }, [status, result, resultLoading, fetchResult]);

  useEffect(() => {
    if (status?.status === "unknown") {
      const timer = setTimeout(() => router.push("/"), 3000);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [status, router]);

  const isProcessing =
    status?.status === "queued" || status?.status === "running";

  return (
    <main className="min-h-screen bg-background">
      <div className="relative mx-auto max-w-3xl px-6 pt-32 pb-20">
        {/* Back nav */}
        <Link
          href="/"
          className="group mb-8 inline-flex items-center gap-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-0.5" />
          Back to Home
        </Link>

        {/* Page header */}
        <div className="mb-10">
          <div className="mb-3 inline-flex items-center gap-1.5 rounded-xl border border-border bg-muted px-3 py-1 text-xs font-medium text-foreground">
            <Sparkles className="h-3 w-3 text-accent" />
            Canton Sandbox
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            {status?.status === "complete"
              ? "Contract Deployed"
              : status?.status === "failed"
                ? "Deployment Failed"
                : "Deploying Contract"}
          </h1>
          <p className="mt-2 flex items-center gap-2 text-sm text-muted-foreground font-mono">
            Job {jobId.substring(0, 8)}...
            {isProcessing && (
              <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                transport === "websocket"
                  ? "bg-green-500/10 text-green-600 dark:text-green-400"
                  : transport === "polling"
                    ? "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400"
                    : "bg-muted text-muted-foreground"
              }`}>
                <span className={`h-1.5 w-1.5 rounded-full ${
                  transport === "websocket" ? "bg-green-500" : transport === "polling" ? "bg-yellow-500" : "bg-muted-foreground"
                }`} />
                {transport === "websocket" ? "Live" : transport === "polling" ? "Polling" : "Connecting"}
              </span>
            )}
          </p>
        </div>

        {/* Pipeline Steps */}
        {status && (
          <div className="mb-10">
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
                      className={`flex h-9 w-9 items-center justify-center rounded-full border text-xs font-bold transition-all duration-500 ${
                        status.status === "complete"
                          ? "border-green-500/50 bg-green-500/15 text-green-600 dark:text-green-400"
                          : status.status === "failed" && active && !current
                            ? "border-red-500/30 bg-red-500/10 text-red-500"
                            : current && isProcessing
                              ? "border-accent bg-accent/20 text-foreground shadow-[0_0_12px_rgba(168,217,70,0.2)]"
                              : active
                                ? "border-accent/40 bg-accent/10 text-foreground/70"
                                : "border-border bg-muted text-muted-foreground"
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
                          ? "text-foreground"
                          : active
                            ? "text-foreground/60"
                            : "text-muted-foreground/50"
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
                <span className="text-muted-foreground">{status.current_step}</span>
                <span className="font-mono text-foreground/60">
                  {status.progress}%
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-border">
                <div
                  className={`h-full rounded-full transition-all duration-700 ease-out ${
                    status.status === "complete"
                      ? "bg-green-500"
                      : status.status === "failed"
                        ? "bg-red-500"
                        : "bg-accent"
                  }`}
                  style={{ width: `${status.progress}%` }}
                />
              </div>
            </div>

            {status.error_message && (
              <div className="mt-4 rounded-2xl border border-red-500/20 bg-red-500/5 p-4">
                <p className="text-sm text-red-600 dark:text-red-400">{status.error_message}</p>
              </div>
            )}
          </div>
        )}

        {/* Result loading / error fallback (between progress and result panel) */}
        {status?.status === "complete" && !result && (
          <div className="mb-8 rounded-2xl border border-border bg-muted p-5">
            {resultLoading && !resultError && (
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin text-accent" />
                Loading deployment artifacts (code, IDs, audit report)...
              </div>
            )}
            {resultError && (
              <div className="space-y-3">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-yellow-500" />
                  <div className="text-sm">
                    <p className="font-medium text-foreground">
                      Deployment succeeded, but the result payload is not available yet.
                    </p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      The contract is on the ledger (you can verify it via the Ledger Explorer).
                      The backend may still be persisting the result. Try again in a moment.
                    </p>
                    <p className="mt-1 font-mono text-[10px] text-muted-foreground/70">
                      last error: {resultError}
                    </p>
                  </div>
                </div>
                <button
                  onClick={fetchResult}
                  className="inline-flex items-center gap-2 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
                >
                  <Loader2 className={`h-3.5 w-3.5 ${resultLoading ? "animate-spin" : ""}`} />
                  Retry
                </button>
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
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-foreground">
                    Successfully Deployed to Canton
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Your contract is live on the Canton ledger
                    {result.fallback_used && (
                      <span className="ml-2 rounded-full bg-yellow-500/10 px-2 py-0.5 text-xs text-yellow-600 dark:text-yellow-400">
                        Fallback template used
                      </span>
                    )}
                  </p>
                </div>
              </div>
            </div>

            {/* Security & Compliance Dashboard */}
            {(result.security_score != null || result.compliance_score != null) && (
              <div className="rounded-2xl border border-border bg-muted p-6">
                <div className="mb-4 flex items-center gap-2">
                  {result.deploy_gate !== false ? (
                    <ShieldCheck className="h-5 w-5 text-green-500" />
                  ) : (
                    <ShieldAlert className="h-5 w-5 text-yellow-500" />
                  )}
                  <h3 className="text-sm font-semibold text-foreground">
                    Enterprise Security &amp; Compliance
                  </h3>
                  {result.deploy_gate !== false ? (
                    <span className="ml-auto rounded-full bg-green-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-green-600 dark:text-green-400 border border-green-500/20">
                      DEPLOY READY
                    </span>
                  ) : (
                    <span className="ml-auto rounded-full bg-yellow-500/10 px-2.5 py-0.5 text-[10px] font-semibold text-yellow-600 dark:text-yellow-400 border border-yellow-500/20">
                      REVIEW RECOMMENDED
                    </span>
                  )}
                </div>

                {/* Score cards */}
                <div className="grid grid-cols-3 gap-4">
                  {result.security_score != null && (
                    <div className="relative flex flex-col items-center rounded-xl border border-border bg-background p-4">
                      <ScoreRing score={result.security_score} label="Security" />
                    </div>
                  )}
                  {result.compliance_score != null && (
                    <div className="relative flex flex-col items-center rounded-xl border border-border bg-background p-4">
                      <ScoreRing score={result.compliance_score} label="Compliance" />
                    </div>
                  )}
                  {result.enterprise_score != null && (
                    <div className="relative flex flex-col items-center rounded-xl border border-border bg-background p-4">
                      <ScoreRing score={Math.round(result.enterprise_score)} label="Enterprise" />
                    </div>
                  )}
                </div>

                {/* Findings toggle */}
                {auditFindings.length > 0 && (
                  <div className="mt-4">
                    <button
                      onClick={() => setShowFindings(!showFindings)}
                      className="flex w-full items-center justify-between rounded-xl border border-border bg-background px-4 py-2.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                    >
                      <span className="flex items-center gap-2">
                        <AlertTriangle className="h-3.5 w-3.5" />
                        {auditFindings.length} Security Finding{auditFindings.length !== 1 ? "s" : ""}
                        <span className="flex gap-1 ml-1">
                          {auditFindings.filter(f => f.severity === "CRITICAL").length > 0 && (
                            <span className="rounded bg-red-500/15 px-1.5 py-0.5 text-[9px] font-bold text-red-600 dark:text-red-400">
                              {auditFindings.filter(f => f.severity === "CRITICAL").length} CRIT
                            </span>
                          )}
                          {auditFindings.filter(f => f.severity === "HIGH").length > 0 && (
                            <span className="rounded bg-orange-500/15 px-1.5 py-0.5 text-[9px] font-bold text-orange-600 dark:text-orange-400">
                              {auditFindings.filter(f => f.severity === "HIGH").length} HIGH
                            </span>
                          )}
                          {auditFindings.filter(f => f.severity === "MEDIUM").length > 0 && (
                            <span className="rounded bg-yellow-500/15 px-1.5 py-0.5 text-[9px] font-bold text-yellow-600 dark:text-yellow-400">
                              {auditFindings.filter(f => f.severity === "MEDIUM").length} MED
                            </span>
                          )}
                        </span>
                      </span>
                      {showFindings ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                    </button>

                    {showFindings && (
                      <div className="mt-2 max-h-80 space-y-2 overflow-y-auto pr-1">
                        {auditFindings.map((finding, i) => (
                          <div
                            key={finding.id || i}
                            className="rounded-xl border border-border bg-background p-3"
                          >
                            <div className="mb-1 flex items-center gap-2">
                              <SeverityBadge severity={finding.severity} />
                              <span className="text-xs font-medium text-foreground/80">{finding.title}</span>
                            </div>
                            {finding.description && (
                              <p className="mb-1 text-[11px] leading-relaxed text-muted-foreground">
                                {finding.description}
                              </p>
                            )}
                            {finding.recommendation && (
                              <p className="text-[11px] text-accent/80">
                                <span className="font-semibold text-accent">Fix: </span>
                                {finding.recommendation}
                              </p>
                            )}
                            {finding.references && finding.references.length > 0 && (
                              <div className="mt-1 flex flex-wrap gap-1">
                                {finding.references.map((ref, j) => (
                                  <span key={j} className="rounded bg-muted px-1.5 py-0.5 text-[9px] font-mono text-muted-foreground">
                                    {ref}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* IDs */}
            <div className="space-y-3">
              {result.contract_id && (
                <div className="rounded-2xl border border-border bg-muted p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <FileText className="h-3.5 w-3.5 text-accent" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Contract ID
                    </span>
                  </div>
                  <div className="flex items-start justify-between">
                    <p className="break-all font-mono text-xs leading-relaxed text-foreground/70">
                      {result.contract_id}
                    </p>
                    <CopyButton text={result.contract_id} />
                  </div>
                </div>
              )}
              {result.package_id && (
                <div className="rounded-2xl border border-border bg-muted p-4">
                  <div className="mb-2 flex items-center gap-2">
                    <Package className="h-3.5 w-3.5 text-accent" />
                    <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Package ID
                    </span>
                  </div>
                  <div className="flex items-start justify-between">
                    <p className="break-all font-mono text-xs leading-relaxed text-foreground/70">
                      {result.package_id}
                    </p>
                    <CopyButton text={result.package_id} />
                  </div>
                </div>
              )}
            </div>

            {/* Deployment Note */}
            {result.deployment_note && (
              <div className="rounded-2xl border border-accent/20 bg-accent/5 p-4">
                <p className="text-sm text-foreground/80">{result.deployment_note}</p>
              </div>
            )}

            {/* Tabbed Code / Diagram / Project Files */}
            {(result.generated_code || result.diagram_mermaid || result.project_files) && (
              <div>
                {/* Tab bar */}
                <div className="mb-3 flex items-center gap-1 rounded-xl border border-border bg-muted p-1">
                  <button
                    onClick={() => setActiveTab("code")}
                    className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                      activeTab === "code"
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    <Code2 className="h-3.5 w-3.5" />
                    Code
                  </button>
                  {result.diagram_mermaid && (
                    <button
                      onClick={() => setActiveTab("diagram")}
                      className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                        activeTab === "diagram"
                          ? "bg-background text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      <Workflow className="h-3.5 w-3.5" />
                      Contract Flow
                    </button>
                  )}
                  {result.project_files && Object.keys(result.project_files).length > 1 && (
                    <button
                      onClick={() => setActiveTab("files")}
                      className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                        activeTab === "files"
                          ? "bg-background text-foreground shadow-sm"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      <FolderTree className="h-3.5 w-3.5" />
                      Files ({Object.keys(result.project_files).length})
                    </button>
                  )}
                </div>

                {/* Tab content */}
                {activeTab === "code" && result.generated_code && (
                  <div className="relative">
                    <pre className="max-h-[500px] overflow-auto rounded-2xl border border-border bg-muted p-5 text-sm leading-relaxed text-foreground/80 font-mono">
                      <code>{result.generated_code}</code>
                    </pre>
                    <div className="absolute right-3 top-3">
                      <CopyButton text={result.generated_code} />
                    </div>
                  </div>
                )}

                {activeTab === "diagram" && result.diagram_mermaid && (
                  <MermaidDiagram chart={result.diagram_mermaid} />
                )}

                {activeTab === "files" && result.project_files && (
                  <div className="space-y-3">
                    {Object.entries(result.project_files).map(([filename, code]) => (
                      <div key={filename} className="rounded-2xl border border-border bg-muted">
                        <div className="flex items-center justify-between border-b border-border px-4 py-2">
                          <span className="font-mono text-xs text-foreground/70">{filename}</span>
                          <CopyButton text={code} />
                        </div>
                        <pre className="max-h-64 overflow-auto p-4 text-xs leading-relaxed text-foreground/80 font-mono">
                          <code>{code}</code>
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-3 border-t border-border pt-6">
              <Link
                href="/"
                className="group inline-flex items-center gap-2 rounded-xl bg-foreground px-6 py-3 text-sm font-semibold text-background transition-colors hover:bg-foreground/90"
              >
                Generate Another
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link
                href="/explorer"
                className="group inline-flex items-center gap-2 rounded-xl border border-accent/30 bg-accent/10 px-6 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-accent/20"
              >
                <Database className="h-4 w-4 text-accent" />
                Canton Ledger Explorer
                <ExternalLink className="h-3.5 w-3.5 text-accent transition-transform group-hover:translate-x-0.5" />
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
                  <XCircle className="h-5 w-5 text-red-500" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-foreground">
                    Generation Failed
                  </h3>
                  {result.error_message && (
                    <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                      {result.error_message}
                    </p>
                  )}
                </div>
              </div>

              {result.compile_errors && result.compile_errors.length > 0 && (
                <div className="mt-4 rounded-xl border border-border bg-muted p-4">
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-red-500/60">
                    Compilation Errors
                  </p>
                  <div className="space-y-1">
                    {result.compile_errors.map((error, i) => (
                      <p
                        key={i}
                        className="font-mono text-xs text-red-600/70 dark:text-red-400/70"
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

            <div className="flex items-center gap-3">
              <Link
                href="/"
                className="group inline-flex items-center gap-2 rounded-xl bg-foreground px-6 py-3 text-sm font-semibold text-background transition-colors hover:bg-foreground/90"
              >
                Try Again
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </Link>
              <Link
                href="/explorer"
                className="group inline-flex items-center gap-2 rounded-xl border border-accent/30 bg-accent/10 px-6 py-3 text-sm font-semibold text-foreground transition-colors hover:bg-accent/20"
              >
                <Database className="h-4 w-4 text-accent" />
                Ledger Explorer
                <ExternalLink className="h-3.5 w-3.5 text-accent transition-transform group-hover:translate-x-0.5" />
              </Link>
            </div>
          </div>
        )}

        {/* Loading state */}
        {!status && (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-border bg-muted py-16">
            <Loader2 className="mb-4 h-10 w-10 animate-spin text-accent" />
            <p className="text-sm text-muted-foreground">Loading job status...</p>
          </div>
        )}
      </div>
    </main>
  );
}
