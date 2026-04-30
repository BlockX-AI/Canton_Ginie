"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Loader2,
  Trophy,
  Zap,
  FileText,
  Upload,
  Award,
  ArrowLeft,
  User as UserIcon,
  Crown,
  Medal,
  Sparkles,
  Building2,
  Rocket,
  Gem,
  Sprout,
  Shield,
  Star,
  Target,
  Search,
  Code2,
  Flame,
} from "lucide-react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface BadgeMini {
  slug: string;
  name: string;
  icon: string;
  color: string;
  rarity: string;
}

interface LeaderboardUser {
  display_name: string;
  profile_picture_url: string | null;
  xp: number;
  level: number;
  badge_count: number;
  contract_count: number;
  deploy_count: number;
  rank_tier: string;
  recent_badges: BadgeMini[];
  member_since: string | null;
}

const ICON_MAP: Record<
  string,
  React.ComponentType<{ className?: string; style?: React.CSSProperties }>
> = {
  Sprout,
  Sparkles,
  Zap,
  Building2,
  Rocket,
  Gem,
  Trophy,
  Upload,
  Shield,
  Award,
  Star,
  Code2,
  Target,
  Crown,
};

const TIER_STYLES: Record<string, { bg: string; border: string; text: string }> = {
  ARCHITECT: {
    bg: "bg-amber-500/15",
    border: "border-amber-500/40",
    text: "text-amber-400",
  },
  BUILDER: {
    bg: "bg-purple-500/15",
    border: "border-purple-500/40",
    text: "text-purple-400",
  },
  SIGNER: {
    bg: "bg-cyan-500/15",
    border: "border-cyan-500/40",
    text: "text-cyan-400",
  },
  NEWCOMER: {
    bg: "bg-foreground/5",
    border: "border-foreground/15",
    text: "text-muted-foreground",
  },
};

type Tab = "trust" | "xp" | "deploy" | "contracts";

function RankIndicator({ rank }: { rank: number }) {
  if (rank === 1)
    return (
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-amber-300 to-amber-600 flex items-center justify-center shadow-lg shadow-amber-500/30">
        <Crown className="w-5 h-5 text-white" />
      </div>
    );
  if (rank === 2)
    return (
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-slate-300 to-slate-500 flex items-center justify-center shadow-lg shadow-slate-400/20">
        <Medal className="w-5 h-5 text-white" />
      </div>
    );
  if (rank === 3)
    return (
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-400 to-amber-700 flex items-center justify-center shadow-lg shadow-orange-500/20">
        <Medal className="w-5 h-5 text-white" />
      </div>
    );
  return (
    <div className="w-10 h-10 rounded-full bg-foreground/5 border border-border flex items-center justify-center text-sm font-mono font-semibold text-muted-foreground">
      {rank}
    </div>
  );
}

function MiniBadge({ badge }: { badge: BadgeMini }) {
  const Icon = ICON_MAP[badge.icon] || Award;
  return (
    <div
      className="w-8 h-8 rounded-lg flex items-center justify-center ring-1 ring-foreground/10"
      style={{
        background: `linear-gradient(135deg, ${badge.color}30, ${badge.color}10)`,
        boxShadow: `0 0 12px ${badge.color}25`,
      }}
      title={`${badge.name} (${badge.rarity})`}
    >
      <Icon className="w-4 h-4" style={{ color: badge.color }} />
    </div>
  );
}

