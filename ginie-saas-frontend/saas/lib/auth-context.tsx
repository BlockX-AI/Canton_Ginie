"use client";

/**
 * Authentication context for Ginie — holds JWT, party info, and auth actions.
 *
 * Wraps the app to provide isAuthenticated, partyId, login/logout/refresh.
 * JWT is stored in memory (not localStorage) for security; the key file
 * is the persistent backup.
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface AuthState {
  isAuthenticated: boolean;
  token: string | null;
  partyId: string | null;
  displayName: string | null;
  partyName: string | null;
  fingerprint: string | null;
  email: string | null;
  profilePictureUrl: string | null;
  needsParty: boolean;
}

interface EmailAuthResult {
  needsParty: boolean;
  partyId: string | null;
}

interface AuthContextValue extends AuthState {
  hydrated: boolean;
  login: (token: string, partyId: string, displayName: string, fingerprint: string) => void;
  loginEmail: (email: string, password: string) => Promise<EmailAuthResult>;
  signupEmail: (email: string, password: string, displayName?: string, inviteCode?: string) => Promise<EmailAuthResult>;
  sendOTP: (email: string, displayName?: string) => Promise<void>;
  verifyOTP: (email: string, otp: string) => Promise<void>;
  uploadProfilePictureSignup: (email: string, file: Blob) => Promise<string>;
  linkParty: (partyId: string, displayName: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
  setProfilePictureUrl: (url: string | null) => void;
}

const defaultState: AuthState = {
  isAuthenticated: false,
  token: null,
  partyId: null,
  displayName: null,
  partyName: null,
  fingerprint: null,
  email: null,
  profilePictureUrl: null,
  needsParty: false,
};

const STORAGE_KEY = "ginie_auth";

function saveToStorage(s: AuthState) {
  try {
    if (typeof window !== "undefined") {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(s));
    }
  } catch { /* ignore */ }
}

function loadFromStorage(): AuthState {
  try {
    if (typeof window !== "undefined") {
      const raw = sessionStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw) as AuthState;
    }
  } catch { /* ignore */ }
  return defaultState;
}

function clearStorage() {
  try {
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  } catch { /* ignore */ }
}

