"use client";

import { useEffect, useState, type ReactNode, type ComponentType } from "react";
import { toast } from "sonner";
import { useTheme } from "next-themes";
import { Settings, Cpu, Brain, Network, Database, Sun, Moon, Monitor, Info, ExternalLink, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { PageContainer } from "@/components/views/page-container";
import { getSettings, putSettings, type AppSettings } from "@/lib/api";

export function SettingsView() {
  const [s, setS] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const { theme, setTheme } = useTheme();

  useEffect(() => {
    getSettings().then((d) => {
      setS(d);
      setLoading(false);
    });
  }, []);

  async function toggleMemory(key: string, val: boolean) {
    setS((prev) => (prev ? { ...prev, memory: { ...prev.memory, [key]: val } } : prev));
    await putSettings("memory", { [key]: val });
    toast.success("Settings updated");
  }

  return (
    <PageContainer title="Settings" subtitle="Models, memory, multi-agent, appearance, and about." icon={Settings}>
      {loading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : !s ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          The backend returned no settings (it may not have been restarted). Please run <code>Ctrl+C → python server/main.py</code> to restart the backend, then refresh.
        </div>
      ) : (
        <div className="space-y-4">
          <Card icon={Cpu} title="Models">
            <Row k="Chat / Triage / Report" v={String(s.model.chat_model_name)} />
            <Row k="Reasoning (CoT)" v={String(s.model.reasoning_model_name)} />
            <Row k="Embedding" v={String(s.model.embedding_model_name)} />
          </Card>

          <Card icon={Brain} title="Memory">
            <ToggleRow
              k="Long-term profile injection"
              desc="Inject the company profile as background into Q&A and investment advice"
              on={!!s.memory.profile_inject}
              onChange={(v) => toggleMemory("profile_inject", v)}
            />
            <ToggleRow
              k="Auto-extract after chat"
              desc="Automatically distill company facts from chats into the profile"
              on={!!s.memory.auto_extract}
              onChange={(v) => toggleMemory("auto_extract", v)}
            />
            <Row k="Max profile facts" v={String(s.memory.profile_max_facts ?? "-")} />
          </Card>

          <Card icon={Network} title="Multi-Agent">
            <Row k="Min research experts" v={String(s.multiagent.min_workers ?? "-")} />
            <Row k="Recursion limit" v={String(s.multiagent.recursion_limit ?? "-")} />
          </Card>

          <Card icon={Database} title="Knowledge Base / Transcription">
            <Row k="ASR model" v={String(s.kb.asr_model ?? "-")} />
            <Row k="Segment seconds" v={String(s.kb.asr_segment_seconds ?? "-")} />
            <Row k="Max file size (MB)" v={String(s.kb.max_upload_mb ?? "-")} />
          </Card>

          <Card icon={Sun} title="Appearance">
            <div className="flex items-center justify-between py-1.5">
              <span className="text-sm">Theme</span>
              <div className="flex gap-1 rounded-lg border p-0.5">
                {[
                  { v: "light", Icon: Sun, label: "Light" },
                  { v: "dark", Icon: Moon, label: "Dark" },
                  { v: "system", Icon: Monitor, label: "System" },
                ].map(({ v, Icon, label }) => (
                  <button
                    key={v}
                    onClick={() => setTheme(v)}
                    className={cn(
                      "flex items-center gap-1 rounded-md px-2.5 py-1 text-xs transition-colors",
                      theme === v ? "bg-primary text-primary-foreground" : "hover:bg-accent",
                    )}
                  >
                    <Icon className="size-3.5" />
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </Card>

          <Card icon={Info} title="About">
            <Row k="Project" v="Chamber Investment Advisor · Multi-Agent + RAG + Long-term Memory" />
          </Card>

          <p className="px-1 text-xs text-muted-foreground">
            Note: models and parameters are read-only; toggles take effect immediately and persist. To change model names/parameters, edit config/settings.yml and restart the backend.
          </p>
        </div>
      )}
    </PageContainer>
  );
}

function Card({ icon: Icon, title, children }: { icon: ComponentType<{ className?: string }>; title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        <Icon className="size-4 text-primary" />
        {title}
      </div>
      <div className="divide-y">{children}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-mono text-xs">{v}</span>
    </div>
  );
}

function ToggleRow({ k, desc, on, onChange }: { k: string; desc: string; on: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div>
        <div className="text-sm">{k}</div>
        <div className="text-xs text-muted-foreground">{desc}</div>
      </div>
      <button
        onClick={() => onChange(!on)}
        className={cn("relative h-5 w-9 shrink-0 rounded-full transition-colors", on ? "bg-primary" : "bg-muted-foreground/30")}
      >
        <span className={cn("absolute top-0.5 size-4 rounded-full bg-white transition-all", on ? "left-[18px]" : "left-0.5")} />
      </button>
    </div>
  );
}
