"use client";

import { useEffect, useRef, useState } from "react";
import { ChatPanel, type ChatMsg } from "@/components/chat-panel";
import { Worktable, type RunState, type Activity } from "@/components/worktable";
import { Sessions } from "@/components/sessions";
import { cn } from "@/lib/utils";
import { streamChat, listThreads, getThread, type Thread } from "@/lib/api";

const EMPTY_RUN: RunState = { mode: undefined, items: [], report: null, active: false };

let _c = 0;
const uid = () => `${Date.now()}-${_c++}`;

export function ChatView({ showWorktable = true, onNewChat }: { showWorktable?: boolean; onNewChat?: () => void }) {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [run, setRun] = useState<RunState>(EMPTY_RUN);
  const [loading, setLoading] = useState(false);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThread, setActiveThread] = useState<string | null>(null);
  const [mobileTab, setMobileTab] = useState<"chat" | "work">("chat"); // 手机: 聊天 / 工作台 切换
  const threadRef = useRef<string | null>(null);
  const streamIdRef = useRef<string | null>(null);
  const runTokenRef = useRef(0); // 标识"当前拥有 UI 的对话流"；切换/新建时自增，使旧流回调失效(旧流仍后台跑完)

  useEffect(() => {
    listThreads().then(setThreads);
  }, []);

  function attachActivity(agent: string, act: Activity) {
    setRun((r) => {
      const items = r.items.slice();
      for (let i = items.length - 1; i >= 0; i--) {
        const it = items[i];
        if (it.kind === "phase" && it.agent === agent) {
          const activities = [...it.activities, act];
          let tools = it.tools;
          if (act.kind === "tool") {
            tools = tools.slice();
            const last = tools[tools.length - 1];
            if (last && last.name === act.tool) tools[tools.length - 1] = { ...last, count: last.count + 1 };
            else tools.push({ name: act.tool, count: 1 });
          }
          items[i] = { ...it, activities, tools };
          break;
        }
      }
      return { ...r, items };
    });
  }

  async function handleSend(text: string) {
    if (loading) return;
    const myToken = ++runTokenRef.current; // 本次发送的归属 token
    const userId = uid();
    setMessages((m) => [...m, { id: userId, role: "user", content: text }]);
    setRun({ mode: undefined, items: [], report: null, active: true });
    streamIdRef.current = null;
    setLoading(true);
    try {
      await streamChat(text, threadRef.current, (e) => {
        if (runTokenRef.current !== myToken) return; // 已切走/新建：丢弃此流的 UI 更新
        switch (e.type) {
          case "thread":
            threadRef.current = e.thread_id;
            setActiveThread(e.thread_id);
            listThreads().then(setThreads); // 后端已登记该会话 → 立即刷新左侧历史，新对话即时出现
            break;
          case "phase":
            if (e.status === "running") {
              const pid = uid();
              const agent = e.agent;
              const label = e.label;
              setRun((r) => ({
                ...r,
                items: [...r.items, { id: pid, kind: "phase", agent, label, status: "running", tools: [], activities: [] }],
              }));
            } else {
              const agent = e.agent;
              const detail = e.detail;
              const mode = e.mode;
              setRun((r) => {
                const items = r.items.slice();
                for (let i = items.length - 1; i >= 0; i--) {
                  const it = items[i];
                  if (it.kind === "phase" && it.agent === agent && it.status === "running") {
                    items[i] = { ...it, status: "done", detail: detail ?? it.detail };
                    break;
                  }
                }
                return { ...r, items, mode: agent === "triage" && mode ? mode : r.mode };
              });
            }
            break;
          case "route": {
            const rid = uid();
            const label = e.label;
            setRun((r) => ({ ...r, items: [...r.items, { id: rid, kind: "route", label }] }));
            break;
          }
          case "reasoning": {
            const agent = e.agent;
            const delta = e.delta;
            setRun((r) => {
              const items = r.items.slice();
              for (let i = items.length - 1; i >= 0; i--) {
                const it = items[i];
                if (it.kind === "phase" && it.agent === agent) {
                  items[i] = { ...it, reasoning: (it.reasoning ?? "") + delta };
                  break;
                }
              }
              return { ...r, items };
            });
            break;
          }
          case "thought":
            attachActivity(e.agent, { kind: "thought", text: e.text });
            break;
          case "tool": {
            attachActivity(e.agent, { kind: "tool", tool: e.tool, args: e.args });
            const sid = streamIdRef.current;
            if (sid) setMessages((m) => m.map((x) => (x.id === sid ? { ...x, content: "" } : x)));
            break;
          }
          case "tool_result":
            attachActivity(e.agent, { kind: "result", tool: e.tool, preview: e.preview });
            break;
          case "token": {
            const tok = e.content;
            if (!streamIdRef.current) {
              const id = uid();
              streamIdRef.current = id;
              setMessages((m) => [...m, { id, role: "assistant", content: tok, kind: "text" }]);
            } else {
              const sid = streamIdRef.current;
              setMessages((m) => m.map((x) => (x.id === sid ? { ...x, content: x.content + tok } : x)));
            }
            break;
          }
          case "message": {
            const content = e.content;
            const sid = streamIdRef.current;
            streamIdRef.current = null;
            if (sid) {
              setMessages((m) => m.map((x) => (x.id === sid ? { ...x, content } : x)));
            } else {
              const id = uid();
              setMessages((m) => [...m, { id, role: "assistant", content, kind: "text" }]);
            }
            break;
          }
          case "final": {
            const report = e.report;
            const findings = e.findings;
            const id = uid();
            setRun((r) => ({ ...r, report, findings }));
            setMessages((m) => [...m, { id, role: "assistant", content: "", kind: "report-pointer", decision: report?.decision }]);
            break;
          }
          case "error": {
            const id = uid();
            const msg = e.message;
            setMessages((m) => [...m, { id, role: "assistant", content: `Error: ${msg}`, kind: "text" }]);
            break;
          }
        }
      });
    } catch (err) {
      if (runTokenRef.current === myToken) {
        const id = uid();
        setMessages((m) => [...m, { id, role: "assistant", content: `Request failed: ${String(err)}`, kind: "text" }]);
      }
    } finally {
      // 仅当本流仍拥有 UI 时才重置 loading/run，避免后台旧流覆盖当前对话状态
      if (runTokenRef.current === myToken) {
        setLoading(false);
        streamIdRef.current = null;
        setRun((r) => ({ ...r, active: false }));
      }
      listThreads().then(setThreads); // 历史列表不受 token 限制：任何流(含后台)结束都刷新
    }
  }

  async function selectThread(id: string) {
    if (id === activeThread) return;
    runTokenRef.current++; // 当前流转后台，立即可切换
    setLoading(false);
    try {
      const detail = await getThread(id);
      threadRef.current = id;
      setActiveThread(id);
      setMessages(
        (detail.messages || []).map((m) => ({
          id: uid(),
          role: m.role === "human" || m.role === "user" ? "user" : "assistant",
          content: m.content,
          kind: "text" as const,
        })),
      );
      setRun(EMPTY_RUN);
    } catch {
      /* ignore */
    }
  }

  function newChat() {
    runTokenRef.current++; // 让正在跑的流转入后台(它会自己跑完并保存)，UI 立即可开新对话
    threadRef.current = null;
    setActiveThread(null);
    setMessages([]);
    setRun(EMPTY_RUN);
    setLoading(false);
    setMobileTab("chat");
    onNewChat?.(); // 桌面端: 顺便收起左侧导航栏
  }

  const lastQuestion = [...messages].reverse().find((m) => m.role === "user")?.content ?? "";

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* 手机: 聊天 / Agent 工作台 切换 (大屏两栏并排, 隐藏此切换) */}
      <div className="flex shrink-0 items-center gap-1 border-b p-1.5 lg:hidden">
        <button
          onClick={() => setMobileTab("chat")}
          className={cn(
            "flex-1 rounded-md py-1.5 text-sm font-medium transition-colors",
            mobileTab === "chat" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent",
          )}
        >
          Chat
        </button>
        <button
          onClick={() => setMobileTab("work")}
          className={cn(
            "flex-1 rounded-md py-1.5 text-sm font-medium transition-colors",
            mobileTab === "work" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent",
          )}
        >
          Agent worktable
        </button>
      </div>

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-[210px] shrink-0 flex-col border-r lg:flex">
          <Sessions threads={threads} activeId={activeThread} onSelect={selectThread} onNew={newChat} />
        </aside>
        <div
          className={cn(
            "min-h-0 flex-col lg:flex",
            mobileTab === "chat" ? "flex flex-1" : "hidden",
            showWorktable ? "lg:w-[40%] lg:min-w-[300px] lg:flex-none lg:border-r" : "lg:flex-1",
          )}
        >
          <ChatPanel messages={messages} loading={loading} onSend={handleSend} />
        </div>
        <div
          className={cn(
            "min-h-0 flex-1",
            mobileTab === "work" ? "block" : "hidden",
            showWorktable ? "lg:block" : "lg:hidden",
          )}
        >
          <Worktable run={run} question={lastQuestion} />
        </div>
      </div>
    </div>
  );
}
