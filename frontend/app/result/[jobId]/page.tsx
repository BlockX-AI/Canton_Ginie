"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getJobResult, iterateContract, type JobResult, type CompileError } from "@/lib/api";
import toast from "react-hot-toast";

export default function ResultPage() {
  const params = useParams();
  const router = useRouter();
  const jobId  = params.jobId as string;

  const [result,        setResult]        = useState<JobResult | null>(null);
  const [loading,       setLoading]       = useState(true);
  const [feedback,      setFeedback]      = useState("");
  const [isIterating,   setIsIterating]   = useState(false);
  const [codeCopied,    setCodeCopied]    = useState(false);
  const [contractCopied,setContractCopied]= useState(false);
  const [activeTab,     setActiveTab]     = useState<"code"|"intent"|"errors">("code");

  useEffect(() => {
    if (!jobId) return;
    getJobResult(jobId)
      .then(setResult)
      .catch(() => toast.error("Failed to load result."))
      .finally(() => setLoading(false));
  }, [jobId]);

  const handleCopyCode = async () => {
    if (!result?.generated_code) return;
    await navigator.clipboard.writeText(result.generated_code);
    setCodeCopied(true);
    setTimeout(() => setCodeCopied(false), 2000);
  };

  const handleCopyContractId = async () => {
    if (!result?.contract_id) return;
    await navigator.clipboard.writeText(result.contract_id);
    setContractCopied(true);
    setTimeout(() => setContractCopied(false), 2000);
  };

  const handleIterate = async () => {
    if (!feedback.trim()) {
      toast.error("Please describe what you want to change.");
      return;
    }
    setIsIterating(true);
    try {
      const response = await iterateContract(jobId, feedback, result?.generated_code);
      toast.success("Iteration started!");
      router.push(`/generate/${response.job_id}`);
    } catch {
      toast.error("Failed to start iteration.");
      setIsIterating(false);
    }
  };

  const handleDownloadDAR = () => {
    toast("DAR download requires the contract to be compiled locally. Check your /tmp/ginie_jobs directory.", { icon: "ℹ️" });
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center animate-fade-in">
          <svg className="animate-spin w-8 h-8 mx-auto mb-4" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="#818cf8" strokeWidth="4" />
            <path className="opacity-75" fill="#818cf8" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <p style={{ color: "#9ca3af" }}>Loading result...</p>
        </div>
      </div>
    );
  }

  if (!result) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p style={{ color: "#ef4444" }}>Result not found.</p>
          <button onClick={() => router.push("/")} className="mt-4 text-sm" style={{ color: "#818cf8" }}>← Back to home</button>
        </div>
      </div>
    );
  }

  const isSuccess = result.status === "complete" && !!result.contract_id;
  const intent    = result.structured_intent as Record<string, unknown> | undefined;

  return (
    <div className="min-h-screen px-4 py-16">
      <div className="max-w-4xl mx-auto animate-fade-in">

        {/* Status banner */}
        <div className="glass-card p-6 mb-6" style={{ border: isSuccess ? "1px solid rgba(16, 185, 129, 0.3)" : "1px solid rgba(239, 68, 68, 0.3)" }}>
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
                style={{ background: isSuccess ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.1)" }}>
                {isSuccess ? (
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12" />
                  </svg>
                ) : (
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                  </svg>
                )}
              </div>
              <div>
                <h1 className="text-xl font-bold mb-1" style={{ color: "#e8eaf6" }}>
                  {isSuccess ? "Contract Deployed Successfully" : "Contract Generation Failed"}
                </h1>
                <p className="text-sm" style={{ color: "#6b7280" }}>
                  Job ID: <span className="font-mono" style={{ color: "#818cf8" }}>{jobId}</span>
                  {result.attempt_number !== undefined && (
                    <span className="ml-3">· {result.attempt_number} compile attempt{result.attempt_number !== 1 ? "s" : ""}</span>
                  )}
                </p>
              </div>
            </div>
            <button onClick={() => router.push("/")} className="text-xs px-3 py-2 rounded-lg flex-shrink-0 transition-all"
              style={{ background: "rgba(30, 42, 74, 0.6)", color: "#9ca3af", border: "1px solid rgba(30, 42, 74, 0.8)" }}>
              ← New Contract
            </button>
          </div>

          {isSuccess && (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
              {[
                { label: "Contract ID",  value: result.contract_id,  mono: true  },
                { label: "Package ID",   value: result.package_id,   mono: true  },
                { label: "Network",      value: result.status === "complete" ? "Canton Sandbox" : "—", mono: false },
              ].map(field => (
                <div key={field.label} className="rounded-xl p-4" style={{ background: "rgba(10, 13, 26, 0.6)", border: "1px solid rgba(30, 42, 74, 0.6)" }}>
                  <p className="text-xs mb-1" style={{ color: "#6b7280" }}>{field.label}</p>
                  <p className={`text-sm break-all ${field.mono ? "font-mono" : "font-medium"}`} style={{ color: "#e8eaf6" }}>
                    {field.value || "—"}
                  </p>
                </div>
              ))}
            </div>
          )}

          {result.error_message && (
            <div className="mt-4 p-4 rounded-xl" style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.2)" }}>
              <p className="text-xs font-semibold mb-1" style={{ color: "#ef4444" }}>ERROR</p>
              <p className="text-sm font-mono" style={{ color: "#fca5a5" }}>{result.error_message}</p>
            </div>
          )}
        </div>

        {/* Action buttons */}
        {isSuccess && (
          <div className="flex flex-wrap gap-3 mb-6">
            {result.explorer_link && (
              <a href={result.explorer_link} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all"
                style={{ background: "rgba(90, 107, 255, 0.15)", color: "#818cf8", border: "1px solid rgba(90, 107, 255, 0.3)" }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>
                </svg>
                View on Explorer
              </a>
            )}
            <button onClick={handleCopyContractId}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all"
              style={{ background: "rgba(30, 42, 74, 0.6)", color: "#9ca3af", border: "1px solid rgba(30, 42, 74, 0.8)" }}>
              {contractCopied ? "✓ Copied!" : "Copy Contract ID"}
            </button>
            <button onClick={handleDownloadDAR}
              className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all"
              style={{ background: "rgba(30, 42, 74, 0.6)", color: "#9ca3af", border: "1px solid rgba(30, 42, 74, 0.8)" }}>
              Download DAR
            </button>
          </div>
        )}

        {/* Tabs */}
        {result.generated_code && (
          <div className="glass-card overflow-hidden mb-6">
            <div className="flex border-b" style={{ borderColor: "rgba(30, 42, 74, 0.8)" }}>
              {([
                { id: "code",   label: "Daml Code"       },
                { id: "intent", label: "Parsed Intent"   },
                ...(result.compile_errors?.length ? [{ id: "errors", label: `Errors (${result.compile_errors.length})` }] : []),
              ] as { id: string; label: string }[]).map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as "code"|"intent"|"errors")}
                  className="px-5 py-3 text-sm font-medium transition-colors"
                  style={{
                    color:       activeTab === tab.id ? "#e8eaf6" : "#6b7280",
                    borderBottom: activeTab === tab.id ? "2px solid #5a6bff" : "2px solid transparent",
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="p-5">
              {activeTab === "code" && (
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-xs font-semibold" style={{ color: "#6b7280" }}>Main.daml</span>
                    <button onClick={handleCopyCode} className="text-xs px-3 py-1 rounded-lg transition-all"
                      style={{ background: "rgba(90, 107, 255, 0.1)", color: "#818cf8", border: "1px solid rgba(90, 107, 255, 0.2)" }}>
                      {codeCopied ? "✓ Copied!" : "Copy code"}
                    </button>
                  </div>
                  <pre className="text-xs overflow-auto max-h-96 font-mono leading-relaxed p-4 rounded-xl"
                    style={{ background: "rgba(10, 13, 26, 0.8)", color: "#a5b4fc", border: "1px solid rgba(30, 42, 74, 0.4)" }}>
                    {result.generated_code}
                  </pre>
                </div>
              )}

              {activeTab === "intent" && intent && (
                <div className="space-y-4">
                  {Object.entries(intent).map(([key, val]) => (
                    <div key={key} className="flex gap-4">
                      <span className="text-xs font-mono w-40 flex-shrink-0 pt-0.5" style={{ color: "#6b7280" }}>
                        {key.replace(/_/g, " ")}
                      </span>
                      <span className="text-sm" style={{ color: "#e8eaf6" }}>
                        {Array.isArray(val) ? (val as string[]).join(", ") : String(val)}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {activeTab === "errors" && result.compile_errors && (
                <div className="space-y-3">
                  {result.compile_errors.map((err: CompileError, i: number) => (
                    <div key={i} className="p-4 rounded-xl" style={{ background: "rgba(239, 68, 68, 0.07)", border: "1px solid rgba(239, 68, 68, 0.15)" }}>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-mono" style={{ color: "#f87171" }}>{err.file}:{err.line}</span>
                        <span className="text-xs px-2 py-0.5 rounded" style={{ background: "rgba(239, 68, 68, 0.1)", color: "#fca5a5" }}>{err.error_type}</span>
                        <span className="text-xs" style={{ color: err.fixable ? "#10b981" : "#f59e0b" }}>{err.fixable ? "fixable" : "architectural"}</span>
                      </div>
                      <p className="text-xs font-mono" style={{ color: "#fca5a5" }}>{err.message}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Iterate */}
        <div className="glass-card p-6">
          <h3 className="text-sm font-semibold mb-3" style={{ color: "#e8eaf6" }}>Iterate on this contract</h3>
          <p className="text-xs mb-4" style={{ color: "#6b7280" }}>
            Describe changes, new features, or fixes — Ginie will regenerate and redeploy.
          </p>
          <textarea
            value={feedback}
            onChange={e => setFeedback(e.target.value)}
            rows={3}
            placeholder="e.g. Add a transfer choice so investors can transfer the bond to other parties..."
            className="w-full resize-none rounded-xl px-4 py-3 text-sm mb-4 transition-all"
            style={{ background: "rgba(10, 13, 26, 0.6)", border: "1px solid rgba(30, 42, 74, 0.8)", color: "#e8eaf6" }}
            onFocus={e  => (e.currentTarget.style.borderColor = "rgba(90, 107, 255, 0.5)")}
            onBlur={e   => (e.currentTarget.style.borderColor = "rgba(30, 42, 74, 0.8)")}
          />
          <button onClick={handleIterate} disabled={isIterating || !feedback.trim()}
            className="btn-primary px-6 py-3 rounded-xl text-sm font-semibold flex items-center gap-2 transition-all">
            {isIterating ? (
              <>
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Starting iteration...
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>
                </svg>
                Iterate &amp; Redeploy
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  );
}
