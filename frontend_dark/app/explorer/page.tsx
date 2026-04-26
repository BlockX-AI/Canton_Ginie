"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Loader2,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
  Search,
  Users,
  Package,
  FileText,
  Eye,
  Shield,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Database,
  Activity,
} from "lucide-react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Party {
  identifier: string;
  displayName: string;
  isLocal: boolean;
}

interface Contract {
  contractId: string;
  templateId: string;
  payload: Record<string, unknown>;
  signatories: string[];
  observers: string[];
  agreementText: string;
}

interface LedgerStatus {
  status: string;
  canton_url: string;
  environment: string;
  parties: number;
  packages: number;
  error?: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="ml-1 shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
      title="Copy"
    >
      {copied ? <Check className="h-3 w-3 text-accent" /> : <Copy className="h-3 w-3" />}
    </button>
  );
}

function truncate(s: string, n = 24): string {
  return s.length > n ? s.slice(0, n) + "..." : s;
}

function StatusDot({ online }: { online: boolean }) {
  return (
    <span className={`inline-block h-2.5 w-2.5 rounded-full ${online ? "bg-accent shadow-[0_0_6px_rgba(34,197,94,0.5)]" : "bg-red-400 shadow-[0_0_6px_rgba(239,68,68,0.5)]"}`} />
  );
}

// ---------------------------------------------------------------------------
// Tab Components
// ---------------------------------------------------------------------------