export default function LeaderboardPage() {
  const [users, setUsers] = useState<LeaderboardUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("trust");
  const [search, setSearch] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        const resp = await fetch(`${API_URL}/profile/leaderboard?limit=200`);
        if (!resp.ok) throw new Error("Failed to load leaderboard");
        const data = await resp.json();
        setUsers(data.users || []);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const sortedUsers = useMemo(() => {
    const sorted = [...users];
    if (tab === "xp") sorted.sort((a, b) => b.xp - a.xp);
    else if (tab === "deploy")
      sorted.sort((a, b) => b.deploy_count - a.deploy_count);
    else if (tab === "contracts")
      sorted.sort((a, b) => b.contract_count - a.contract_count);
    // "trust" leaves the default backend order (xp + tie-breakers)
    return sorted;
  }, [users, tab]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return sortedUsers;
    return sortedUsers.filter((u) =>
      u.display_name.toLowerCase().includes(q),
    );
  }, [sortedUsers, search]);

  const tabs: { key: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
    { key: "trust", label: "Trust Tier", icon: Shield },
    { key: "xp", label: "XP", icon: Zap },
    { key: "deploy", label: "Deployments", icon: Upload },
    { key: "contracts", label: "Contracts", icon: FileText },
  ];

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="min-h-screen pt-28 pb-20 px-4 md:px-8 relative overflow-hidden">
      {/* Decorative glows */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[400px] bg-accent/5 blur-3xl rounded-full pointer-events-none" />
      <div className="absolute top-60 right-10 w-[400px] h-[400px] bg-amber-500/5 blur-3xl rounded-full pointer-events-none" />

      <div className="max-w-6xl mx-auto relative">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to home
        </Link>

        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-2 mb-2 px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/20 text-xs font-semibold text-amber-400">
              <Flame className="w-3.5 h-3.5" />
              LIVE
            </div>
            <h1 className="text-4xl md:text-5xl font-semibold tracking-tight text-foreground mb-1">
              Leaderboard
            </h1>
            <p className="text-muted-foreground text-sm">
              Top builders on the Canton Network — ranked by XP, deployments, and contracts.
            </p>
          </div>

          {/* Search */}
          <div className="relative w-full md:w-72">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search users..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 rounded-full bg-frame border border-border text-sm focus:outline-none focus:border-foreground/30 transition-colors"
            />
          </div>
        </div>

        {/* Tab pills */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-1 scrollbar-hide">
          {tabs.map((t) => {
            const Icon = t.icon;
            const active = tab === t.key;
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium border transition-all whitespace-nowrap ${
                  active
                    ? "bg-accent text-background border-accent shadow-md"
                    : "bg-frame border-border text-muted-foreground hover:text-foreground hover:border-foreground/20"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {t.label}
              </button>
            );
          })}
        </div>

        {error && (
          <div className="mb-6 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-500">
            {error}
          </div>
        )}

        {/* Leaderboard table */}
        <div className="rounded-3xl border border-border bg-gradient-to-br from-frame to-frame/60 overflow-hidden shadow-xl">
          {/* Header row */}
          <div className="grid grid-cols-[60px_1fr_auto_auto_auto] md:grid-cols-[60px_1fr_120px_120px_220px] gap-4 px-5 py-3 border-b border-border text-[10px] uppercase tracking-wider text-muted-foreground font-semibold bg-foreground/[0.02]">
            <div>#</div>
            <div>User</div>
            <div className="text-right">
              {tab === "xp" ? "XP" : tab === "deploy" ? "Deploys" : tab === "contracts" ? "Contracts" : "Trust"}
            </div>
            <div className="text-center hidden md:block">Level</div>
            <div className="text-right">Badges</div>
          </div>

          {filtered.length === 0 ? (
            <div className="p-12 text-center">
              <Trophy className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                {search ? "No users match your search." : "No users yet — be the first to climb the ranks!"}
              </p>
            </div>
          ) : (
            <div>
              {filtered.map((user, idx) => {
                const rank = idx + 1;
                const tier = TIER_STYLES[user.rank_tier] ?? TIER_STYLES.NEWCOMER!;
                const primaryStat =
                  tab === "xp"
                    ? user.xp
                    : tab === "deploy"
                      ? user.deploy_count
                      : tab === "contracts"
                        ? user.contract_count
                        : user.xp;
                const isTop3 = rank <= 3;

                return (
                  <div
                    key={`${user.display_name}-${idx}`}
                    className={`grid grid-cols-[60px_1fr_auto_auto_auto] md:grid-cols-[60px_1fr_120px_120px_220px] gap-4 px-5 py-4 items-center border-b border-border/40 last:border-b-0 transition-colors hover:bg-foreground/[0.02] ${
                      isTop3 ? "bg-gradient-to-r from-foreground/[0.02] to-transparent" : ""
                    }`}
                  >
                    {/* Rank */}
                    <div className="flex items-center justify-center">
                      <RankIndicator rank={rank} />
                    </div>

                    {/* User */}
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="relative flex-shrink-0">
                        <div className="w-11 h-11 rounded-full overflow-hidden bg-foreground/5 border border-border flex items-center justify-center">
                          {user.profile_picture_url ? (
                            <img
                              src={user.profile_picture_url}
                              alt={user.display_name}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <UserIcon className="w-5 h-5 text-muted-foreground" />
                          )}
                        </div>
                      </div>
                      <div className="min-w-0">
                        <div className="text-sm font-semibold text-foreground truncate">
                          {user.display_name}
                        </div>
                        <span
                          className={`inline-flex items-center gap-1 mt-0.5 px-2 py-0.5 rounded-full text-[9px] uppercase tracking-wider font-bold border ${tier.bg} ${tier.border} ${tier.text}`}
                        >
                          {user.rank_tier}
                        </span>
                      </div>
                    </div>

                    {/* Primary stat (depends on tab) */}
                    <div className="text-right">
                      <span className="inline-flex items-center justify-center min-w-[3.5rem] px-3 py-1 rounded-full bg-foreground/5 border border-border text-sm font-mono font-semibold text-foreground">
                        {primaryStat}
                      </span>
                    </div>

                    {/* Level */}
                    <div className="hidden md:flex items-center justify-center">
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-accent/10 border border-accent/20 text-xs font-mono font-bold text-accent">
                        Lv {user.level}
                      </span>
                    </div>

                    {/* Badges */}
                    <div className="flex items-center justify-end gap-1.5">
                      {user.recent_badges.length === 0 ? (
                        <span className="text-xs text-muted-foreground/60">—</span>
                      ) : (
                        <>
                          {user.recent_badges.slice(0, 3).map((b) => (
                            <MiniBadge key={b.slug} badge={b} />
                          ))}
                          {user.badge_count > 3 && (
                            <span className="text-[11px] text-muted-foreground font-mono ml-1">
                              +{user.badge_count - 3}
                            </span>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <p className="text-center text-xs text-muted-foreground mt-6">
          Updated in real-time. {users.length} {users.length === 1 ? "builder" : "builders"} on the network.
        </p>
      </div>
    </div>
  );
}
