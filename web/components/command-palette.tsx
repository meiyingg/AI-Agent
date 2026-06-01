"use client";

import { type ReactNode } from "react";
import { Command } from "cmdk";
import { useTheme } from "next-themes";
import {
  LayoutDashboard,
  MessageSquare,
  FileText,
  Database,
  Building2,
  Settings,
  Sun,
  Moon,
  Upload,
  Search,
} from "lucide-react";

const NAV_ITEMS = [
  { id: "overview", label: "Overview", Icon: LayoutDashboard },
  { id: "chat", label: "Chat", Icon: MessageSquare },
  { id: "reports", label: "Decisions", Icon: FileText },
  { id: "knowledge", label: "Knowledge", Icon: Database },
  { id: "profile", label: "Profile", Icon: Building2 },
  { id: "settings", label: "Settings", Icon: Settings },
];

export function CommandPalette({
  open,
  onOpenChange,
  onNavigate,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onNavigate: (v: string) => void;
}) {
  const { resolvedTheme, setTheme } = useTheme();

  function run(fn: () => void) {
    fn();
    onOpenChange(false);
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 pt-[16vh] backdrop-blur-sm"
      onClick={() => onOpenChange(false)}
    >
      <Command
        label="Command palette"
        className="w-full max-w-lg overflow-hidden rounded-xl border bg-popover text-popover-foreground shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === "Escape") onOpenChange(false);
        }}
      >
        <div className="flex items-center gap-2 border-b px-3">
          <Search className="size-4 shrink-0 text-muted-foreground" />
          <Command.Input
            autoFocus
            placeholder="Search pages or actions…"
            className="h-11 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground"
          />
          <kbd className="hidden rounded border bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground sm:inline">ESC</kbd>
        </div>
        <Command.List className="max-h-[320px] overflow-y-auto p-1.5 [&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:text-muted-foreground">
          <Command.Empty className="py-6 text-center text-sm text-muted-foreground">No results</Command.Empty>
          <Command.Group heading="Go to">
            {NAV_ITEMS.map(({ id, label, Icon }) => (
              <Item key={id} onSelect={() => run(() => onNavigate(id))}>
                <Icon className="size-4 text-muted-foreground" /> {label}
              </Item>
            ))}
          </Command.Group>
          <Command.Group heading="Actions">
            <Item onSelect={() => run(() => onNavigate("knowledge"))}>
              <Upload className="size-4 text-muted-foreground" /> Upload materials
            </Item>
            <Item onSelect={() => run(() => setTheme(resolvedTheme === "dark" ? "light" : "dark"))}>
              {resolvedTheme === "dark" ? (
                <Sun className="size-4 text-muted-foreground" />
              ) : (
                <Moon className="size-4 text-muted-foreground" />
              )}
              Switch to {resolvedTheme === "dark" ? "light" : "dark"} theme
            </Item>
          </Command.Group>
        </Command.List>
      </Command>
    </div>
  );
}

function Item({ children, onSelect }: { children: ReactNode; onSelect: () => void }) {
  return (
    <Command.Item
      onSelect={onSelect}
      className="flex cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-2 text-sm data-[selected=true]:bg-accent"
    >
      {children}
    </Command.Item>
  );
}
