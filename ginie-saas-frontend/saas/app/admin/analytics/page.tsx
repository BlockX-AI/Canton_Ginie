"use client";

import {
  Activity,
  CheckCircle2,
  Flame,
  Layers,
  Loader2,
  LogOut,
  RefreshCw,
  Shield,
  TrendingUp,
  Trophy,
  Users,
  XCircle,
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
  failed_jobs: number;
  success_rate: number;
  invite_codes_total: number;
  invite_codes_used: number;
  estimated_cc_burn: number;
  cc_burn_per_contract: number;
}

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

function formatDate(iso: string): string {
  const d = new Date(iso + "T00:00:00Z");
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
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
}: {
  data: TimelinePoint[];
  keys: { key: keyof TimelinePoint; label: string; color: string }[];
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

  // X tick labels — show every ~5th
  const xTickIdx = data.map((_, i) => i).filter((i) => i % 5 === 0 || i === data.length - 1);

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
              {formatDate(point.date)}
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
            {formatDate(data[hover]!.date)}
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

  const fetchAnalytics = useCallback(async () => {
    const pwd =
      typeof window !== "undefined"
        ? sessionStorage.getItem("ginie_admin_password")
        : null;
    if (!pwd) {
      router.replace("/admin");
      return;
    }
    try {
      const resp = await fetch(`${API_URL}/admin/analytics`, {
        headers: { "X-Admin-Password": pwd },
      });
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
  }, [router]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchAnalytics();
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
      <header className="sticky top-0 z-10 bg-white/80 backdrop-blur border-b border-neutral-200">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-neutral-900 flex items-center justify-center">
              <Shield className="w-4 h-4 text-accent" />
            </div>
            <div>
              <h1 className="text-lg font-semibold text-neutral-900 leading-tight">
                Ginie Admin Analytics
              </h1>
              <p className="text-[11px] text-neutral-500">
                Generated {new Date(data.generated_at).toLocaleString()}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-neutral-700 bg-white border border-neutral-200 hover:bg-neutral-50 disabled:opacity-50"
            >
              <RefreshCw
                className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`}
              />
              Refresh
            </button>
            <button
              onClick={handleLogout}
              className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-neutral-700 bg-white border border-neutral-200 hover:bg-neutral-50"
            >
              <LogOut className="w-3.5 h-3.5" />
              Log out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-6 pt-8 space-y-6">
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
            icon={<Flame className="w-5 h-5" />}
            label="Estimated CC Burn"
            value={`${formatNumber(totals.estimated_cc_burn)} CC`}
            sublabel={`~${totals.cc_burn_per_contract} CC per contract`}
            accent="amber"
          />
        </section>

        {/* Secondary stats */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <StatCard
            icon={<Zap className="w-5 h-5" />}
            label="Total Generations"
            value={totals.total_jobs}
            sublabel={`${totals.successful_jobs} successful`}
            accent="neutral"
          />
          <StatCard
            icon={<CheckCircle2 className="w-5 h-5" />}
            label="Successful Jobs"
            value={totals.successful_jobs}
            accent="green"
          />
          <StatCard
            icon={<XCircle className="w-5 h-5" />}
            label="Failed Jobs"
            value={totals.failed_jobs}
            accent="red"
          />
          <StatCard
            icon={<Activity className="w-5 h-5" />}
            label="Invite Codes Used"
            value={`${totals.invite_codes_used}/${totals.invite_codes_total}`}
            sublabel={`${totals.invite_codes_total - totals.invite_codes_used} remaining`}
            accent="neutral"
          />
        </section>

        {/* Timeline chart */}
        <section className="bg-white rounded-2xl border border-neutral-200 p-6">
          <div className="flex items-center justify-between mb-5">
            <div>
              <h2 className="text-base font-semibold text-neutral-900 flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-neutral-500" />
                30-Day Activity Timeline
              </h2>
              <p className="text-xs text-neutral-500 mt-0.5">
                Daily signups, generations, and deployments
              </p>
            </div>
          </div>
          <TimelineChart
            data={timeline}
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
              Job Status Distribution
            </h2>
            <p className="text-xs text-neutral-500 mb-5">
              Breakdown of every generation attempt
            </p>
            <DonutChart
              data={status_breakdown.map((s) => ({
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
