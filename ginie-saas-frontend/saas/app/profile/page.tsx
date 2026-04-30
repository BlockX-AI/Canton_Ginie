"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import {
  Loader2,
  Camera,
  Award,
  Zap,
  FileText,
  Upload,
  Sparkles,
  Trophy,
  Lock,
  Calendar,
  Mail,
  User as UserIcon,
  ArrowLeft,
  Sprout,
  Building2,
  Rocket,
  Gem,
  Star,
  Shield,
  Code2,
} from "lucide-react";
import { useAuth } from "@/lib/auth-context";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface Badge {
  slug: string;
  name: string;
  description: string;
  icon: string;
  color: string;
  category: string;
  criteria_type?: string;
  criteria_value?: number;
  rarity: string;
  xp_reward: number;
  earned_at?: string | null;
}

interface ProfileData {
  email: string;
  display_name: string | null;
  profile_picture_url: string | null;
  xp: number;
  level: number;
  badge_count: number;
  contract_count: number;
  deploy_count: number;
  member_since: string | null;
  badges: Badge[];
}

// Map icon string from backend to lucide component
const ICON_MAP: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
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
};

const RARITY_STYLES: Record<string, { ring: string; label: string }> = {
  common: { ring: "ring-slate-400/30", label: "text-slate-400" },
  rare: { ring: "ring-cyan-400/40", label: "text-cyan-400" },
  epic: { ring: "ring-purple-400/40", label: "text-purple-400" },
  legendary: { ring: "ring-amber-400/50", label: "text-amber-400" },
};

function BadgeCard({ badge, earned }: { badge: Badge; earned: boolean }) {
  const Icon = ICON_MAP[badge.icon] || Award;
  const rarity = RARITY_STYLES[badge.rarity] ?? RARITY_STYLES.common!;
  const earnedAt = badge.earned_at ? new Date(badge.earned_at).toLocaleDateString() : null;

  return (
    <div
      className={`group relative rounded-2xl border p-5 transition-all duration-300 overflow-hidden ${
        earned
          ? "bg-gradient-to-br from-frame to-frame/50 border-border hover:-translate-y-1 hover:shadow-2xl hover:border-foreground/20"
          : "bg-foreground/[0.02] border-foreground/10 opacity-50 hover:opacity-70"
      }`}
      title={earned ? `Earned ${earnedAt}` : "Not yet earned"}
    >
      {/* Glow effect on hover for earned badges */}
      {earned && (
        <div
          className="absolute inset-0 opacity-0 group-hover:opacity-30 transition-opacity duration-300 pointer-events-none"
          style={{
            background: `radial-gradient(circle at 50% 0%, ${badge.color}60 0%, transparent 70%)`,
          }}
        />
      )}
      {!earned && (
        <div className="absolute top-3 right-3 w-7 h-7 rounded-full bg-foreground/5 flex items-center justify-center">
          <Lock className="w-3.5 h-3.5 text-muted-foreground" />
        </div>
      )}
      <div
        className={`relative w-16 h-16 rounded-2xl flex items-center justify-center mb-4 ring-2 ${rarity.ring} ${
          earned ? "shadow-lg" : ""
        }`}
        style={{
          background: earned
            ? `linear-gradient(135deg, ${badge.color}30, ${badge.color}10)`
            : "rgba(120,120,120,0.08)",
          boxShadow: earned ? `0 0 24px ${badge.color}30` : undefined,
        }}
      >
        <Icon
          className="w-8 h-8"
          style={{ color: earned ? badge.color : "#666" }}
        />
      </div>
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        <h3 className="text-sm font-semibold text-foreground">{badge.name}</h3>
        <span
          className={`text-[9px] uppercase tracking-wider font-bold px-2 py-0.5 rounded-full border border-current/30 ${rarity.label}`}
        >
          {badge.rarity}
        </span>
      </div>
      <p className="text-xs text-muted-foreground leading-relaxed mb-3 min-h-[2.5em]">
        {badge.description}
      </p>
      <div className="flex items-center justify-between text-[11px] pt-3 border-t border-border/50">
        <span className="inline-flex items-center gap-1 text-accent font-semibold">
          <Zap className="w-3 h-3" />
          {badge.xp_reward} XP
        </span>
        {earned && earnedAt && (
          <span className="text-muted-foreground">{earnedAt}</span>
        )}
      </div>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  accent,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  accent?: string;
}) {
  return (
    <div className="group relative rounded-2xl border border-border bg-gradient-to-br from-frame to-frame/60 p-5 hover:border-foreground/20 hover:-translate-y-0.5 transition-all duration-300 overflow-hidden">
      <div className="absolute -top-6 -right-6 w-24 h-24 bg-foreground/[0.02] rounded-full group-hover:bg-foreground/[0.04] transition-colors" />
      <div className="relative flex items-center gap-2 mb-3">
        <div className={`w-8 h-8 rounded-lg flex items-center justify-center bg-foreground/5 ${accent || "text-muted-foreground"}`}>
          <Icon className="w-4 h-4" />
        </div>
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold">
          {label}
        </span>
      </div>
      <div className="relative text-3xl font-semibold text-foreground tracking-tight">
        {value}
      </div>
    </div>
  );
}

