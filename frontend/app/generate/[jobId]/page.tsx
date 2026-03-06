"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { pollUntilComplete, type JobStatus, type JobResult } from "@/lib/api";

const PIPELINE_STEPS = [
  { key: "intent",   label: "Understanding your requirements",  icon: "🧠", threshold: 20  },
  { key: "rag",      label: "Finding similar Daml patterns",    icon: "📚", threshold: 35  },
  { key: "generate", label: "Generating Daml code",             icon: "✍️", threshold: 50  },
  { key: "compile",  label: "Compiling contract",               icon: "⚙️", threshold: 70  },
  { key: "deploy",   label: "Deploying to Canton",              icon: "🚀", threshold: 95  },
  { key: "done",     label: "Deployed successfully",            icon: "✅", threshold: 100 },
];

function getActiveStep(progress: number): number {
  for (let i = PIPELINE_STEPS.length - 1; i >= 0; i--) {
    if (progress >= PIPELINE_STEPS[i].threshold) return i;
  }
  return 0;
}

export default function GeneratePage() {
  const router   = useRouter();
  const params   = useParams();
  const jobId    = params.jobId as string;

  const [status,      setStatus]      = useState<JobStatus | null>(null);
  const [codePreview, setCodePreview] = useState<string>("");
  const [elapsed,     setElapsed]     = useState(0);
  const startRef = useRef(Date.now());
  const codeRef  = useRef<HTMLPreElement>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!jobId) return;

    pollUntilComplete(
      jobId,
      (s: JobStatus) => {
        setStatus(s);
      },
      1500
    ).then((result: JobResult) => {
      if (result.generated_code) {
        setCodePreview(result.generated_code);
      }
      if (result.status === "complete") {
        router.push(`/result/${jobId}`);
      } else {
        router.push(`/result/${jobId}`);
      }
    }).catch(() => {
      router.push(`/result/${jobId}`);
    });
  }, [jobId, router]);

  const progress    = status?.progress ?? 5;
  const currentStep = status?.current_step ?? "Starting pipeline...";
  const activeIdx   = getActiveStep(progress);

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return m > 0 ? `${m}m ${sec}s` : `${sec}s`;
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-16">
      <div className="w-full max-w-2xl animate-fade-in">

        {/* Header */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium mb-4" style={{ background: "rgba(90, 107, 255, 0.12)", color: "#818cf8", border: "1px solid rgba(90, 107, 255, 0.25)" }}>
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
            Pipeline running · {formatTime(elapsed)} elapsed
          </div>
          <h2 className="text-2xl font-bold mb-2" style={{ color: "#e8eaf6" }}>Generating your contract</h2>
          <p className="text-sm" style={{ color: "#9ca3af" }}>Job ID: <span className="font-mono" style={{ color: "#818cf8" }}>{jobId}</span></p>
        </div>

        {/* Progress bar */}
        <div className="glass-card p-6 mb-6">
          <div className="flex justify-between items-center mb-3">
            <span className="text-sm font-medium" style={{ color: "#e8eaf6" }}>{currentStep}</span>
            <span className="text-sm font-mono" style={{ color: "#818cf8" }}>{progress}%</span>
          </div>
          <div className="w-full h-2 rounded-full mb-6" style={{ background: "rgba(30, 42, 74, 0.8)" }}>
            <div
              className="h-2 rounded-full progress-bar-fill"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Steps */}
          <div className="space-y-3">
            {PIPELINE_STEPS.map((step, i) => {
              const isDone    = progress >= step.threshold;
              const isActive  = i === activeIdx && progress < 100;
              const isPending = !isDone && !isActive;

              return (
                <div key={step.key} className="flex items-center gap-4">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-300"
                    style={{
                      background: isDone
                        ? "rgba(16, 185, 129, 0.15)"
                        : isActive
                        ? "rgba(90, 107, 255, 0.2)"
                        : "rgba(30, 42, 74, 0.5)",
                      border: isDone
                        ? "1px solid rgba(16, 185, 129, 0.4)"
                        : isActive
                        ? "1px solid rgba(90, 107, 255, 0.5)"
                        : "1px solid rgba(30, 42, 74, 0.6)",
                    }}
                  >
                    {isDone ? (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    ) : isActive ? (
                      <svg className="animate-spin w-3.5 h-3.5" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="#818cf8" strokeWidth="4" />
                        <path className="opacity-75" fill="#818cf8" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                    ) : (
                      <span style={{ color: "#374151", fontSize: "10px" }}>○</span>
                    )}
                  </div>
                  <div className="flex-1">
                    <span className="text-sm font-medium transition-colors duration-300"
                      style={{
                        color: isDone ? "#10b981" : isActive ? "#e8eaf6" : "#4b5563",
                      }}
                    >
                      {step.icon} {step.label}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Live code preview */}
        {codePreview && (
          <div className="glass-card p-5 animate-slide-up">
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold" style={{ color: "#6b7280" }}>GENERATED DAML CODE PREVIEW</span>
              <span className="text-xs font-mono px-2 py-0.5 rounded" style={{ background: "rgba(90, 107, 255, 0.1)", color: "#818cf8" }}>Main.daml</span>
            </div>
            <pre
              ref={codeRef}
              className="text-xs overflow-auto max-h-64 font-mono leading-relaxed"
              style={{ color: "#a5b4fc" }}
            >
              {codePreview.slice(0, 1200)}{codePreview.length > 1200 ? "\n..." : ""}
            </pre>
          </div>
        )}

        {/* Tip */}
        <p className="text-center text-xs mt-6" style={{ color: "#4b5563" }}>
          This takes 30–90 seconds · The page will redirect automatically when complete
        </p>
      </div>
    </div>
  );
}
