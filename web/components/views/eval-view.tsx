"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { FlaskConical, Play, Loader2, RefreshCw } from "lucide-react";
import { PageContainer } from "@/components/views/page-container";
import {
  getEvalLatest, getEvalStatus, runEval,
  type EvalResult, type EvalItem,
} from "@/lib/api";

const METRICS: { key: keyof EvalItem; label: string }[] = [
  { key: "faithfulness", label: "Faithfulness" },
  { key: "answer_relevancy", label: "Answer relevancy" },
  { key: "context_precision", label: "Context precision" },
  { key: "context_recall", label: "Context recall" },
];

function color(v: number | null | undefined): string {
  if (v == null || isNaN(v)) return "#9ca3af";
  return v >= 0.8 ? "#16a34a" : v >= 0.5 ? "#f59e0b" : "#dc2626";
}
const fmt = (v: number | null | undefined) => (v == null || isNaN(v as number) ? "—" : (v as number).toFixed(2));

export function EvalView() {
  const [data, setData] = useState<EvalResult | null>(null);
  const [running, setRunning] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [limit, setLimit] = useState(5);
  const [notice, setNotice] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  async function refresh() {
    setData(await getEvalLatest());
  }
  useEffect(() => {
    refresh();
    return () => { if (timer.current) clearInterval(timer.current); };
  }, []);

  async function doRun() {
    setStatusMsg("starting…");
    const res = await runEval(limit);
    // 线上只读(镜像无 demo 语料)→ 不实跑,弹提示
    if (res.state === "readonly") {
      setNotice(res.msg || "To run a new evaluation, please contact the system administrator.");
      setStatusMsg("");
      return;
    }
    setRunning(true);
    timer.current = setInterval(async () => {
      const s = await getEvalStatus();
      setStatusMsg(s.msg || s.state);
      if (s.state === "done" || s.state === "error") {
        if (timer.current) clearInterval(timer.current);
        setRunning(false);
        if (s.state === "done") refresh();
      }
    }, 3000);
  }

  const summary = data?.summary ?? {};
  return (
    <PageContainer
      title="Eval"
      subtitle="RAG quality (RAGAS, judge = qwen) · golden set · faithfulness / relevancy / context precision·recall"
      icon={FlaskConical}
      actions={
        <div className="flex items-center gap-2">
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            disabled={running}
            className="rounded-md border bg-background px-2 py-1.5 text-sm disabled:opacity-50"
          >
            <option value={3}>3 questions</option>
            <option value={5}>5 questions</option>
            <option value={0}>all</option>
          </select>
          <button
            onClick={doRun}
            disabled={running}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 active:scale-[0.97] disabled:opacity-50"
          >
            {running ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
            {running ? "Running…" : "Run eval"}
          </button>
          <button
            onClick={refresh}
            disabled={running}
            className="rounded-md border p-1.5 transition-colors hover:bg-accent disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className="size-3.5" />
          </button>
        </div>
      }
    >
      {/* status / last-run */}
      <div className="mb-4 flex items-center gap-3 text-xs text-muted-foreground">
        {data?.ts ? <span>Last run: <b className="text-foreground">{data.ts}</b> · {data.n} questions</span> : <span>No run yet — click “Run eval”.</span>}
        {running && <span className="flex items-center gap-1 text-primary"><Loader2 className="size-3 animate-spin" /> {statusMsg} (≈1 RMB for a full run, takes a minute)</span>}
      </div>

      {/* 指标卡 */}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        {METRICS.map((m) => {
          const v = summary[m.key as string] as number | undefined;
          return (
            <div key={m.key as string} className="rounded-lg border bg-card p-4">
              <div className="mb-1.5 text-xs font-medium text-muted-foreground">{m.label}</div>
              <div className="text-3xl font-semibold leading-none tracking-tight" style={{ color: color(v) }}>
                {fmt(v)}
              </div>
            </div>
          );
        })}
      </div>

      {/* 每题明细 */}
      <Panel title="Per-question results">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="pb-2 text-left text-xs font-medium text-muted-foreground">Question</th>
                {METRICS.map((m) => (
                  <th key={m.key as string} className="pb-2 text-center text-xs font-medium text-muted-foreground">{m.label.split(" ")[0]}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(data?.items ?? []).map((it, i) => (
                <tr key={i} className="border-t align-top">
                  <td className="max-w-[420px] py-2 pr-3">{it.question}</td>
                  {METRICS.map((m) => {
                    const v = it[m.key] as number | null | undefined;
                    return (
                      <td key={m.key as string} className="py-2 text-center font-semibold tabular-nums" style={{ color: color(v) }}>{fmt(v)}</td>
                    );
                  })}
                </tr>
              ))}
              {!data?.items?.length && (
                <tr><td colSpan={5} className="py-8 text-center text-xs text-muted-foreground">No results yet.</td></tr>
              )}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">🟢 ≥ 0.80 good · 🟡 0.50–0.80 ok · 🔴 &lt; 0.50 weak · 0–1, higher is better</p>
      </Panel>

      {/* 只读提示弹窗(线上点 Run 时) */}
      {notice && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setNotice(null)}
        >
          <div
            className="w-full max-w-sm rounded-xl border bg-card p-5 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-2 flex items-center gap-2 text-base font-semibold">
              <FlaskConical className="size-4 text-primary" /> Evaluation
            </div>
            <p className="text-sm leading-relaxed text-muted-foreground">{notice}</p>
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setNotice(null)}
                className="rounded-md bg-primary px-3.5 py-1.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}
    </PageContainer>
  );
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-3 text-sm font-semibold">{title}</div>
      {children}
    </div>
  );
}