function ContractsTab() {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Contract | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  const fetchContracts = async () => {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch(`${API_URL}/ledger/contracts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data: unknown = await resp.json();
      const parsed = data as { contracts?: Contract[] };
      setContracts(parsed.contracts ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch contracts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void fetchContracts(); }, []);

  const filtered = contracts.filter(
    (c) =>
      c.contractId.toLowerCase().includes(searchTerm.toLowerCase()) ||
      c.templateId.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-accent" />
        <span className="ml-3 text-muted-foreground">Querying ledger...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center">
        <XCircle className="mx-auto h-8 w-8 text-red-400" />
        <p className="mt-2 text-sm text-red-300">{error}</p>
        <button onClick={() => void fetchContracts()} className="mt-3 rounded-lg bg-muted px-4 py-2 text-xs text-foreground/60 hover:bg-muted">
          Retry
        </button>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/70" />
          <input
            type="text"
            placeholder="Search by contract ID or template..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-lg border border-border bg-muted py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground/70 focus:border-accent/50 focus:outline-none"
          />
        </div>
        <button onClick={() => void fetchContracts()} className="rounded-lg border border-border bg-muted p-2.5 text-muted-foreground hover:bg-muted hover:text-foreground">
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {filtered.length === 0 ? (
        <div className="py-16 text-center text-muted-foreground">
          <FileText className="mx-auto h-10 w-10 text-muted-foreground/50" />
          <p className="mt-3">No contracts found on ledger</p>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="grid grid-cols-12 gap-4 px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
            <div className="col-span-3">Contract ID</div>
            <div className="col-span-5">Template ID</div>
            <div className="col-span-2">Signatories</div>
            <div className="col-span-2 text-right">Actions</div>
          </div>

          {filtered.map((c) => (
            <div key={c.contractId}>
              <div
                className={`grid cursor-pointer grid-cols-12 gap-4 rounded-lg border px-4 py-3 transition-all ${
                  selected?.contractId === c.contractId
                    ? "border-accent/40 bg-accent/10"
                    : "border-border bg-muted hover:border-border hover:bg-muted/80"
                }`}
                onClick={() => setSelected(selected?.contractId === c.contractId ? null : c)}
              >
                <div className="col-span-3 flex items-center gap-2">
                  <span className="font-mono text-xs text-foreground/80">{truncate(c.contractId, 16)}</span>
                  <CopyButton text={c.contractId} />
                </div>
                <div className="col-span-5">
                  <span className="font-mono text-xs text-accent">{truncate(c.templateId, 50)}</span>
                </div>
                <div className="col-span-2 flex items-center gap-1">
                  <Users className="h-3 w-3 text-muted-foreground/70" />
                  <span className="text-xs text-muted-foreground">{c.signatories.length}</span>
                </div>
                <div className="col-span-2 flex items-center justify-end">
                  {selected?.contractId === c.contractId ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground/70" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground/70" />
                  )}
                </div>
              </div>

              {selected?.contractId === c.contractId && (
                <div className="mx-2 mt-1 space-y-4 rounded-b-lg border border-t-0 border-border bg-muted p-5">
                  <div>
                    <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">Contract ID</h4>
                    <div className="mt-1 flex items-center">
                      <code className="break-all font-mono text-xs text-foreground/70">{c.contractId}</code>
                      <CopyButton text={c.contractId} />
                    </div>
                  </div>
                  <div>
                    <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">Template</h4>
                    <div className="mt-1 flex items-center">
                      <code className="break-all font-mono text-xs text-accent">{c.templateId}</code>
                      <CopyButton text={c.templateId} />
                    </div>
                  </div>
                  <div>
                    <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">Signatories</h4>
                    <div className="mt-1 flex flex-wrap gap-2">
                      {c.signatories.map((s, i) => (
                        <span key={i} className="inline-flex items-center gap-1 rounded-full bg-accent/10 px-3 py-1 text-xs text-accent border border-accent/20">
                          <Shield className="h-3 w-3" />
                          {truncate(s, 30)}
                          <CopyButton text={s} />
                        </span>
                      ))}
                    </div>
                  </div>
                  {c.observers.length > 0 && (
                    <div>
                      <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">Observers</h4>
                      <div className="mt-1 flex flex-wrap gap-2">
                        {c.observers.map((o, i) => (
                          <span key={i} className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-3 py-1 text-xs text-blue-300 border border-blue-500/20">
                            <Eye className="h-3 w-3" />
                            {truncate(o, 30)}
                            <CopyButton text={o} />
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div>
                    <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">Contract Payload</h4>
                    <pre className="mt-1 max-h-64 overflow-auto rounded-lg border border-border bg-muted p-4 font-mono text-xs text-foreground/60">
                      {JSON.stringify(c.payload, null, 2)}
                    </pre>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      <div className="mt-4 text-center text-xs text-muted-foreground/70">{filtered.length} contract{filtered.length !== 1 ? "s" : ""} on ledger</div>
    </div>
  );
}

function PartiesTab() {
  const [parties, setParties] = useState<Party[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const fetchParties = async () => {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch(`${API_URL}/ledger/parties`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data: unknown = await resp.json();
      const parsed = data as { parties?: Party[] };
      setParties(parsed.parties ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch parties");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void fetchParties(); }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-accent" />
        <span className="ml-3 text-muted-foreground">Fetching parties...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center">
        <XCircle className="mx-auto h-8 w-8 text-red-400" />
        <p className="mt-2 text-sm text-red-300">{error}</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-muted-foreground">{parties.length} parties on ledger</span>
        <button onClick={() => void fetchParties()} className="rounded-lg border border-border bg-muted p-2 text-muted-foreground hover:bg-muted hover:text-foreground">
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-2">
        <div className="grid grid-cols-12 gap-4 px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
          <div className="col-span-3">Display Name</div>
          <div className="col-span-7">Identifier</div>
          <div className="col-span-2 text-right">Local</div>
        </div>

        {parties.map((p, idx) => (
          <div key={idx} className="grid grid-cols-12 gap-4 rounded-lg border border-border bg-muted px-4 py-3 hover:border-border hover:bg-muted/80 transition-all">
            <div className="col-span-3 flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-accent/20 text-xs font-bold text-accent">
                {(p.displayName || "?").charAt(0).toUpperCase()}
              </div>
              <span className="text-sm font-medium text-foreground/80">{p.displayName || "—"}</span>
            </div>
            <div className="col-span-7 flex items-center gap-1">
              <code className="truncate font-mono text-xs text-muted-foreground">{p.identifier}</code>
              <CopyButton text={p.identifier} />
            </div>
            <div className="col-span-2 flex items-center justify-end">
              {p.isLocal ? (
                <span className="inline-flex items-center gap-1 rounded-full bg-accent/10 px-2.5 py-1 text-[10px] font-medium text-accent border border-accent/20">
                  <CheckCircle2 className="h-3 w-3" /> Local
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-1 text-[10px] font-medium text-muted-foreground border border-border">
                  Remote
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PackagesTab() {
  const [packages, setPackages] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const fetchPackages = async () => {
    setLoading(true);
    setError("");
    try {
      const resp = await fetch(`${API_URL}/ledger/packages`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data: unknown = await resp.json();
      const parsed = data as { packages?: string[] };
      setPackages(parsed.packages ?? []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch packages");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void fetchPackages(); }, []);

  const filtered = packages.filter((p) => p.toLowerCase().includes(searchTerm.toLowerCase()));

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-accent" />
        <span className="ml-3 text-muted-foreground">Fetching packages...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6 text-center">
        <XCircle className="mx-auto h-8 w-8 text-red-400" />
        <p className="mt-2 text-sm text-red-300">{error}</p>
      </div>
    );
  }

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/70" />
          <input
            type="text"
            placeholder="Search packages..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-lg border border-border bg-muted py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground/70 focus:border-accent/50 focus:outline-none"
          />
        </div>
        <button onClick={() => void fetchPackages()} className="rounded-lg border border-border bg-muted p-2.5 text-muted-foreground hover:bg-muted hover:text-foreground">
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {filtered.length === 0 ? (
        <div className="py-16 text-center text-muted-foreground">
          <Package className="mx-auto h-10 w-10 text-muted-foreground/50" />
          <p className="mt-3">No packages found</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((pkg, idx) => (
            <div key={idx} className="flex items-center justify-between rounded-lg border border-border bg-muted px-4 py-3 hover:border-border hover:bg-muted/80 transition-all">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/20">
                  <Package className="h-4 w-4 text-accent" />
                </div>
                <code className="font-mono text-xs text-foreground/70">{pkg}</code>
              </div>
              <CopyButton text={pkg} />
            </div>
          ))}
        </div>
      )}
      <div className="mt-4 text-center text-xs text-muted-foreground/70">{filtered.length} package{filtered.length !== 1 ? "s" : ""} uploaded</div>
    </div>
  );
}

interface VerifyResult {
  verified: boolean;
  error?: string;
  templateId?: string;
  signatories?: string[];
  payload?: Record<string, unknown>;
  environment?: string;
}

function VerifyTab() {
  const [contractId, setContractId] = useState("");
  const [result, setResult] = useState<VerifyResult | null>(null);
  const [loading, setLoading] = useState(false);

  const verify = async () => {
    if (!contractId.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const resp = await fetch(`${API_URL}/ledger/verify/${encodeURIComponent(contractId)}`);
      const data: unknown = await resp.json();
      setResult(data as VerifyResult);
    } catch (e: unknown) {
      setResult({ verified: false, error: e instanceof Error ? e.message : "Unknown error" } satisfies VerifyResult);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/70">Contract ID</label>
        <div className="mt-2 flex gap-3">
          <input
            type="text"
            placeholder="Paste contract ID to verify..."
            value={contractId}
            onChange={(e) => setContractId(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") void verify(); }}
            className="flex-1 rounded-lg border border-border bg-muted px-4 py-3 font-mono text-sm text-foreground placeholder:text-muted-foreground/70 focus:border-accent/50 focus:outline-none"
          />
          <button
            onClick={() => void verify()}
            disabled={loading || !contractId.trim()}
            className="rounded-lg bg-accent px-6 py-3 text-sm font-medium text-black transition-colors hover:bg-accent/80 disabled:opacity-40"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : "Verify"}
          </button>
        </div>
      </div>

      {result && (
        <div className={`rounded-xl border p-6 ${result.verified ? "border-accent/20 bg-accent/5" : "border-red-500/20 bg-red-500/5"}`}>
          <div className="flex items-center gap-3">
            {result.verified ? (
              <>
                <CheckCircle2 className="h-8 w-8 text-accent" />
                <div>
                  <h3 className="text-lg font-semibold text-accent">Contract Verified</h3>
                  <p className="text-sm text-accent/60">This contract exists and is active on the Canton ledger</p>
                </div>
              </>
            ) : (
              <>
                <XCircle className="h-8 w-8 text-red-400" />
                <div>
                  <h3 className="text-lg font-semibold text-red-300">Not Found</h3>
                  <p className="text-sm text-red-300/60">{result.error ?? "Contract not found on ledger"}</p>
                </div>
              </>
            )}
          </div>

          {result.verified && (
            <div className="mt-6 space-y-4">
              <div>
                <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">Template</h4>
                <code className="mt-1 block font-mono text-xs text-accent">{result.templateId ?? ""}</code>
              </div>

              {result.signatories && result.signatories.length > 0 && (
                <div>
                  <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">Signatories</h4>
                  <div className="mt-1 flex flex-wrap gap-2">
                    {result.signatories.map((s, i) => (
                      <span key={i} className="inline-flex items-center gap-1 rounded-full bg-accent/10 px-3 py-1 text-xs text-accent border border-accent/20">
                        <Shield className="h-3 w-3" />
                        {truncate(s, 30)}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {result.payload && (
                <div>
                  <h4 className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">Payload</h4>
                  <pre className="mt-1 max-h-48 overflow-auto rounded-lg border border-border bg-muted p-4 font-mono text-xs text-foreground/60">
                    {JSON.stringify(result.payload, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Explorer Page
// ---------------------------------------------------------------------------

type TabKey = "contracts" | "parties" | "packages" | "verify";

export default function ExplorerPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("contracts");
  const [ledgerStatus, setLedgerStatus] = useState<LedgerStatus | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/ledger/status`)
      .then((r) => r.json())
      .then((d: unknown) => setLedgerStatus(d as LedgerStatus))
      .catch(() => setLedgerStatus({ status: "offline", canton_url: "", environment: "", parties: 0, packages: 0, error: "Cannot reach backend" }));
  }, []);

  const tabs: { key: TabKey; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: "contracts", label: "Contracts", icon: <FileText className="h-4 w-4" /> },
    { key: "parties", label: "Parties", icon: <Users className="h-4 w-4" />, ...(ledgerStatus?.parties != null ? { count: ledgerStatus.parties } : {}) },
    { key: "packages", label: "Packages", icon: <Package className="h-4 w-4" />, ...(ledgerStatus?.packages != null ? { count: ledgerStatus.packages } : {}) },
    { key: "verify", label: "Verify", icon: <Shield className="h-4 w-4" /> },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="border-b border-border bg-background/80 backdrop-blur-xl sticky top-0 z-50">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <Link href="/" className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors">
              <ArrowLeft className="h-4 w-4" />
              <span className="text-sm">Home</span>
            </Link>
            <div className="h-5 w-px bg-border" />
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-accent" />
              <h1 className="text-lg font-semibold text-foreground">Ledger Explorer</h1>
            </div>
          </div>

          {ledgerStatus && (
            <div className="flex items-center gap-3 rounded-full border border-border bg-muted px-4 py-1.5">
              <StatusDot online={ledgerStatus.status === "online"} />
              <span className="text-xs text-foreground/60">
                {ledgerStatus.status === "online" ? "Canton Online" : "Canton Offline"}
              </span>
              <span className="text-[10px] text-muted-foreground/70">
                {ledgerStatus.environment?.toUpperCase()}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-6 py-8">
        {/* Ledger summary cards */}
        {ledgerStatus?.status === "online" && (
          <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-4">
            <div className="rounded-xl border border-border bg-muted p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
                  <Activity className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">Online</p>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70">Ledger Status</p>
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-border bg-muted p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
                  <Users className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">{ledgerStatus.parties >= 0 ? ledgerStatus.parties : "—"}</p>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70">Parties</p>
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-border bg-muted p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
                  <Package className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">{ledgerStatus.packages >= 0 ? ledgerStatus.packages : "—"}</p>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70">Packages</p>
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-border bg-muted p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/10">
                  <Database className="h-5 w-5 text-amber-400" />
                </div>
                <div>
                  <p className="text-sm font-mono font-bold text-foreground truncate">{ledgerStatus.canton_url || "—"}</p>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground/70">{ledgerStatus.environment} endpoint</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="mb-6 flex items-center gap-1 rounded-xl border border-border bg-muted p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-all ${
                activeTab === tab.key
                  ? "bg-accent text-black shadow-lg shadow-accent/20"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground/70"
              }`}
            >
              {tab.icon}
              {tab.label}
              {tab.count !== undefined && (
                <span className={`ml-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  activeTab === tab.key ? "bg-background/20 text-black" : "bg-muted text-muted-foreground/70"
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="rounded-xl border border-border bg-muted p-6">
          {activeTab === "contracts" && <ContractsTab />}
          {activeTab === "parties" && <PartiesTab />}
          {activeTab === "packages" && <PackagesTab />}
          {activeTab === "verify" && <VerifyTab />}
        </div>
      </div>
    </div>
  );
}