const AuthContext = createContext<AuthContextValue>({
  ...defaultState,
  hydrated: false,
  login: () => {},
  loginEmail: async () => ({ needsParty: false, partyId: null }),
  signupEmail: async () => ({ needsParty: true, partyId: null }),
  sendOTP: async () => {},
  verifyOTP: async () => {},
  uploadProfilePictureSignup: async () => "",
  linkParty: async () => {},
  logout: async () => {},
  refreshToken: async () => {},
  setProfilePictureUrl: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(defaultState);
  const [hydrated, setHydrated] = useState(false);

  // Restore from sessionStorage on mount
  useEffect(() => {
    const stored = loadFromStorage();
    if (stored.isAuthenticated) {
      setState(stored);
    }
    setHydrated(true);
  }, []);

  const login = useCallback(
    (token: string, partyId: string, displayName: string, fingerprint: string) => {
      // Ed25519-only login — no email account, party name == displayName.
      const next: AuthState = {
        isAuthenticated: true,
        token,
        partyId,
        displayName,
        partyName: displayName,
        fingerprint,
        email: null,
        profilePictureUrl: null,
        needsParty: false,
      };
      setState(next);
      saveToStorage(next);
    },
    [],
  );

  const applyEmailResult = useCallback((data: {
    token: string;
    email: string;
    display_name: string | null;
    party_name?: string | null;
    party_id: string | null;
    profile_picture_url?: string | null;
    needs_party: boolean;
  }): EmailAuthResult => {
    const next: AuthState = {
      isAuthenticated: true,
      token: data.token,
      partyId: data.party_id,
      displayName: data.display_name || data.email.split("@")[0] || "Account",
      partyName: data.party_name ?? null,
      fingerprint: `email:${data.email}`,
      email: data.email,
      profilePictureUrl: data.profile_picture_url ?? null,
      needsParty: data.needs_party,
    };
    setState(next);
    saveToStorage(next);
    return { needsParty: data.needs_party, partyId: data.party_id };
  }, []);

  const sendOTP = useCallback(
    async (email: string, displayName?: string): Promise<void> => {
      const resp = await fetch(`${API_URL}/auth/email/send-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, display_name: displayName }),
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail?.detail || "Failed to send verification code");
      }
    },
    [],
  );

  const verifyOTP = useCallback(
    async (email: string, otp: string): Promise<void> => {
      const resp = await fetch(`${API_URL}/auth/email/verify-otp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, otp }),
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail?.detail || "Invalid verification code");
      }
    },
    [],
  );

  const uploadProfilePictureSignup = useCallback(
    async (email: string, file: Blob): Promise<string> => {
      const formData = new FormData();
      formData.append("email", email);
      formData.append("file", file, "profile.jpg");
      const resp = await fetch(`${API_URL}/profile/upload-picture-signup`, {
        method: "POST",
        body: formData,
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail?.detail || "Failed to upload picture");
      }
      const data = await resp.json();
      return data.profile_picture_url as string;
    },
    [],
  );

  const setProfilePictureUrl = useCallback((url: string | null) => {
    setState((prev) => {
      const next = { ...prev, profilePictureUrl: url };
      if (next.isAuthenticated) saveToStorage(next);
      return next;
    });
  }, []);

  const signupEmail = useCallback(
    async (email: string, password: string, displayName?: string, inviteCode?: string): Promise<EmailAuthResult> => {
      const resp = await fetch(`${API_URL}/auth/email/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          display_name: displayName,
          invite_code: inviteCode,
        }),
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail?.detail || `Signup failed (HTTP ${resp.status})`);
      }
      const data = await resp.json();
      return applyEmailResult(data);
    },
    [applyEmailResult],
  );

  const loginEmail = useCallback(
    async (email: string, password: string): Promise<EmailAuthResult> => {
      const resp = await fetch(`${API_URL}/auth/email/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail?.detail || "Invalid email or password");
      }
      const data = await resp.json();
      return applyEmailResult(data);
    },
    [applyEmailResult],
  );

  const linkParty = useCallback(
    async (partyId: string, displayName: string) => {
      if (!state.token) throw new Error("Not authenticated");
      const resp = await fetch(`${API_URL}/auth/email/link-party`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${state.token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ party_id: partyId, display_name: displayName }),
      });
      if (!resp.ok) {
        const detail = await resp.json().catch(() => ({}));
        throw new Error(detail?.detail || "Failed to link party");
      }
      const data = await resp.json();
      applyEmailResult(data);
    },
    [state.token, applyEmailResult],
  );

  const logout = useCallback(async () => {
    if (state.token) {
      try {
        await fetch(`${API_URL}/auth/logout`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${state.token}`,
            "Content-Type": "application/json",
          },
        });
      } catch {
        // Ignore logout API errors — still clear local state
      }
    }
    setState(defaultState);
    clearStorage();
  }, [state.token]);

  const refreshToken = useCallback(async () => {
    if (!state.token) return;
    try {
      const resp = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${state.token}`,
          "Content-Type": "application/json",
        },
      });
      if (resp.ok) {
        const data = await resp.json();
        setState((prev) => ({ ...prev, token: data.token }));
      } else {
        // Token expired or invalid — force logout
        setState(defaultState);
      }
    } catch {
      // Network error — keep current state, retry later
    }
  }, [state.token]);

  // Auto-refresh token every 6 hours
  useEffect(() => {
    if (!state.isAuthenticated) return;
    const interval = setInterval(
      () => {
        refreshToken();
      },
      6 * 60 * 60 * 1000,
    );
    return () => clearInterval(interval);
  }, [state.isAuthenticated, refreshToken]);

  return (
    <AuthContext.Provider
      value={{
        ...state,
        hydrated,
        login,
        loginEmail,
        signupEmail,
        sendOTP,
        verifyOTP,
        uploadProfilePictureSignup,
        linkParty,
        logout,
        refreshToken,
        setProfilePictureUrl,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
