"use client";

import { useAuth } from "@/lib/auth-context";
import { UserCircle2 } from "lucide-react";
import type { ReactNode } from "react";

/**
 * Small chip pinned to the top-right corner OUTSIDE the header notch,
 * showing the user's account username (distinct from the party name shown
 * inside the notch).
 */
export function UsernameBadge(): ReactNode {
  const { isAuthenticated, displayName, email } = useAuth();
  if (!isAuthenticated) return null;
  const label = displayName || (email ? email.split("@")[0] : null);
  if (!label) return null;

  return (
    <div
      className="fixed top-5 right-6 z-[9997] hidden md:flex items-center gap-1.5 rounded-full bg-foreground/5 border border-foreground/10 backdrop-blur px-3 py-1 text-xs font-medium text-foreground/80"
      title={email ? `Signed in as ${email}` : "Signed in"}
    >
      <UserCircle2 className="w-3.5 h-3.5" />
      <span className="truncate max-w-[140px]">{label}</span>
    </div>
  );
}
