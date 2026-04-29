"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
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
  Lock,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";

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
  jobId?: string;
  history?: boolean;
  prompt?: string;
  createdAt?: string;
  hasDar?: boolean;
}

interface MyContractItem {
  job_id: string;
  contract_id: string;
  package_id: string;
  template_id: string;
  party_id: string | null;
  canton_env: string;
  explorer_link: string | null;
  created_at: string | null;
  signatories: string[];
  observers: string[];
  prompt: string;
  has_dar: boolean;
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
      className="ml-1 shrink-0 rounded-md p-1 text-muted-foreground/70 transition-colors hover:bg-foreground/10 hover:text-foreground"
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

function ContractsTab({
  partyId,
  token,
  onContractsLoaded,
}: {
  partyId: string | null;
  token: string | null;
  onContractsLoaded?: (contracts: Contract[]) => void;
}) {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Contract | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  const fetchContracts = async () => {
    setLoading(true);
    setError("");
    try {
      // 1. Live ACS for the current party (Canton-side privacy filter).
      const livePromise = (async (): Promise<Contract[]> => {
        const body = partyId ? { party: partyId } : {};
        const r = await fetch(`${API_URL}/ledger/contracts`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!r.ok) return [];
        const d = (await r.json()) as { contracts?: Contract[] };
        return d.contracts ?? [];
      })();

      // 2. User's full deployment history (across every party they ever
      //    created), keyed off email account on the backend.
      const myPromise = (async (): Promise<Contract[]> => {
        if (!token) return [];
        const r = await fetch(`${API_URL}/me/contracts`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!r.ok) return [];
        const d = (await r.json()) as { contracts?: MyContractItem[] };
        return (d.contracts ?? []).map((c): Contract => {
          const item: Contract = {
            contractId: c.contract_id,
            templateId: c.template_id || "",
            payload: {},
            signatories: c.signatories || (c.party_id ? [c.party_id] : []),
            observers: c.observers || [],
            agreementText: "",
            jobId: c.job_id,
            history: true,
            prompt: c.prompt || "",
            hasDar: !!c.has_dar,
          };
          if (c.created_at) item.createdAt = c.created_at;
          return item;
        });
      })();

      const [live, mine] = await Promise.all([livePromise, myPromise]);

      // Merge: live wins on contractId conflict (richer payload), but keep the
      // historical entries that the current party can no longer see on-ledger.
      const byId = new Map<string, Contract>();
      for (const c of mine) byId.set(c.contractId, c);
      for (const c of live) {
        const prev = byId.get(c.contractId);
        byId.set(c.contractId, prev ? { ...prev, ...c, history: false } : c);
      }
      const merged = Array.from(byId.values());
      setContracts(merged);
      onContractsLoaded?.(merged);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch contracts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void fetchContracts(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [partyId, token]);

  // No defensive client-side party filter here: /me/contracts already returns
  // only this user's history, and /ledger/contracts is already scoped to the
  // current party server-side. We deliberately keep historical contracts from
  // older parties visible (user is the stable identity, not party).
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
        <XCircle className="mx-auto h-8 w-8 text-red-500 dark:text-red-400" />
        <p className="mt-2 text-sm text-red-500 dark:text-red-300">{error}</p>
        <button onClick={() => void fetchContracts()} className="mt-3 rounded-lg bg-foreground/5 px-4 py-2 text-xs text-muted-foreground hover:bg-foreground/10">
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
            className="w-full rounded-lg border border-border bg-foreground/5 py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground/70 focus:border-accent/50 focus:outline-none"
          />
        </div>
        <button onClick={() => void fetchContracts()} className="rounded-lg border border-border bg-foreground/5 p-2.5 text-muted-foreground hover:bg-foreground/10 hover:text-foreground">
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {filtered.length === 0 ? (
        <div className="py-16 text-center text-muted-foreground/80">
          <FileText className="mx-auto h-10 w-10 text-muted-foreground/40" />
          <p className="mt-3">
            {token
              ? "You haven\u2019t deployed any contracts yet"
              : partyId
                ? "No contracts visible to your party yet"
                : "No contracts found on ledger"}
          </p>
          <p className="mt-1 text-xs text-muted-foreground/60">
            Deploy a contract from the home page to see it here.
          </p>
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
                    : "border-border bg-foreground/[0.03] hover:border-border hover:bg-foreground/[0.05]"
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
                  {c.history && (
                    <span className="ml-1 rounded-full bg-foreground/5 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-muted-foreground" title="Deployed by you in an earlier session">
                      history
                    </span>
                  )}
                </div>
                <div className="col-span-2 flex items-center justify-end gap-2">
                  {c.jobId && (
                    <a
                      href={`${API_URL}/download/${c.jobId}/source`}
                      onClick={(e) => e.stopPropagation()}
                      className="rounded-md border border-border bg-foreground/5 px-2 py-1 text-[10px] font-medium text-muted-foreground hover:bg-foreground/10 hover:text-foreground"
                      title="Download source zip"
                    >
                      Source
                    </a>
                  )}
                  {c.jobId && c.hasDar && (
                    <a
                      href={`${API_URL}/download/${c.jobId}/dar`}
                      onClick={(e) => e.stopPropagation()}
                      className="rounded-md border border-accent/30 bg-accent/10 px-2 py-1 text-[10px] font-medium text-accent hover:bg-accent/20"
                      title="Download compiled DAR"
                    >
                      DAR
                    </a>
                  )}
                  {selected?.contractId === c.contractId ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground/70" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground/70" />
                  )}
                </div>
              </div>

              {selected?.contractId === c.contractId && (
                <div className="mx-2 mt-1 space-y-4 rounded-b-lg border border-t-0 border-border bg-foreground/[0.03] p-5">
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
                          <span key={i} className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-3 py-1 text-xs text-blue-600 dark:text-blue-300 border border-blue-500/20">
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
                    <pre className="mt-1 max-h-64 overflow-auto rounded-lg border border-border bg-muted p-4 font-mono text-xs text-muted-foreground">
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

function PartiesTab({
  relevantPartyIds,
  currentPartyId,
  token,
}: {
  relevantPartyIds: Set<string>;
  currentPartyId: string | null;
  token: string | null;
}) {
  const [parties, setParties] = useState<Party[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  // ``user-owned`` when /me/parties responded, ``ledger`` when we fell back
  // to the global Canton listing. Drives the on-screen scope hint.
  const [scope, setScope] = useState<"user-owned" | "ledger">("ledger");
  // When we have a token but /me/parties returned non-2xx, capture why so the
  // UI can surface it instead of silently masquerading as the ledger view.
  const [meFailure, setMeFailure] = useState<string | null>(null);

  const fetchParties = async () => {
    setLoading(true);
    setError("");
    setMeFailure(null);
    try {
      // Authenticated path: ask the backend for ONLY this user's parties.
      // Sourced entirely from our Postgres tables, so it's immune to the
      // shared-sandbox 500s that ``/ledger/parties`` is prone to.
      if (token) {
        try {
          const resp = await fetch(`${API_URL}/me/parties`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (resp.ok) {
            const data = (await resp.json()) as {
              parties?: Party[];
              scope?: string;
              partial_errors?: string[];
            };
            setParties(data.parties ?? []);
            setScope("user-owned");
            if (data.partial_errors && data.partial_errors.length > 0) {
              setMeFailure(`Partial: ${data.partial_errors.join("; ")}`);
            }
            return;
          }
          // 4xx/5xx \u2014 record why and fall through to the public ledger
          // listing. We DO NOT silently filter the fallback to empty: the
          // banner makes it clear the user is seeing the global view.
          let body = "";
          try { body = (await resp.text()).slice(0, 200); } catch { /* ignore */ }
          setMeFailure(`/me/parties HTTP ${resp.status}${body ? `: ${body}` : ""}`);
        } catch (e: unknown) {
          setMeFailure(`/me/parties failed: ${e instanceof Error ? e.message : String(e)}`);
        }
      }

      const resp = await fetch(`${API_URL}/ledger/parties`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = (await resp.json()) as { parties?: Party[]; ledger_error?: string };
      setParties(data.parties ?? []);
      setScope("ledger");
      if (data.ledger_error && (data.parties ?? []).length === 0) {
        setError(`Canton ledger temporarily unavailable: ${data.ledger_error}`);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch parties");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void fetchParties(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [token]);

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
        <XCircle className="mx-auto h-8 w-8 text-red-500 dark:text-red-400" />
        <p className="mt-2 text-sm text-red-500 dark:text-red-300">{error}</p>
      </div>
    );
  }

  // Show only parties relevant to the authenticated user. When the
  // backend already scoped the response to ``user-owned`` we trust it
  // verbatim — those rows are sourced from RegisteredParty +
  // DeployedContract joined to the user's email, so client-side
  // filtering would only re-introduce false negatives for the user's
  // own historical parties. When the response came from /ledger/parties
  // (unauthenticated or fallback path) we apply the legacy counterparty
  // filter ONLY when we actually have something to filter against;
  // otherwise we'd hide every party on the ledger and lie about the
  // count, which is what made this tab look broken before.
  const haveCounterpartyHints =
    !!currentPartyId || relevantPartyIds.size > 0;
  const visible =
    scope === "user-owned"
      ? parties
      : haveCounterpartyHints
      ? parties.filter((p) => {
          if (currentPartyId && p.identifier === currentPartyId) return true;
          if (relevantPartyIds.has(p.identifier)) return true;
          return false;
        })
      : parties;

  return (
    <div>
      {meFailure && (
        <div className="mb-4 rounded-lg border border-yellow-500/30 bg-yellow-500/5 px-4 py-3 text-xs text-yellow-600 dark:text-yellow-300">
          <span className="font-semibold">Couldn&apos;t load your scoped parties.</span>{" "}
          Showing the global ledger view instead. Detail: <code>{meFailure}</code>
        </div>
      )}
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm text-muted-foreground/80">
          {scope === "user-owned"
            ? `${visible.length} part${visible.length === 1 ? "y" : "ies"} you own`
            : haveCounterpartyHints
            ? `${visible.length} of ${parties.length} parties (yours & counterparties)`
            : `${visible.length} part${visible.length === 1 ? "y" : "ies"} on ledger`}
        </span>
        <button onClick={() => void fetchParties()} className="rounded-lg border border-border bg-foreground/5 p-2 text-muted-foreground hover:bg-foreground/10 hover:text-foreground">
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      <div className="space-y-2">
        <div className="grid grid-cols-12 gap-4 px-4 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
          <div className="col-span-3">Display Name</div>
          <div className="col-span-7">Identifier</div>
          <div className="col-span-2 text-right">Local</div>
        </div>

        {visible.length === 0 && (
          <div className="py-12 text-center text-xs text-muted-foreground/70">
            {scope === "user-owned" ? (
              <>
                No parties linked to your account yet. Parties get
                auto-registered to your account when you deploy a contract
                from the Sandbox &mdash; head there to create one.
              </>
            ) : haveCounterpartyHints ? (
              <>No counterparties for your current session yet.</>
            ) : (
              <>No parties visible on this ledger.</>
            )}
          </div>
        )}

        {visible.map((p, idx) => (
          <div key={idx} className="grid grid-cols-12 gap-4 rounded-lg border border-border bg-foreground/[0.03] px-4 py-3 hover:border-border hover:bg-foreground/[0.05] transition-all">
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
                <span className="inline-flex items-center gap-1 rounded-full bg-foreground/5 px-2.5 py-1 text-[10px] font-medium text-muted-foreground/80 border border-border">
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

function PackagesTab({ token }: { token: string | null }) {
  // ``packages`` may be either a list of raw package_id strings (the
  // shape ``/ledger/packages`` returns) OR a list of objects from
  // ``/me/packages``. Normalise to {package_id, template_id?, contracts?}
  // so the renderer doesn't care which endpoint we hit.
  type PackageEntry = { package_id: string; template_id?: string; contracts?: number };
  const [packages, setPackages] = useState<PackageEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [scope, setScope] = useState<"user-owned" | "ledger">("ledger");
  const [meFailure, setMeFailure] = useState<string | null>(null);

  const fetchPackages = async () => {
    setLoading(true);
    setError("");
    setMeFailure(null);
    try {
      // Authenticated path first \u2014 sourced from our DB so it works
      // even when Canton's /v1/packages 500s with a JWT-scope error.
      if (token) {
        try {
          const resp = await fetch(`${API_URL}/me/packages`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (resp.ok) {
            const data = (await resp.json()) as { packages?: PackageEntry[] };
            setPackages(data.packages ?? []);
            setScope("user-owned");
            return;
          }
          let body = "";
          try { body = (await resp.text()).slice(0, 200); } catch { /* ignore */ }
          setMeFailure(`/me/packages HTTP ${resp.status}${body ? `: ${body}` : ""}`);
        } catch (e: unknown) {
          setMeFailure(`/me/packages failed: ${e instanceof Error ? e.message : String(e)}`);
        }
      }

      const resp = await fetch(`${API_URL}/ledger/packages`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = (await resp.json()) as {
        packages?: (string | PackageEntry)[];
        ledger_error?: string;
      };
      const raw = data.packages ?? [];
      const normalised: PackageEntry[] = raw.map((p) =>
        typeof p === "string" ? { package_id: p } : p
      );
      setPackages(normalised);
      setScope("ledger");
      if (data.ledger_error && normalised.length === 0) {
        setError(`Canton ledger temporarily unavailable: ${data.ledger_error}`);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to fetch packages");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void fetchPackages(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [token]);

  const needle = searchTerm.toLowerCase();
  const filtered = packages.filter((p) => {
    if (!needle) return true;
    return (
      p.package_id.toLowerCase().includes(needle) ||
      (p.template_id ?? "").toLowerCase().includes(needle)
    );
  });

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
        <XCircle className="mx-auto h-8 w-8 text-red-500 dark:text-red-400" />
        <p className="mt-2 text-sm text-red-500 dark:text-red-300">{error}</p>
      </div>
    );
  }

  return (
    <div>
      {meFailure && (
        <div className="mb-4 rounded-lg border border-yellow-500/30 bg-yellow-500/5 px-4 py-3 text-xs text-yellow-600 dark:text-yellow-300">
          <span className="font-semibold">Couldn&apos;t load your scoped packages.</span>{" "}
          Showing the global ledger view instead. Detail: <code>{meFailure}</code>
        </div>
      )}
      <div className="mb-4 flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground/70" />
          <input
            type="text"
            placeholder="Search packages..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full rounded-lg border border-border bg-foreground/5 py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-muted-foreground/70 focus:border-accent/50 focus:outline-none"
          />
        </div>
        <button onClick={() => void fetchPackages()} className="rounded-lg border border-border bg-foreground/5 p-2.5 text-muted-foreground hover:bg-foreground/10 hover:text-foreground">
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {filtered.length === 0 ? (
        <div className="py-16 text-center text-muted-foreground/80">
          <Package className="mx-auto h-10 w-10 text-muted-foreground/40" />
          <p className="mt-3">No packages found</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map((pkg, idx) => (
            <div key={idx} className="flex items-center justify-between rounded-lg border border-border bg-foreground/[0.03] px-4 py-3 hover:border-border hover:bg-foreground/[0.05] transition-all">
              <div className="flex min-w-0 items-center gap-3">
                <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-accent/20">
                  <Package className="h-4 w-4 text-accent" />
                </div>
                <div className="min-w-0">
                  <code className="block truncate font-mono text-xs text-foreground/70">{pkg.package_id}</code>
                  {pkg.template_id && (
                    <span className="block truncate text-[10px] text-muted-foreground/60">{pkg.template_id}</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {typeof pkg.contracts === "number" && (
                  <span className="rounded-full bg-foreground/5 px-2 py-0.5 text-[10px] text-muted-foreground/80 border border-border">
                    {pkg.contracts} contract{pkg.contracts === 1 ? "" : "s"}
                  </span>
                )}
                <CopyButton text={pkg.package_id} />
              </div>
            </div>
          ))}
        </div>
      )}
      <div className="mt-4 text-center text-xs text-muted-foreground/70">
        {scope === "user-owned"
          ? `${filtered.length} package${filtered.length !== 1 ? "s" : ""} you uploaded`
          : `${filtered.length} package${filtered.length !== 1 ? "s" : ""} on ledger`}
      </div>
    </div>
  );
}

interface VerifyResult {
  verified: boolean;
  error?: string;
  status?: string;
  template_id?: string;
  deployed_at?: string;
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
            className="flex-1 rounded-lg border border-border bg-foreground/5 px-4 py-3 font-mono text-sm text-foreground placeholder:text-muted-foreground/70 focus:border-accent/50 focus:outline-none"
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
                <XCircle className={`h-8 w-8 ${result.status === "deployed_but_unreachable" ? "text-yellow-500 dark:text-yellow-400" : "text-red-500 dark:text-red-400"}`} />
                <div>
                  <h3 className={`text-lg font-semibold ${result.status === "deployed_but_unreachable" ? "text-yellow-500 dark:text-yellow-300" : "text-red-500 dark:text-red-300"}`}>
                    {result.status === "deployed_but_unreachable" ? "Deployed, but not currently on ledger" : "Not Found"}
                  </h3>
                  <p className={`text-sm ${result.status === "deployed_but_unreachable" ? "text-yellow-500/70 dark:text-yellow-300/70" : "text-red-500/70 dark:text-red-300/70"}`}>
                    {result.error ?? "Contract not found on ledger"}
                  </p>
                  {result.status === "deployed_but_unreachable" && result.deployed_at && (
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      Originally deployed {new Date(result.deployed_at).toLocaleString()}
                    </p>
                  )}
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
                  <pre className="mt-1 max-h-48 overflow-auto rounded-lg border border-border bg-muted p-4 font-mono text-xs text-muted-foreground">
                    {JSON.stringify(result.payload, null, 2)}
                  </pre>
                </div>
              )}

              {/*
                Privacy-projection disclaimer. Canton's privacy guarantees
                rely on PARTICIPANT-LEVEL projection: each participant
                sees only the subset of transactions its parties signed
                or observed. Single-participant sandbox cannot prove this
                \u2014 every party shares one participant, so "visible to"
                is meaningless. Surface the limitation here so users do
                not infer privacy guarantees from a green Verify badge.
                See "The Complete Guide" \u00a72.11.
              */}
              <div className="rounded-lg border border-yellow-500/20 bg-yellow-500/5 p-3 text-[11px] leading-relaxed text-yellow-700 dark:text-yellow-300/80">
                <strong className="font-semibold">Privacy not yet validated.</strong>{" "}
                This contract has been validated on a single-participant
                Canton sandbox. Cross-participant privacy projection
                (the property that Party B&apos;s participant cannot see
                Party A&apos;s contracts) has <em>not</em> been tested.
                Re-run on a multi-participant LocalNet or DevNet before
                claiming privacy guarantees.
              </div>
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
  const { isAuthenticated, partyId, token } = useAuth();
  const [mounted, setMounted] = useState(false);
  const [userContracts, setUserContracts] = useState<Contract[]>([]);

  // Build the set of party identifiers that should be visible in the Parties
  // tab: every signatory/observer that appears in this user's contracts.
  const relevantPartyIds = useMemo(() => {
    const s = new Set<string>();
    for (const c of userContracts) {
      for (const sig of c.signatories) s.add(sig);
      for (const obs of c.observers) s.add(obs);
    }
    if (partyId) s.add(partyId);
    return s;
  }, [userContracts, partyId]);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    fetch(`${API_URL}/ledger/status`)
      .then((r) => r.json())
      .then((d: unknown) => setLedgerStatus(d as LedgerStatus))
      .catch(() => setLedgerStatus({ status: "offline", canton_url: "", environment: "", parties: 0, packages: 0, error: "Cannot reach backend" }));
  }, [isAuthenticated]);

  // --- Auth gate: require sign-in before showing any ledger data ---
  if (mounted && !isAuthenticated) {
    return (
      <div className="min-h-screen bg-background pt-32 pb-20">
        <div className="mx-auto max-w-md px-6">
          <div className="rounded-2xl border border-border bg-frame p-8 text-center shadow-lg">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10">
              <Lock className="h-7 w-7 text-accent" />
            </div>
            <h1 className="mt-5 text-2xl font-semibold text-foreground">Sign in required</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Create your party identity to access the Canton Ledger Explorer and browse contracts, parties, and packages.
            </p>
            <Link
              href="/setup"
              className="mt-6 inline-flex items-center justify-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-black shadow-lg shadow-accent/30 hover:bg-accent/90 transition-colors"
            >
              <Shield className="h-4 w-4" />
              Create Party & Sign in
            </Link>
            <Link
              href="/"
              className="mt-3 block text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Return to home
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Avoid flashing auth-gate on initial SSR hydration
  if (!mounted) {
    return (
      <div className="min-h-screen bg-background pt-32 flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-accent" />
      </div>
    );
  }

  const tabs: { key: TabKey; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: "contracts", label: "Contracts", icon: <FileText className="h-4 w-4" /> },
    { key: "parties", label: "Parties", icon: <Users className="h-4 w-4" />, ...(ledgerStatus?.parties != null && ledgerStatus.parties >= 0 ? { count: ledgerStatus.parties } : {}) },
    { key: "packages", label: "Packages", icon: <Package className="h-4 w-4" />, ...(ledgerStatus?.packages != null && ledgerStatus.packages >= 0 ? { count: ledgerStatus.packages } : {}) },
    { key: "verify", label: "Verify", icon: <Shield className="h-4 w-4" /> },
  ];

  return (
    <div className="min-h-screen bg-background">
      {/* Extra top padding so content clears the floating site header pill */}
      <div className="mx-auto max-w-6xl px-6 pt-28 pb-12 max-[850px]:pt-24">
        {/* Page title + status */}
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10">
              <Database className="h-5 w-5 text-accent" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Ledger Explorer</h1>
              <p className="text-xs text-muted-foreground">Browse the Canton sandbox state</p>
            </div>
          </div>

          {ledgerStatus && (
            <div className="flex items-center gap-3 rounded-full border border-border bg-muted px-4 py-1.5">
              <StatusDot online={ledgerStatus.status === "online"} />
              <span className="text-xs text-foreground/70">
                {ledgerStatus.status === "online" ? "Canton Online" : "Canton Offline"}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {ledgerStatus.environment?.toUpperCase()}
              </span>
            </div>
          )}
        </div>

        {/* Ledger summary cards */}
        {ledgerStatus?.status === "online" && (
          <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-4">
            <div className="rounded-xl border border-border bg-frame p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
                  <Activity className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">Online</p>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Ledger Status</p>
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-border bg-frame p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
                  <Users className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">{ledgerStatus.parties >= 0 ? ledgerStatus.parties : "—"}</p>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Parties</p>
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-border bg-frame p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/10">
                  <Package className="h-5 w-5 text-accent" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">{ledgerStatus.packages >= 0 ? ledgerStatus.packages : "—"}</p>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Packages</p>
                </div>
              </div>
            </div>
            <div className="rounded-xl border border-border bg-frame p-5">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/10">
                  <Database className="h-5 w-5 text-amber-500" />
                </div>
                <div>
                  <p className="text-sm font-mono font-bold text-foreground truncate">{ledgerStatus.canton_url || "—"}</p>
                  <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{ledgerStatus.environment} endpoint</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="mb-6 flex flex-wrap items-center gap-1 rounded-xl border border-border bg-frame p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-all ${
                activeTab === tab.key
                  ? "bg-accent text-black shadow-lg shadow-accent/20"
                  : "text-muted-foreground hover:bg-foreground/5 hover:text-foreground"
              }`}
            >
              {tab.icon}
              {tab.label}
              {tab.count !== undefined && (
                <span className={`ml-1 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  activeTab === tab.key ? "bg-black/20 text-black" : "bg-muted text-muted-foreground"
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="rounded-xl border border-border bg-frame p-6">
          {activeTab === "contracts" && (
            <ContractsTab partyId={partyId} token={token} onContractsLoaded={setUserContracts} />
          )}
          {activeTab === "parties" && (
            <PartiesTab
              relevantPartyIds={relevantPartyIds}
              currentPartyId={partyId}
              token={token}
            />
          )}
          {activeTab === "packages" && <PackagesTab token={token} />}
          {activeTab === "verify" && <VerifyTab />}
        </div>
      </div>
    </div>
  );
}
