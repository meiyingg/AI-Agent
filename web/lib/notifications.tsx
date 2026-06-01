"use client";

import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export interface Notif {
  id: string;
  title: string;
  desc?: string;
  ts: number;
  read: boolean;
}

interface Ctx {
  items: Notif[];
  unread: number;
  notify: (n: { title: string; desc?: string }) => void;
  markAllRead: () => void;
  clear: () => void;
}

const NotificationsContext = createContext<Ctx | null>(null);

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Notif[]>([]);

  const notify = useCallback((n: { title: string; desc?: string }) => {
    // 在 updater 外构造对象，保持 updater 纯函数（避免 StrictMode 双调用重复插入）
    const item: Notif = {
      id: Math.random().toString(36).slice(2),
      title: n.title,
      desc: n.desc,
      ts: Date.now(),
      read: false,
    };
    setItems((prev) => [item, ...prev].slice(0, 50));
  }, []);

  const markAllRead = useCallback(() => setItems((prev) => prev.map((x) => ({ ...x, read: true }))), []);
  const clear = useCallback(() => setItems([]), []);
  const unread = items.reduce((s, x) => s + (x.read ? 0 : 1), 0);

  return (
    <NotificationsContext.Provider value={{ items, unread, notify, markAllRead, clear }}>
      {children}
    </NotificationsContext.Provider>
  );
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error("useNotifications 必须在 NotificationsProvider 内使用");
  return ctx;
}