export default function ProfilePage() {
  const { isAuthenticated, hydrated, token, setProfilePictureUrl } = useAuth();
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [allBadges, setAllBadges] = useState<Badge[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated || !token) {
      setLoading(false);
      return;
    }

    const load = async () => {
      try {
        const [profileRes, badgesRes] = await Promise.all([
          fetch(`${API_URL}/profile/me`, {
            headers: { Authorization: `Bearer ${token}` },
          }),
          fetch(`${API_URL}/badges`),
        ]);

        if (!profileRes.ok) throw new Error("Failed to load profile");
        const profileData = await profileRes.json();
        setProfile(profileData);

        if (badgesRes.ok) {
          const data = await badgesRes.json();
          setAllBadges(data.badges || []);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load profile");
      } finally {
        setLoading(false);
      }
    };

    load();
  }, [isAuthenticated, hydrated, token]);

  const handlePictureUpload = async (file: File) => {
    if (!token) return;
    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const resp = await fetch(`${API_URL}/profile/upload-picture`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });

      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new Error(data.detail || "Failed to upload picture");
      }

      const data = await resp.json();
      setProfile((prev) =>
        prev ? { ...prev, profile_picture_url: data.profile_picture_url } : prev,
      );
      setProfilePictureUrl(data.profile_picture_url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  if (!hydrated || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center pt-32">
        <div className="text-center max-w-md px-6">
          <UserIcon className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
          <h1 className="text-2xl font-semibold mb-2">Sign in to view your profile</h1>
          <p className="text-muted-foreground mb-6">
            Track your badges, XP, and contract history.
          </p>
          <Link
            href="/login"
            className="inline-flex items-center gap-2 rounded-full bg-accent px-5 py-2.5 text-sm font-semibold text-background hover:bg-accent/90 transition-colors"
          >
            Sign in
          </Link>
        </div>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="min-h-screen flex items-center justify-center px-6">
        <div className="text-center">
          <p className="text-red-500 mb-4">{error}</p>
          <Link href="/" className="text-accent hover:underline">
            Back to home
          </Link>
        </div>
      </div>
    );
  }

  if (!profile) return null;

  const earnedSlugs = new Set(profile.badges.map((b) => b.slug));
  const earnedBadges = profile.badges;
  const lockedBadges = allBadges.filter((b) => !earnedSlugs.has(b.slug));
  const memberSince = profile.member_since
    ? new Date(profile.member_since).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      })
    : null;

  // XP progress to next level
  const currentLevelXp = Math.pow(profile.level - 1, 2) * 50;
  const nextLevelXp = Math.pow(profile.level, 2) * 50;
  const progressInLevel = profile.xp - currentLevelXp;
  const xpNeeded = nextLevelXp - currentLevelXp;
  const progressPercent = Math.min(100, (progressInLevel / xpNeeded) * 100);

  return (
    <div className="min-h-screen pt-28 pb-20 px-4 md:px-8 relative overflow-hidden">
      {/* Decorative background glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-accent/5 blur-3xl rounded-full pointer-events-none" />
      <div className="absolute top-40 right-0 w-[400px] h-[400px] bg-purple-500/5 blur-3xl rounded-full pointer-events-none" />

      <div className="max-w-6xl mx-auto relative">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-8 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to home
        </Link>

        {/* Profile header card */}
        <div className="relative rounded-3xl border border-border bg-gradient-to-br from-frame via-frame to-frame/80 p-8 md:p-10 mb-10 overflow-hidden shadow-xl">
          {/* Subtle pattern overlay */}
          <div
            className="absolute inset-0 opacity-[0.03] pointer-events-none"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)",
              backgroundSize: "24px 24px",
            }}
          />

          <div className="relative flex flex-col md:flex-row gap-8 items-start md:items-center">
            {/* Avatar with gradient ring */}
            <div className="relative group flex-shrink-0">
              <div className="absolute -inset-1 rounded-full bg-gradient-to-tr from-accent via-purple-500 to-cyan-500 opacity-60 blur-md group-hover:opacity-100 transition-opacity" />
              <div className="relative w-32 h-32 rounded-full border-4 border-background overflow-hidden bg-foreground/5 flex items-center justify-center shadow-2xl">
                {profile.profile_picture_url ? (
                  <img
                    src={profile.profile_picture_url}
                    alt={profile.display_name || profile.email}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <UserIcon className="w-14 h-14 text-muted-foreground" />
                )}
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="absolute bottom-1 right-1 w-10 h-10 rounded-full bg-accent text-background flex items-center justify-center shadow-xl hover:bg-accent/90 hover:scale-110 transition-all disabled:opacity-50 ring-4 ring-background"
                title="Change picture"
                aria-label="Change profile picture"
              >
                {uploading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Camera className="w-4 h-4" />
                )}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handlePictureUpload(file);
                }}
              />
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0 w-full">
              <div className="flex items-center gap-3 mb-2 flex-wrap">
                <h1 className="text-4xl font-semibold text-foreground tracking-tight">
                  {profile.display_name || profile.email.split("@")[0]}
                </h1>
                <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-accent/15 border border-accent/30 text-xs font-bold text-accent">
                  <Star className="w-3 h-3 fill-current" />
                  LVL {profile.level}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-sm text-muted-foreground mb-5">
                <span className="inline-flex items-center gap-1.5">
                  <Mail className="w-3.5 h-3.5" />
                  {profile.email}
                </span>
                {memberSince && (
                  <span className="inline-flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5" />
                    Joined {memberSince}
                  </span>
                )}
              </div>

              {/* XP bar */}
              <div className="max-w-lg">
                <div className="flex items-center justify-between mb-2 text-xs">
                  <span className="font-medium text-foreground/80 inline-flex items-center gap-1.5">
                    <Zap className="w-3.5 h-3.5 text-accent" />
                    Progress to Level {profile.level + 1}
                  </span>
                  <span className="text-muted-foreground font-mono">
                    {progressInLevel} / {xpNeeded} XP
                  </span>
                </div>
                <div className="h-2.5 rounded-full bg-foreground/10 overflow-hidden relative">
                  <div
                    className="h-full bg-gradient-to-r from-accent via-accent to-cyan-400 transition-all duration-700 relative"
                    style={{ width: `${progressPercent}%` }}
                  >
                    <div className="absolute inset-0 bg-white/20 animate-pulse" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {error && (
            <div className="relative mt-6 text-sm text-red-500 px-4 py-2 rounded-lg bg-red-500/10 border border-red-500/20">
              {error}
            </div>
          )}
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-10">
          <StatCard
            icon={Zap}
            label="Total XP"
            value={profile.xp}
            accent="text-accent"
          />
          <StatCard
            icon={Award}
            label="Badges"
            value={`${profile.badge_count} / ${allBadges.length || profile.badge_count}`}
            accent="text-amber-500"
          />
          <StatCard
            icon={FileText}
            label="Contracts"
            value={profile.contract_count}
            accent="text-cyan-500"
          />
          <StatCard
            icon={Upload}
            label="Deployments"
            value={profile.deploy_count}
            accent="text-purple-500"
          />
        </div>

        {/* Earned badges */}
        <section className="mb-12">
          <div className="flex items-center gap-2 mb-5">
            <Trophy className="w-5 h-5 text-accent" />
            <h2 className="text-xl font-semibold text-foreground">
              Earned Badges
            </h2>
            <span className="text-sm text-muted-foreground ml-1">
              ({earnedBadges.length})
            </span>
          </div>
          {earnedBadges.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border p-8 text-center">
              <Award className="w-8 h-8 text-muted-foreground mx-auto mb-2" />
              <p className="text-sm text-muted-foreground">
                No badges earned yet. Generate your first contract to start earning!
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {earnedBadges.map((badge) => (
                <BadgeCard key={badge.slug} badge={badge} earned />
              ))}
            </div>
          )}
        </section>

        {/* Locked badges */}
        {lockedBadges.length > 0 && (
          <section>
            <div className="flex items-center gap-2 mb-5">
              <Lock className="w-5 h-5 text-muted-foreground" />
              <h2 className="text-xl font-semibold text-foreground">
                Locked Badges
              </h2>
              <span className="text-sm text-muted-foreground ml-1">
                ({lockedBadges.length})
              </span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {lockedBadges.map((badge) => (
                <BadgeCard key={badge.slug} badge={badge} earned={false} />
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
