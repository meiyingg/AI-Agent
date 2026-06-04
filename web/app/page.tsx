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
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
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
        <div className="flex min-w-0 items-center gap-2">
          <button
            onClick={() => setMobileNavOpen((v) => !v)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground md:hidden"
            title="Menu"
          >
            <PanelLeft className="size-4" />
          </button>
          <button
            onClick={() => setNavCollapsed((v) => !v)}
            className="hidden rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground md:block"
            title="Collapse / expand menu"
          >
            <PanelLeft className="size-4" />
          </button>
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Brain className="size-4" />
            </div>
            <div className="min-w-0 leading-tight">
              <div className="truncate text-sm font-semibold">Chamber Investment Advisor</div>
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
                "hidden rounded-md p-1.5 hover:bg-accent lg:block",
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
        {/* mobile drawer backdrop */}
        {mobileNavOpen && (
          <div
            className="fixed inset-x-0 bottom-0 top-14 z-30 bg-black/40 md:hidden"
            onClick={() => setMobileNavOpen(false)}
          />
        )}
        <nav
          className={cn(
            "flex shrink-0 flex-col gap-0.5 border-r bg-background p-2",
            // mobile: off-canvas drawer under the header
            "fixed bottom-0 left-0 top-14 z-40 w-60 transition-transform",
            mobileNavOpen ? "translate-x-0" : "-translate-x-full",
            // md+: back in normal flow; width collapses
            "md:static md:top-auto md:z-auto md:w-[168px] md:translate-x-0 md:transition-all",
            navCollapsed && "md:w-[52px]",
          )}
        >
          {NAV.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => {
                setView(id);
                setMobileNavOpen(false); // 点功能项后自动收起手机抽屉
              }}
              title={navCollapsed ? label : undefined}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                navCollapsed && "md:justify-center md:px-0",
                view === id ? "bg-primary/10 font-medium text-primary" : "text-foreground/70 hover:bg-accent",
              )}
            >
              <Icon className="size-4 shrink-0" />
              <span className={cn(navCollapsed && "md:hidden")}>{label}</span>
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
