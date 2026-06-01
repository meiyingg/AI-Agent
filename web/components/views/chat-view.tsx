"use client";

import { useEffect, useRef, useState } from "react";
import { ChatPanel, type ChatMsg } from "@/components/chat-panel";
import { Worktable, type RunState, type Activity } from "@/components/worktable";
import { Sessions } from "@/components/sessions";
import { streamChat, listThreads, getThread, type Thread } from "@/lib/api";

const EMPTY_RUN: RunState = { mode: undefined, items: [], report: null, active: false };

let _c = 0;
const uid = () => `${Date.now()}-${_c++}`;

export function ChatView() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [run, setRun] = useState<RunState>(EMPTY_RUN);
  const [loading, setLoading] = useState(false);
  const [threads, setThreads] = useState<Thread[]>([]);
  const [activeThread, setActiveThread] = useState<string | null>(null);
  const threadRef = useRef<string | null>(null);
  const streamIdRef = useRef<string | null>(null);

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
    const userId = uid();
    setMessages((m) => [...m, { id: userId, role: "user", content: text }]);
    setRun({ mode: undefined, items: [], report: null, active: true });
    streamIdRef.current = null;
    setLoading(true);
    try {
      await streamChat(text, threadRef.current, (e) => {
        switch (e.type) {
          case "thread":
            threadRef.current = e.thread_id;
            setActiveThread(e.thread_id);
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
            setMessages((m) => [...m, { id, role: "assistant", content: `出错了：${msg}`, kind: "text" }]);
            break;
          }
        }
      });
    } catch (err) {
      const id = uid();
      setMessages((m) => [...m, { id, role: "assistant", content: `请求失败：${String(err)}`, kind: "text" }]);
    } finally {
      setLoading(false);
      streamIdRef.current = null;
      setRun((r) => ({ ...r, active: false }));
      listThreads().then(setThreads);
    }
  }

  async function selectThread(id: string) {
    if (loading || id === activeThread) return;
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
    if (loading) return;
    threadRef.current = null;
    setActiveThread(null);
    setMessages([]);
    setRun(EMPTY_RUN);
  }

  const lastQuestion = [...messages].reverse().find((m) => m.role === "user")?.content ?? "";

  return (
    <div className="flex h-full min-h-0">
      <aside className="hidden w-[210px] shrink-0 flex-col border-r lg:flex">
        <Sessions threads={threads} activeId={activeThread} loading={loading} onSelect={selectThread} onNew={newChat} />
      </aside>
      <div className="flex min-h-0 w-[40%] min-w-[300px] flex-col border-r">
        <ChatPanel messages={messages} loading={loading} onSend={handleSend} />
      </div>
      <div className="min-h-0 flex-1">
        <Worktable run={run} question={lastQuestion} />
      </div>
    </div>
  );
}
