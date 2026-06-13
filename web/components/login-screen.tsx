"use client";

import { useState } from "react";
import Image from "next/image";
import { ArrowRight, Database, MessageSquare, Cpu, Loader2 } from "lucide-react";
import { useAuth } from "@/lib/auth";

export function LoginScreen() {
  const { login } = useAuth();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (loading) return;
    setLoading(true);
    setError("");
    const ok = await login(username, password);
    if (!ok) {
      setError("Wrong username or password");
      setLoading(false);
    }
    // on success the app re-renders (user is set) and this screen unmounts
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary/10 via-background to-background p-4">
      <div className="w-full max-w-sm rounded-2xl border bg-card p-8 shadow-xl">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <div className="flex size-12 items-center justify-center rounded-xl bg-primary">
            <Image
              src="/logo.png"
              alt="Foodsta Kitchens AI Advisor"
              width={30}
              height={30}
              className="size-7 object-contain invert dark:invert-0"
              priority
            />
          </div>
          <div>
            <div className="text-lg font-semibold">Foodsta Kitchens AI Advisor</div>
            <div className="text-sm text-muted-foreground">Multi-Agent · Advanced RAG · Long-term Memory</div>
          </div>
        </div>

        <label className="mb-1.5 block text-xs text-muted-foreground">Username</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          className="mb-3 w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          placeholder="admin"
        />
        <label className="mb-1.5 block text-xs text-muted-foreground">Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
          className="mb-3 w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          placeholder="••••••••"
        />
        {error && <p className="mb-3 text-xs text-rose-500">{error}</p>}
        <button
          onClick={submit}
          disabled={loading}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-60"
        >
          {loading ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <>
              Enter Console <ArrowRight className="size-4" />
            </>
          )}
        </button>

        <div className="mt-6 flex items-center justify-center gap-4 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <MessageSquare className="size-3" /> Multi-Agent
          </span>
          <span className="flex items-center gap-1">
            <Database className="size-3" /> Advanced RAG
          </span>
          <span className="flex items-center gap-1">
            <Cpu className="size-3" /> Reasoning
          </span>
        </div>
      </div>
    </div>
  );
}
