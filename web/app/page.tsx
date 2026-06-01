"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Brain, LayoutDashboard, MessageSquare, Database, Building2, Settings, Sun, Moon } from "lucide-react";
import { cn } from "@/lib/utils";
import { ChatView } from "@/components/views/chat-view";
import { OverviewView } from "@/components/views/overview-view";
import { KnowledgeView } from "@/components/views/knowledge-view";
import { ProfileView } from "@/components/views/profile-view";
import { SettingsView } from "@/components/views/settings-view";
import { health } from "@/lib/api";

const NAV = [
  { id: "overview", label: "概览", Icon: LayoutDashboard },
  { id: "chat", label: "对话", Icon: MessageSquare },
  { id: "knowledge", label: "知识库", Icon: Database },
  { id: "profile", label: "企业档案", Icon: Building2 },
  { id: "settings", label: "设置", Icon: Settings },
] as const;

export default function Home() {
  const [view, setView] = useState<string>("overview");
  const [online, setOnline] = useState<boolean | null>(null);
  const [mounted, setMounted] = useState(false);
  const { resolvedTheme, setTheme } = useTheme();

  useEffect(() => {
    setMounted(true);
    const check = () => health().then(setOnline);
    check();
    const t = setInterval(check, 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex h-14 shrink-0 items-center justify-between border-b px-4">
        <div className="flex items-center gap-2.5">
          <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Brain className="size-4" />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold">商会企业投资顾问</div>
            <div className="text-[11px] text-muted-foreground">多 Agent · 高级 RAG · 长期记忆</div>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              className={cn(
                "size-1.5 rounded-full",
                online ? "bg-emerald-500" : online === false ? "bg-rose-500" : "bg-muted-foreground/40",
              )}
            />
            {online ? "后端在线" : online === false ? "后端离线" : "检测中"}
          </span>
          <button
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            title="切换主题"
          >
            {mounted && resolvedTheme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <nav className="flex w-[168px] shrink-0 flex-col gap-0.5 border-r p-2">
          {NAV.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setView(id)}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                view === id ? "bg-primary/10 font-medium text-primary" : "text-foreground/70 hover:bg-accent",
              )}
            >
              <Icon className="size-4" />
              {label}
            </button>
          ))}
        </nav>

        <main className="min-w-0 flex-1">
          {/* 对话常驻，保住流式状态；非当前视图时隐藏 */}
          <div className={cn("h-full", view === "chat" ? "block" : "hidden")}>
            <ChatView />
          </div>
          {view === "overview" && <OverviewView onNavigate={setView} />}
          {view === "knowledge" && <KnowledgeView />}
          {view === "profile" && <ProfileView />}
          {view === "settings" && <SettingsView />}
        </main>
      </div>
    </div>
  );
}
