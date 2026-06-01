"use client";

import { useState } from "react";
import { Bell, CheckCheck, Inbox } from "lucide-react";
import { useNotifications } from "@/lib/notifications";
import { relativeTime } from "@/lib/format";

export function NotificationBell() {
  const { items, unread, clear, markAllRead } = useNotifications();
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => {
          setOpen((o) => !o);
          if (!open) markAllRead();
        }}
        className="relative rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        title="Notifications"
      >
        <Bell className="size-4" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex min-w-[15px] items-center justify-center rounded-full bg-rose-500 px-1 text-[9px] font-semibold leading-none text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-50 mt-2 w-80 overflow-hidden rounded-lg border bg-popover text-popover-foreground shadow-lg">
            <div className="flex items-center justify-between border-b px-3 py-2">
              <span className="text-sm font-semibold">Notifications</span>
              {items.length > 0 && (
                <button onClick={clear} className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
                  <CheckCheck className="size-3.5" /> Clear
                </button>
              )}
            </div>
            <div className="max-h-[360px] overflow-y-auto">
              {items.length === 0 ? (
                <div className="flex flex-col items-center gap-2 py-8 text-sm text-muted-foreground">
                  <Inbox className="size-6" />
                  No notifications
                </div>
              ) : (
                items.map((n) => (
                  <div key={n.id} className="border-b px-3 py-2.5 last:border-0">
                    <div className="flex items-start gap-2">
                      {!n.read && <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-primary" />}
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium">{n.title}</div>
                        {n.desc && <div className="truncate text-xs text-muted-foreground">{n.desc}</div>}
                        <div className="mt-0.5 text-[11px] text-muted-foreground">{relativeTime(n.ts)}</div>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
