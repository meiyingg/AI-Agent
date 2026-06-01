"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export interface User {
  name: string;
  role: string;
}

interface Ctx {
  user: User | null;
  ready: boolean;
  login: (name: string) => void;
  logout: () => void;
}

const AuthContext = createContext<Ctx | null>(null);
const KEY = "mia.user";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) setUser(JSON.parse(raw));
    } catch {
      /* ignore */
    }
    setReady(true);
  }, []);

  function login(name: string) {
    const u: User = { name: name.trim() || "Admin", role: "Investment Committee" };
    setUser(u);
    try {
      localStorage.setItem(KEY, JSON.stringify(u));
    } catch {
      /* ignore */
    }
  }

  function logout() {
    setUser(null);
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  }

  return <AuthContext.Provider value={{ user, ready, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return ctx;
}
