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
  fingerprint: string | null;
}

interface AuthContextValue extends AuthState {
  login: (token: string, partyId: string, displayName: string, fingerprint: string) => void;
  logout: () => Promise<void>;
  refreshToken: () => Promise<void>;
}

const defaultState: AuthState = {
  isAuthenticated: false,
  token: null,
  partyId: null,
  displayName: null,
  fingerprint: null,
};

const AuthContext = createContext<AuthContextValue>({
  ...defaultState,
  login: () => {},
  logout: async () => {},
  refreshToken: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(defaultState);

  const login = useCallback(
    (token: string, partyId: string, displayName: string, fingerprint: string) => {
      setState({
        isAuthenticated: true,
        token,
        partyId,
        displayName,
        fingerprint,
      });
    },
    [],
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
    <AuthContext.Provider value={{ ...state, login, logout, refreshToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
