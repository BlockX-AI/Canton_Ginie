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
      className={`relative rounded-2xl border p-5 transition-all ${
        earned
          ? "bg-frame border-border hover:border-foreground/20 hover:shadow-lg"
          : "bg-foreground/[0.02] border-foreground/10 opacity-60"
      }`}
      title={earned ? `Earned ${earnedAt}` : "Not yet earned"}
    >
      {!earned && (
        <Lock className="absolute top-3 right-3 w-4 h-4 text-muted-foreground" />
      )}
      <div
        className={`w-14 h-14 rounded-xl flex items-center justify-center mb-3 ring-2 ${rarity.ring}`}
        style={{
          backgroundColor: earned ? `${badge.color}20` : "rgba(120,120,120,0.1)",
        }}
      >
        <Icon
          className="w-7 h-7"
          style={{ color: earned ? badge.color : "#888" }}
        />
      </div>
      <div className="flex items-center gap-2 mb-1">
        <h3 className="text-sm font-semibold text-foreground">{badge.name}</h3>
        <span className={`text-[10px] uppercase tracking-wider font-bold ${rarity.label}`}>
          {badge.rarity}
        </span>
      </div>
      <p className="text-xs text-muted-foreground leading-relaxed mb-2">
        {badge.description}
      </p>
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-accent font-medium">+{badge.xp_reward} XP</span>
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
    <div className="rounded-2xl border border-border bg-frame p-5">
      <div className="flex items-center gap-2 mb-2">
        <Icon className={`w-4 h-4 ${accent || "text-muted-foreground"}`} />
        <span className="text-xs uppercase tracking-wider text-muted-foreground font-medium">
          {label}
        </span>
      </div>
      <div className="text-2xl font-semibold text-foreground">{value}</div>
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
    <div className="min-h-screen pt-28 pb-20 px-4 md:px-8">
      <div className="max-w-6xl mx-auto">
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back
        </Link>

        {/* Profile header card */}
        <div className="rounded-3xl border border-border bg-frame p-6 md:p-8 mb-8">
          <div className="flex flex-col md:flex-row gap-6 items-start md:items-center">
            {/* Avatar */}
            <div className="relative group">
              <div className="w-28 h-28 rounded-full border-4 border-accent/30 overflow-hidden bg-foreground/5 flex items-center justify-center">
                {profile.profile_picture_url ? (
                  <img
                    src={profile.profile_picture_url}
                    alt={profile.display_name || profile.email}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <UserIcon className="w-12 h-12 text-muted-foreground" />
                )}
              </div>
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="absolute bottom-0 right-0 w-9 h-9 rounded-full bg-accent text-background flex items-center justify-center shadow-lg hover:bg-accent/90 transition-colors disabled:opacity-50"
                title="Change picture"
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
            <div className="flex-1 min-w-0">
              <h1 className="text-3xl font-semibold text-foreground mb-1">
                {profile.display_name || profile.email.split("@")[0]}
              </h1>
              <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground mb-4">
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

              {/* Level + XP bar */}
              <div className="max-w-md">
                <div className="flex items-center justify-between mb-1.5 text-xs">
                  <span className="font-semibold text-foreground inline-flex items-center gap-1.5">
                    <Star className="w-3.5 h-3.5 text-accent" />
                    Level {profile.level}
                  </span>
                  <span className="text-muted-foreground">
                    {progressInLevel} / {xpNeeded} XP
                  </span>
                </div>
                <div className="h-2 rounded-full bg-foreground/10 overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-accent to-accent/70 transition-all duration-500"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          {error && (
            <div className="mt-4 text-sm text-red-500">{error}</div>
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
