"use client";

import { useState } from "react";
import { Brain, ArrowRight, Database, MessageSquare, Cpu } from "lucide-react";
import { useAuth } from "@/lib/auth";

export function LoginScreen() {
  const { login } = useAuth();
  const [name, setName] = useState("Admin");

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary/10 via-background to-background p-4">
      <div className="w-full max-w-sm rounded-2xl border bg-card p-8 shadow-xl">
        <div className="mb-6 flex flex-col items-center gap-3 text-center">
          <div className="flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Brain className="size-6" />
          </div>
          <div>
            <div className="text-lg font-semibold">Chamber Investment Advisor</div>
            <div className="text-sm text-muted-foreground">Multi-Agent · Advanced RAG · Long-term Memory</div>
          </div>
        </div>

        <label className="mb-1.5 block text-xs text-muted-foreground">Username</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && login(name)}
          className="mb-3 w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary/30"
          placeholder="Enter any name"
        />
        <button
          onClick={() => login(name)}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-primary py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Enter Console <ArrowRight className="size-4" />
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
        <p className="mt-4 text-center text-[11px] text-muted-foreground">Demo environment · mock login, no password</p>
      </div>
    </div>
  );
}
