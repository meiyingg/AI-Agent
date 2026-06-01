"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import {
  Brain,
  LayoutDashboard,
  MessageSquare,
  Database,
  Building2,
  Settings,
  Sun,
  Moon,
  PanelLeft,
  PanelRight,
  FileText,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { ChatView } from "@/components/views/chat-view";
import { OverviewView } from "@/components/views/overview-view";
import { KnowledgeView } from "@/components/views/knowledge-view";
import { ProfileView } from "@/components/views/profile-view";
import { SettingsView } from "@/components/views/settings-view";
import { ReportsView } from "@/components/views/reports-view";
import { CommandPalette } from "@/components/command-palette";
import { NotificationBell } from "@/components/notification-bell";
import { UserMenu } from "@/components/user-menu";
import { LoginScreen } from "@/components/login-screen";
import { useAuth } from "@/lib/auth";
import { health } from "@/lib/api";

const NAV = [
  { id: "overview", label: "Overview", Icon: LayoutDashboard },
  { id: "chat", label: "Chat", Icon: MessageSquare },
  { id: "reports", label: "Decisions", Icon: FileText },
  { id: "knowledge", label: "Knowledge", Icon: Database },
  { id: "profile", label: "Profile", Icon: Building2 },
  { id: "settings", label: "Settings", Icon: Settings },
] as const;

export default function Home() {
  const [view, setView] = useState<string>("overview");
  const [navCollapsed, setNavCollapsed] = useState(false);
  const [showWork, setShowWork] = useState(true);
  const [online, setOnline] = useState<boolean | null>(null);
  const [mounted, setMounted] = useState(false);
  const [cmdOpen, setCmdOpen] = useState(false);
  const { resolvedTheme, setTheme } = useTheme();
  const { user, ready } = useAuth();

  useEffect(() => {
    setMounted(true);
    const check = () => health().then(setOnline);
    check();
    const t = setInterval(check, 15000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCmdOpen((o) => !o);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  if (!ready) return null;
  if (!user) return <LoginScreen />;

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex h-14 shrink-0 items-center justify-between border-b px-3">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setNavCollapsed((v) => !v)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            title="Collapse / expand menu"
          >
            <PanelLeft className="size-4" />
          </button>
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Brain className="size-4" />
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold">Chamber Investment Advisor</div>
              <div className="hidden text-[11px] text-muted-foreground sm:block">Multi-Agent · Advanced RAG · Long-term Memory</div>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setCmdOpen(true)}
            className="hidden items-center gap-1.5 rounded-md border px-2 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-foreground sm:flex"
            title="Command palette"
          >
            <Search className="size-3.5" /> Search
            <kbd className="rounded border bg-muted px-1 text-[10px]">Ctrl K</kbd>
          </button>
          {view === "chat" && (
            <button
              onClick={() => setShowWork((v) => !v)}
              className={cn(
                "rounded-md p-1.5 hover:bg-accent",
                showWork ? "text-primary" : "text-muted-foreground hover:text-foreground",
              )}
              title={showWork ? "Hide Agent worktable" : "Show Agent worktable"}
            >
              <PanelRight className="size-4" />
            </button>
          )}
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span
              className={cn(
                "size-1.5 rounded-full",
                online ? "bg-emerald-500" : online === false ? "bg-rose-500" : "bg-muted-foreground/40",
              )}
            />
            <span className="hidden md:inline">{online ? "Backend online" : online === false ? "Backend offline" : "Checking"}</span>
          </span>
          <NotificationBell />
          <button
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            title="Toggle theme"
          >
            {mounted && resolvedTheme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
          <UserMenu />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <nav
          className={cn(
            "flex shrink-0 flex-col gap-0.5 border-r p-2 transition-all",
            navCollapsed ? "w-[52px]" : "w-[168px]",
          )}
        >
          {NAV.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setView(id)}
              title={navCollapsed ? label : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-lg py-2 text-sm transition-colors",
                navCollapsed ? "justify-center px-0" : "px-3",
                view === id ? "bg-primary/10 font-medium text-primary" : "text-foreground/70 hover:bg-accent",
              )}
            >
              <Icon className="size-4 shrink-0" />
              {!navCollapsed && label}
            </button>
          ))}
        </nav>

        <main className="min-w-0 flex-1">
          <div className={cn("h-full", view === "chat" ? "block" : "hidden")}>
            <ChatView showWorktable={showWork} />
          </div>
          {view === "overview" && <OverviewView onNavigate={setView} />}
          {view === "reports" && <ReportsView />}
          {view === "knowledge" && <KnowledgeView />}
          {view === "profile" && <ProfileView />}
          {view === "settings" && <SettingsView />}
        </main>
      </div>

      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} onNavigate={setView} />
    </div>
  );
}
