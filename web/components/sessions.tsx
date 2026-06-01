"use client";

import { Plus, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { relativeTime } from "@/lib/format";
import type { Thread } from "@/lib/api";

export function Sessions({
  threads,
  activeId,
  loading,
  onSelect,
  onNew,
}: {
  threads: Thread[];
  activeId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <div className="flex h-full flex-col bg-muted/40">
      <div className="p-2.5">
        <Button onClick={onNew} variant="outline" disabled={loading} className="w-full justify-start gap-2">
          <Plus className="size-4" />
          New chat
        </Button>
      </div>
      <div className="px-2.5 pb-1 text-[11px] font-medium tracking-wide text-muted-foreground">
        History
      </div>
      <div className="flex-1 space-y-0.5 overflow-y-auto px-1.5 pb-2">
        {threads.length === 0 ? (
          <p className="px-2 py-3 text-xs text-muted-foreground">No conversations yet. Send a message to start.</p>
        ) : (
          threads.map((t) => (
            <button
              key={t.id}
              onClick={() => onSelect(t.id)}
              className={cn(
                "flex w-full items-start gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors",
                t.id === activeId ? "bg-background shadow-sm" : "hover:bg-background/60",
              )}
            >
              <MessageSquare className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <div className="truncate">{t.title}</div>
                <div className="text-[10px] text-muted-foreground">{relativeTime(t.updated_at)}</div>
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
