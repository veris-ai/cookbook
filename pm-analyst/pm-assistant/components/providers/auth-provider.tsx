"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import {
  getToken,
  setToken,
  clearToken,
  checkAuthStatus,
  getLoginUrl,
} from "@/lib/auth";

interface AuthContextValue {
  isAuthenticated: boolean;
  token: string | null;
  isLoading: boolean;
  login: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlToken = params.get("session_token");

    if (urlToken) {
      setToken(urlToken);
      // Clean up URL
      window.history.replaceState({}, "", window.location.pathname);
    }

    const stored = urlToken || getToken();
    if (!stored) {
      setIsLoading(false);
      return;
    }

    checkAuthStatus(stored).then(({ authenticated }) => {
      if (authenticated) {
        setTokenState(stored);
        setIsAuthenticated(true);
      } else {
        clearToken();
      }
      setIsLoading(false);
    });
  }, []);

  const login = useCallback(() => {
    window.location.href = getLoginUrl();
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
    setIsAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider
      value={{ isAuthenticated, token, isLoading, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
