// 后端 API 客户端：SSE 对话流 + 全局档案(长期记忆)读写。
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000";

export interface Report {
  summary: string;
  decision: string;
  confidence: string;
  analysis?: string;
  metrics?: Record<string, string>;
  rationale: string[];
  opportunities: string[];
  risks: string[];
  actions: string[];
  sources: string[];
}

// 调研详情(给报告/PDF附录)
export interface Findings {
  research?: string;
  analysis?: string;
  internal?: string;
}

// 后端 execute_events 吐出的结构化事件
export type ChatEvent =
  | { type: "thread"; thread_id: string }
  | { type: "phase"; agent: string; label: string; status: "running" | "done"; mode?: "general" | "advisory"; detail?: string }
  | { type: "route"; to: string; label: string }
  | { type: "reasoning"; agent: string; delta: string }
  | { type: "thought"; agent: string; text: string }
  | { type: "tool"; agent: string; tool: string; args?: Record<string, unknown> }
  | { type: "tool_result"; agent: string; tool: string; preview: string }
  | { type: "token"; content: string }
  | { type: "message"; role: string; content: string }
  | { type: "final"; content: string; report: Report; findings?: Findings }
  | { type: "done" }
  | { type: "error"; message: string };

/** POST /api/chat 并逐事件回调 (解析 SSE: `data: {json}\n\n`)。 */
export async function streamChat(
  message: string,
  threadId: string | null,
  onEvent: (e: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, thread_id: threadId }),
    signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(`请求失败: ${res.status}`);
  }
  const t0 = performance.now();
  const el = () => ((performance.now() - t0) / 1000).toFixed(2);
  console.log(`[SSE] 已连接 status=${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let reads = 0;
  let ntok = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    reads++;
    // 关键诊断：若 read 次数=1 且都在结尾 → 浏览器在缓冲整条流
    console.log(`[SSE ${el()}s] read#${reads} (${value?.length ?? 0} 字节)`);
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const dataLine = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!dataLine) continue;
      const json = dataLine.slice(5).trim();
      if (!json) continue;
      try {
        const ev = JSON.parse(json) as ChatEvent;
        if (ev.type === "token") ntok++;
        else console.log(`[SSE ${el()}s] event: ${ev.type}`, ev);
        onEvent(ev);
      } catch {
        // 半包/解析失败忽略
      }
    }
  }
  console.log(`[SSE ${el()}s] 结束: reads=${reads}, token事件=${ntok}`);
}

export interface Profile {
  profile: string;
  preferences: string;
  facts: string[];
  history: string;
}

export async function getMemory(): Promise<Profile> {
  const r = await fetch(`${API_BASE}/api/memory`);
  return r.json();
}

export async function putMemory(p: Partial<Profile>): Promise<Profile> {
  const r = await fetch(`${API_BASE}/api/memory`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(p),
  });
  return r.json();
}

// 历史会话
export interface Thread {
  id: string;
  title: string;
  created_at: number;
  updated_at: number;
}

export async function listThreads(): Promise<Thread[]> {
  try {
    const r = await fetch(`${API_BASE}/api/threads`);
    return r.json();
  } catch {
    return [];
  }
}

export interface ThreadDetail {
  thread_id: string;
  messages: { role: string; content: string }[];
}

export async function getThread(id: string): Promise<ThreadDetail> {
  const r = await fetch(`${API_BASE}/api/threads/${id}`);
  return r.json();
}
