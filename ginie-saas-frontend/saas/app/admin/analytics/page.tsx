"use client";

import {
  Activity,
  CheckCircle2,
  DollarSign,
  Flame,
  Layers,
  Loader2,
  LogOut,
  RefreshCw,
  Shield,
  Sparkles,
  TrendingUp,
  Trophy,
  Users,
  Zap,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Totals {
  users: number;
  verified_users: number;
  parties: number;
  deployed_contracts: number;
  total_jobs: number;
  successful_jobs: number;
  success_rate: number;
  invite_codes_total: number;
  invite_codes_used: number;
  estimated_cc_burn: number;
  cc_burn_per_contract: number;
  estimated_usd_value: number;
  cc_to_usd_rate: number;
}

type RangeKey = "1h" | "6h" | "12h" | "1d" | "7d" | "30d";

const RANGE_OPTIONS: { key: RangeKey; label: string }[] = [
  { key: "1h", label: "1H" },
  { key: "6h", label: "6H" },
  { key: "12h", label: "12H" },
  { key: "1d", label: "1D" },
  { key: "7d", label: "1W" },
  { key: "30d", label: "30D" },
];

interface TimelinePoint {
  date: string;
  users: number;
  contracts: number;
  jobs: number;
  successful: number;
}

interface ActiveUser {
  email: string;
  contracts: number;
  deploys: number;
  display_name?: string;
  xp?: number;
}

interface Analytics {
  totals: Totals;
  range: RangeKey;
  bucket_seconds: number;
  timeline: TimelinePoint[];
  most_active_users: ActiveUser[];
  env_breakdown: { env: string; count: number }[];
  top_templates: { template: string; count: number }[];
  status_breakdown: { status: string; count: number }[];
  generated_at: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return n.toLocaleString();
}

function formatTick(iso: string, bucketSeconds: number): string {
  const d = new Date(iso);
  if (bucketSeconds < 3600) {
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  if (bucketSeconds < 3600 * 24) {
    return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function formatFull(iso: string, bucketSeconds: number): string {
  const d = new Date(iso);
  if (bucketSeconds < 3600 * 24) {
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  return d.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatUSD(n: number): string {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(2)}K`;
  return `$${n.toFixed(2)}`;
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  icon,
  label,
  value,
  sublabel,
  accent,
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
  sublabel?: string;
  accent?: "green" | "blue" | "amber" | "purple" | "red" | "neutral";
}): ReactNode {
  const accentClasses: Record<string, string> = {
    green: "bg-emerald-50 text-emerald-600 border-emerald-100",
    blue: "bg-blue-50 text-blue-600 border-blue-100",
    amber: "bg-amber-50 text-amber-600 border-amber-100",
    purple: "bg-purple-50 text-purple-600 border-purple-100",
    red: "bg-red-50 text-red-600 border-red-100",
    neutral: "bg-neutral-50 text-neutral-600 border-neutral-100",
  };
  const cls = accentClasses[accent ?? "neutral"];
  return (
    <div className="bg-white rounded-2xl border border-neutral-200 p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between gap-3 mb-3">
        <div
          className={`inline-flex items-center justify-center w-10 h-10 rounded-xl border ${cls}`}
        >
          {icon}
        </div>
      </div>
      <div className="text-2xl font-semibold text-neutral-900 leading-tight">
        {typeof value === "number" ? formatNumber(value) : value}
      </div>
      <div className="text-xs text-neutral-500 mt-1">{label}</div>
      {sublabel && (
        <div className="text-[11px] text-neutral-400 mt-2">{sublabel}</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Line / area chart (SVG)
// ---------------------------------------------------------------------------

function TimelineChart({
  data,
  keys,
  bucketSeconds,
}: {
  data: TimelinePoint[];
  keys: { key: keyof TimelinePoint; label: string; color: string }[];
  bucketSeconds: number;
}): ReactNode {
  const width = 800;
  const height = 260;
  const padding = { top: 20, right: 20, bottom: 36, left: 40 };
  const [hover, setHover] = useState<number | null>(null);

  const maxY = useMemo(() => {
    let m = 0;
    for (const d of data) {
      for (const k of keys) {
        const v = d[k.key] as number;
        if (v > m) m = v;
      }
    }
    return Math.max(m, 4);
  }, [data, keys]);

  const innerW = width - padding.left - padding.right;
  const innerH = height - padding.top - padding.bottom;
  const xStep = data.length > 1 ? innerW / (data.length - 1) : innerW;

  const xFor = (i: number) => padding.left + i * xStep;
  const yFor = (v: number) =>
    padding.top + innerH - (v / maxY) * innerH;

  const buildPath = (key: keyof TimelinePoint) =>
    data
      .map((d, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(d[key] as number)}`)
      .join(" ");

  const buildArea = (key: keyof TimelinePoint) => {
    const line = data
      .map((d, i) => `${i === 0 ? "M" : "L"}${xFor(i)},${yFor(d[key] as number)}`)
      .join(" ");
    return `${line} L${xFor(data.length - 1)},${padding.top + innerH} L${xFor(0)},${padding.top + innerH} Z`;
  };

  // Y-axis gridlines at 4 intervals
  const gridY = [0, 0.25, 0.5, 0.75, 1].map((t) => ({
    y: padding.top + innerH - t * innerH,
    value: Math.round(t * maxY),
  }));

  // X tick labels — aim for ~6 evenly spaced labels regardless of range.
  const tickStride = Math.max(1, Math.round(data.length / 6));
  const xTickIdx = data
    .map((_, i) => i)
    .filter((i) => i % tickStride === 0 || i === data.length - 1);

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-auto"
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          {keys.map((k) => (
            <linearGradient
              key={k.key}
              id={`grad-${k.key}`}
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop offset="0%" stopColor={k.color} stopOpacity="0.25" />
              <stop offset="100%" stopColor={k.color} stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>

        {/* Grid */}
        {gridY.map((g, i) => (
          <g key={i}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={g.y}
              y2={g.y}
              stroke="#f1f1f1"
              strokeDasharray="3 3"
            />
            <text
              x={padding.left - 8}
              y={g.y + 4}
              textAnchor="end"
              className="fill-neutral-400"
              style={{ fontSize: 10 }}
            >
              {g.value}
            </text>
          </g>
        ))}

        {/* Area fills */}
        {keys.map((k) => (
          <path
            key={`area-${k.key}`}
            d={buildArea(k.key)}
            fill={`url(#grad-${k.key})`}
          />
        ))}

        {/* Lines */}
        {keys.map((k) => (
          <path
            key={`line-${k.key}`}
            d={buildPath(k.key)}
            fill="none"
            stroke={k.color}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}

        {/* Hover dot + invisible hover zones */}
        {hover !== null && data[hover] && (
          <g>
            <line
              x1={xFor(hover)}
              x2={xFor(hover)}
              y1={padding.top}
              y2={padding.top + innerH}
              stroke="#d4d4d4"
              strokeDasharray="3 3"
            />
            {keys.map((k) => {
              const point = data[hover]!;
              return (
                <circle
                  key={`dot-${k.key}`}
                  cx={xFor(hover)}
                  cy={yFor(point[k.key] as number)}
                  r={4}
                  fill="white"
                  stroke={k.color}
                  strokeWidth={2}
                />
              );
            })}
          </g>
        )}
        {data.map((_, i) => (
          <rect
            key={i}
            x={xFor(i) - xStep / 2}
            y={padding.top}
            width={xStep}
            height={innerH}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}

        {/* X axis ticks */}
        {xTickIdx.map((i) => {
          const point = data[i];
          if (!point) return null;
          return (
            <text
              key={i}
              x={xFor(i)}
              y={height - 14}
              textAnchor="middle"
              className="fill-neutral-400"
              style={{ fontSize: 10 }}
            >
              {formatTick(point.date, bucketSeconds)}
            </text>
          );
        })}
      </svg>

      {/* Tooltip */}
      {hover !== null && data[hover] && (
        <div
          className="absolute top-2 right-2 bg-white border border-neutral-200 rounded-lg shadow-lg px-3 py-2 text-xs pointer-events-none"
        >
          <div className="font-medium text-neutral-900 mb-1">
            {formatFull(data[hover]!.date, bucketSeconds)}
          </div>
          {keys.map((k) => (
            <div
              key={k.key}
              className="flex items-center gap-2 text-neutral-600"
            >
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ background: k.color }}
              />
              <span>
                {k.label}: <strong>{data[hover]![k.key] as number}</strong>
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="flex flex-wrap gap-4 mt-2 text-xs text-neutral-600">
        {keys.map((k) => (
          <div key={k.key} className="flex items-center gap-1.5">
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ background: k.color }}
            />
            {k.label}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Horizontal bar chart (SVG)
// ---------------------------------------------------------------------------

function BarChart({
  data,
  color = "#16a34a",
}: {
  data: { label: string; value: number }[];
  color?: string;
}): ReactNode {
  if (data.length === 0) {
    return (
      <p className="text-xs text-neutral-400 py-8 text-center">
        No data available yet.
      </p>
    );
  }
  const max = Math.max(...data.map((d) => d.value), 1);
  return (
    <div className="space-y-2.5">
      {data.map((d) => {
        const pct = Math.round((d.value / max) * 100);
        return (
          <div key={d.label}>
            <div className="flex items-center justify-between text-xs text-neutral-600 mb-1">
              <span className="truncate max-w-[70%]" title={d.label}>
                {d.label}
              </span>
              <span className="font-medium text-neutral-900">{d.value}</span>
            </div>
            <div className="h-2 bg-neutral-100 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${pct}%`, background: color }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Donut chart (SVG)
// ---------------------------------------------------------------------------

const DONUT_COLORS = ["#16a34a", "#2563eb", "#f59e0b", "#a855f7", "#ef4444", "#06b6d4"];

function DonutChart({
  data,
}: {
  data: { label: string; value: number }[];
}): ReactNode {
  const size = 160;
  const stroke = 22;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const total = data.reduce((sum, d) => sum + d.value, 0);

  if (total === 0) {
    return (
      <p className="text-xs text-neutral-400 py-8 text-center">
        No data available yet.
      </p>
    );
  }

  // Precompute cumulative offsets so rendering stays side-effect-free.
  const segments = data.map((d, i) => {
    const len = (d.value / total) * c;
    const prior = data
      .slice(0, i)
      .reduce((sum, p) => sum + (p.value / total) * c, 0);
    return { d, i, len, offset: prior };
  });

  return (
    <div className="flex items-center gap-6 flex-wrap">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="#f5f5f5"
          strokeWidth={stroke}
        />
        {segments.map(({ d, i, len, offset }) => (
          <circle
            key={d.label}
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={DONUT_COLORS[i % DONUT_COLORS.length]}
            strokeWidth={stroke}
            strokeDasharray={`${len} ${c - len}`}
            strokeDashoffset={-offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            strokeLinecap="butt"
          />
        ))}
        <text
          x={size / 2}
          y={size / 2 - 4}
          textAnchor="middle"
          className="fill-neutral-900"
          style={{ fontSize: 22, fontWeight: 600 }}
        >
          {formatNumber(total)}
        </text>
        <text
          x={size / 2}
          y={size / 2 + 14}
          textAnchor="middle"
          className="fill-neutral-400"
          style={{ fontSize: 10 }}
        >
          Total
        </text>
      </svg>
      <div className="space-y-2 text-xs">
        {data.map((d, i) => (
          <div key={d.label} className="flex items-center gap-2">
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }}
            />
            <span className="capitalize text-neutral-700">{d.label}</span>
            <span className="text-neutral-400">— {d.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function AnalyticsPage() {
  const router = useRouter();
  const [data, setData] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [range, setRange] = useState<RangeKey>("30d");

  const fetchAnalytics = useCallback(
    async (rangeKey: RangeKey) => {
      const pwd =
        typeof window !== "undefined"
          ? sessionStorage.getItem("ginie_admin_password")
          : null;
      if (!pwd) {
        router.replace("/admin");
        return;
      }
      try {
        const resp = await fetch(
          `${API_URL}/admin/analytics?range=${rangeKey}`,
          { headers: { "X-Admin-Password": pwd } },
        );
        if (resp.status === 401) {
          sessionStorage.removeItem("ginie_admin_password");
          router.replace("/admin");
          return;
        }
        if (!resp.ok) {
          setError("Failed to load analytics.");
          return;
        }
        const d = (await resp.json()) as Analytics;
        setData(d);
        setError(null);
      } catch {
        setError("Network error loading analytics.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [router],
  );

  useEffect(() => {
    fetchAnalytics(range);
  }, [fetchAnalytics, range]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchAnalytics(range);
  };

  const handleLogout = () => {
    sessionStorage.removeItem("ginie_admin_password");
    router.replace("/admin");
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-50">
        <div className="flex items-center gap-3 text-neutral-500">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Loading analytics…</span>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-neutral-50 p-4">
        <div className="bg-white rounded-2xl border border-neutral-200 p-6 max-w-md text-center shadow-sm">
          <p className="text-sm text-red-600 mb-4">{error || "No data"}</p>
          <button
            onClick={handleRefresh}
            className="px-4 py-2 rounded-lg bg-black text-white text-sm font-medium hover:bg-neutral-800"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const { totals, timeline, most_active_users, env_breakdown, top_templates, status_breakdown } = data;
  const maxXp = Math.max(...most_active_users.map((u) => u.xp ?? 0), 1);

  return (
    <div className="min-h-screen bg-gradient-to-br from-neutral-50 via-white to-accent/5 pb-16">
      {/* Top bar */}
      <header className="sticky top-0 z-20 bg-white/85 backdrop-blur-md border-b border-neutral-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-neutral-900 to-neutral-700 flex items-center justify-center shadow-sm flex-none">
              <Shield className="w-4 h-4 text-accent" />
            </div>
            <div className="min-w-0">
              <h1 className="text-lg font-semibold text-neutral-900 leading-tight flex items-center gap-2">
                Ginie Analytics
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[10px] font-medium border border-emerald-100">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Live
                </span>
              </h1>
              <p className="text-[11px] text-neutral-500 truncate">
                Generated {new Date(data.generated_at).toLocaleString()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-neutral-700 bg-white border border-neutral-200 hover:bg-neutral-50 disabled:opacity-50 transition-colors"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`}
              />
              <span className="hidden sm:inline">Refresh</span>
            </button>
            <button
              onClick={handleLogout}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-neutral-700 bg-white border border-neutral-200 hover:bg-neutral-50 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Log out</span>
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 pt-8 space-y-6">
        {/* CC Burn hero — flagship metric for Canton */}
        <section className="relative overflow-hidden rounded-3xl border border-amber-200/50 bg-gradient-to-br from-amber-50 via-orange-50 to-rose-50 p-6 sm:p-8">
          <div className="absolute -top-12 -right-12 w-48 h-48 rounded-full bg-amber-200/40 blur-3xl pointer-events-none" />
          <div className="absolute -bottom-16 -left-8 w-56 h-56 rounded-full bg-orange-200/30 blur-3xl pointer-events-none" />
          <div className="relative flex flex-col lg:flex-row lg:items-end lg:justify-between gap-6">
            <div>
              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/70 border border-amber-200 text-[11px] font-medium text-amber-800 mb-3">
                <Sparkles className="w-3 h-3" />
                Canton Coin Impact
              </div>
              <h2 className="text-sm font-medium text-amber-900/80 uppercase tracking-wider mb-2">
                Estimated CC Burned by Ginie Deployments
              </h2>
              <div className="flex items-baseline gap-3 flex-wrap">
                <div className="text-5xl sm:text-6xl font-semibold text-neutral-900 tabular-nums leading-none">
                  {formatNumber(totals.estimated_cc_burn)}
                </div>
                <div className="text-2xl font-medium text-amber-700">CC</div>
              </div>
              <p className="text-xs text-amber-900/70 mt-2">
                Across <strong>{totals.deployed_contracts.toLocaleString()}</strong> deployed contracts
                · ~{totals.cc_burn_per_contract} CC / contract
              </p>
            </div>

            <div className="flex items-stretch gap-4">
              <div className="bg-white/80 backdrop-blur-sm border border-amber-200/60 rounded-2xl px-5 py-4 min-w-[180px]">
                <div className="flex items-center gap-1.5 text-[11px] font-medium text-neutral-500 uppercase tracking-wider mb-1">
                  <DollarSign className="w-3 h-3" />
                  USD Value
                </div>
                <div className="text-3xl font-semibold text-emerald-700 tabular-nums">
                  {formatUSD(totals.estimated_usd_value)}
                </div>
                <div className="text-[10px] text-neutral-400 mt-1">
                  @ ${totals.cc_to_usd_rate.toFixed(3)} per CC
                </div>
              </div>
              <div className="hidden sm:flex bg-white/80 backdrop-blur-sm border border-amber-200/60 rounded-2xl px-5 py-4 min-w-[180px] flex-col justify-between">
                <div className="flex items-center gap-1.5 text-[11px] font-medium text-neutral-500 uppercase tracking-wider mb-1">
                  <Flame className="w-3 h-3" />
                  Success Rate
                </div>
                <div className="text-3xl font-semibold text-neutral-900 tabular-nums">
                  {totals.success_rate}%
                </div>
                <div className="text-[10px] text-neutral-400 mt-1">
                  Robust, production-grade pipeline
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* Top-level stats */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            icon={<Users className="w-5 h-5" />}
            label="Total Users"
            value={totals.users}
            sublabel={`${totals.verified_users} verified`}
            accent="blue"
          />
          <StatCard
            icon={<Layers className="w-5 h-5" />}
            label="Deployed Contracts"
            value={totals.deployed_contracts}
            sublabel={`${totals.success_rate}% success rate`}
            accent="green"
          />
          <StatCard
            icon={<Shield className="w-5 h-5" />}
            label="Parties Allocated"
            value={totals.parties}
            sublabel="On Canton ledger"
            accent="purple"
          />
          <StatCard
            icon={<CheckCircle2 className="w-5 h-5" />}
            label="Successful Generations"
            value={totals.successful_jobs}
            sublabel={`${totals.success_rate}% success rate`}
            accent="green"
          />
        </section>

        {/* Secondary stats */}
        <section className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <StatCard
            icon={<Zap className="w-5 h-5" />}
            label="Total Generations"
            value={totals.total_jobs}
            sublabel="Completed + in-flight"
            accent="neutral"
          />
          <StatCard
            icon={<Activity className="w-5 h-5" />}
            label="Invite Codes Used"
            value={`${totals.invite_codes_used}/${totals.invite_codes_total}`}
            sublabel={`${totals.invite_codes_total - totals.invite_codes_used} remaining`}
            accent="neutral"
          />
          <StatCard
            icon={<Flame className="w-5 h-5" />}
            label="CC per Contract"
            value={`${totals.cc_burn_per_contract} CC`}
            sublabel={`≈ ${formatUSD(totals.cc_burn_per_contract * totals.cc_to_usd_rate)} value each`}
            accent="amber"
          />
        </section>

        {/* Timeline chart with range selector */}
        <section className="bg-white rounded-2xl border border-neutral-200 p-6">
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-5">
            <div>
              <h2 className="text-base font-semibold text-neutral-900 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-neutral-500" />
                Activity Timeline
              </h2>
              <p className="text-xs text-neutral-500 mt-0.5">
                Signups, generations, and deployments over time
              </p>
            </div>
            <div className="inline-flex items-center p-1 rounded-xl bg-neutral-100 border border-neutral-200 self-start">
              {RANGE_OPTIONS.map((r) => (
                <button
                  key={r.key}
                  onClick={() => {
                    setRange(r.key);
                    setRefreshing(true);
                  }}
                  className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                    range === r.key
                      ? "bg-white text-neutral-900 shadow-sm"
                      : "text-neutral-500 hover:text-neutral-800"
                  }`}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>
          <TimelineChart
            data={timeline}
            bucketSeconds={data.bucket_seconds}
            keys={[
              { key: "users", label: "New Users", color: "#2563eb" },
              { key: "contracts", label: "Deployed Contracts", color: "#16a34a" },
              { key: "jobs", label: "Generations", color: "#f59e0b" },
            ]}
          />
        </section>

        {/* Two columns: templates + env breakdown */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl border border-neutral-200 p-6">
            <h2 className="text-base font-semibold text-neutral-900 mb-1">
              Most Deployed Templates
            </h2>
            <p className="text-xs text-neutral-500 mb-5">
              Top DAML templates by deployment count
            </p>
            <BarChart
              data={top_templates.map((t) => ({
                label: t.template,
                value: t.count,
              }))}
              color="#16a34a"
            />
          </div>

          <div className="bg-white rounded-2xl border border-neutral-200 p-6">
            <h2 className="text-base font-semibold text-neutral-900 mb-1">
              Canton Environment Split
            </h2>
            <p className="text-xs text-neutral-500 mb-5">
              Where contracts are being deployed
            </p>
            <DonutChart
              data={env_breakdown.map((e) => ({
                label: e.env,
                value: e.count,
              }))}
            />
          </div>
        </section>

        {/* Job status + most active users */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl border border-neutral-200 p-6">
            <h2 className="text-base font-semibold text-neutral-900 mb-1">
              Pipeline Status
            </h2>
            <p className="text-xs text-neutral-500 mb-5">
              Live breakdown of completed & in-flight generations
            </p>
            <DonutChart
              data={status_breakdown
                .filter((s) => s.status !== "failed")
                .map((s) => ({
                  label: s.status,
                  value: s.count,
                }))}
            />
          </div>

          <div className="bg-white rounded-2xl border border-neutral-200 p-6">
            <div className="flex items-center gap-2 mb-1">
              <Trophy className="w-4 h-4 text-amber-500" />
              <h2 className="text-base font-semibold text-neutral-900">
                Most Active Users
              </h2>
            </div>
            <p className="text-xs text-neutral-500 mb-5">
              By deployed contracts & successful generations
            </p>

            {most_active_users.length === 0 ? (
              <p className="text-xs text-neutral-400 py-8 text-center">
                No user activity yet.
              </p>
            ) : (
              <div className="space-y-3">
                {most_active_users.map((u, i) => (
                  <div
                    key={u.email}
                    className="flex items-center gap-3 p-3 rounded-xl bg-neutral-50 border border-neutral-100"
                  >
                    <div
                      className={`w-8 h-8 flex-none rounded-full flex items-center justify-center text-xs font-bold ${
                        i === 0
                          ? "bg-amber-100 text-amber-700"
                          : i === 1
                            ? "bg-neutral-200 text-neutral-700"
                            : i === 2
                              ? "bg-orange-100 text-orange-700"
                              : "bg-white border border-neutral-200 text-neutral-500"
                      }`}
                    >
                      {i + 1}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-neutral-900 truncate">
                        {u.display_name || u.email.split("@")[0]}
                      </div>
                      <div className="text-[11px] text-neutral-500 truncate">
                        {u.email}
                      </div>
                    </div>
                    <div className="flex items-center gap-4 flex-none text-right">
                      <div>
                        <div className="text-sm font-semibold text-neutral-900">
                          {u.deploys}
                        </div>
                        <div className="text-[10px] text-neutral-400 uppercase tracking-wide">
                          Deploys
                        </div>
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-neutral-900">
                          {u.contracts}
                        </div>
                        <div className="text-[10px] text-neutral-400 uppercase tracking-wide">
                          Gens
                        </div>
                      </div>
                      {typeof u.xp === "number" && (
                        <div className="hidden sm:block w-16">
                          <div className="text-[11px] text-neutral-600 font-medium">
                            {u.xp} XP
                          </div>
                          <div className="h-1.5 mt-1 bg-neutral-200 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-gradient-to-r from-amber-400 to-amber-600"
                              style={{ width: `${Math.round(((u.xp ?? 0) / maxXp) * 100)}%` }}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </section>

        {/* Footer note */}
        <footer className="text-center text-[11px] text-neutral-400 pt-4">
          CC burn is an estimate based on {totals.cc_burn_per_contract} CC per
          deployment. Adjust via <code>CC_BURN_PER_CONTRACT</code> env var.
        </footer>
      </main>
    </div>
  );
}
