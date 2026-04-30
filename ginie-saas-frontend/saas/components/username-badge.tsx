"use client";

import { useAuth } from "@/lib/auth-context";
import { UserCircle2 } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

/**
 * Small chip pinned to the top-right corner OUTSIDE the header notch,
 * showing the user's profile picture + display name. Clicking it
 * navigates to the profile page.
 */
export function UsernameBadge(): ReactNode {
  const { isAuthenticated, displayName, email, profilePictureUrl } = useAuth();
  if (!isAuthenticated) return null;
  const label = displayName || (email ? email.split("@")[0] : null);
  if (!label) return null;

  return (
    <Link
      href="/profile"
      className="fixed top-5 right-6 z-[9997] hidden md:flex items-center gap-2 rounded-full bg-foreground/5 border border-foreground/10 backdrop-blur pl-1 pr-3 py-1 text-xs font-medium text-foreground/80 hover:bg-foreground/10 hover:border-foreground/20 transition-colors"
      title={email ? `Signed in as ${email} — view profile` : "View profile"}
    >
      {profilePictureUrl ? (
        <img
          src={profilePictureUrl}
          alt={label}
          className="w-6 h-6 rounded-full object-cover border border-foreground/10"
        />
      ) : (
        <UserCircle2 className="w-5 h-5" />
      )}
      <span className="truncate max-w-[140px]">{label}</span>
    </Link>
  );
}
