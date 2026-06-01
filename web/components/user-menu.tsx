"use client";

import { useState } from "react";
import { LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth";

export function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  if (!user) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex size-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground"
        title={user.name}
      >
        {user.name.slice(0, 1)}
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-50 mt-2 w-52 overflow-hidden rounded-lg border bg-popover p-1 text-popover-foreground shadow-lg">
            <div className="flex items-center gap-2.5 px-2.5 py-2">
              <div className="flex size-8 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                {user.name.slice(0, 1)}
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">{user.name}</div>
                <div className="truncate text-xs text-muted-foreground">{user.role}</div>
              </div>
            </div>
            <div className="my-1 h-px bg-border" />
            <button
              onClick={() => {
                logout();
                setOpen(false);
              }}
              className="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-sm text-foreground/80 hover:bg-accent"
            >
              <LogOut className="size-4" /> Sign out
            </button>
          </div>
        </>
      )}
    </div>
  );
}
