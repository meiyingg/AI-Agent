"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { login as apiLogin, type LoginResult } from "@/lib/api";

export interface User {
  name: string;
  role: string;
}

interface Ctx {
  user: User | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<LoginResult>;
  logout: () => void;
}

const AuthContext = createContext<Ctx | null>(null);
const KEY = "mia.user";
const CODE_KEY = "mia.code";

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

  async function login(username: string, password: string): Promise<LoginResult> {
    const res = await apiLogin(username, password);
    if (!res.ok) return res;
    const u: User = { name: username.trim() || "admin", role: "Investment Committee" };
    setUser(u);
    try {
      localStorage.setItem(KEY, JSON.stringify(u));
      localStorage.setItem(CODE_KEY, password); // api.ts 取它作为 X-Access-Code 头
    } catch {
      /* ignore */
    }
    return { ok: true };
  }

  function logout() {
    setUser(null);
    try {
      localStorage.removeItem(KEY);
      localStorage.removeItem(CODE_KEY);
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
