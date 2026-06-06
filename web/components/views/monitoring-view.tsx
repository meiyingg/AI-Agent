"use client";

import { useEffect, useRef, useState, type ComponentType, type ReactNode } from "react";
import { Activity, DollarSign, Hash, MessageSquare, Calendar } from "lucide-react";
import { BarChart, Bar, XAxis, Tooltip, Cell } from "recharts";
import { PageContainer } from "@/components/views/page-container";
import {
  getUsageSummary, getUsageTimeseries, getUsageRecent, getUsageTools,
  type UsageSummary, type UsagePoint, type UsageRecentRow, type ToolStats,
} from "@/lib/api";

const yuan = (n: number) => "¥" + (n ?? 0).toFixed(4);
const num = (n: number) => (n ?? 0).toLocaleString();

export function MonitoringView() {
  const [sum, setSum] = useState<UsageSummary | null>(null);
  const [series, setSeries] = useState<UsagePoint[]>([]);
  const [recent, setRecent] = useState<UsageRecentRow[]>([]);
  const [tools, setTools] = useState<ToolStats>({ by_agent: [], by_tool: [] });

  async function refresh() {
    setSum(await getUsageSummary());
    setSeries(await getUsageTimeseries(14));
    setRecent(await getUsageRecent(30));
    setTools(await getUsageTools());
  }
  useEffect(() => { refresh(); }, []);

  const t = sum?.total;
  return (
    <PageContainer
      title="Monitoring"
      subtitle="LLM 用量与真实成本(DashScope 新加坡价)· Agent / 工具调用统计"
      icon={Activity}
      actions={<button onClick={refresh} className="rounded-md border px-3 py-1.5 text-sm hover:bg-accent">Refresh</button>}
    >
      {/* 指标卡 */}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Card icon={DollarSign} label="Total cost" value={yuan(t?.yuan ?? 0)} />
        <Card icon={Hash} label="Total tokens" value={num((t?.in_tokens ?? 0) + (t?.out_tokens ?? 0))}
          sub={`in ${num(t?.in_tokens ?? 0)} · out ${num(t?.out_tokens ?? 0)}`} />
        <Card icon={MessageSquare} label="Calls" value={num(t?.calls ?? 0)} />
        <Card icon={Calendar} label="Today" value={yuan(sum?.today?.yuan ?? 0)} sub={`${num(sum?.today?.calls ?? 0)} calls`} />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <Panel title="Daily cost (¥, last 14 days)">
          {series.length ? <Bars data={series} /> : <Empty text="No data yet" />}
        </Panel>
        <Panel title="By model">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr><th className="py-1 text-left font-medium">Model</th><th className="text-right font-medium">Calls</th>
                <th className="text-right font-medium">In</th><th className="text-right font-medium">Out</th><th className="text-right font-medium">¥</th></tr>
            </thead>
            <tbody>
              {(sum?.by_model ?? []).map((m) => (
                <tr key={m.model} className="border-t">
                  <td className="py-1.5">{m.model}</td>
                  <td className="text-right tabular-nums">{num(m.calls)}</td>
                  <td className="text-right tabular-nums">{num(m.in_tokens)}</td>
                  <td className="text-right tabular-nums">{num(m.out_tokens)}</td>
                  <td className="text-right tabular-nums">{yuan(m.yuan)}</td>
                </tr>
              ))}
              {!sum?.by_model?.length && <tr><td colSpan={5} className="py-4 text-center text-xs text-muted-foreground">No data yet</td></tr>}
            </tbody>
          </table>
        </Panel>
      </div>

      {/* 工具统计 */}
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <Panel title="Calls by agent"><CountBars rows={tools.by_agent.map((r) => ({ k: r.agent, n: r.n }))} /></Panel>
        <Panel title="Calls by tool"><CountBars rows={tools.by_tool.map((r) => ({ k: r.tool, n: r.n }))} /></Panel>
      </div>

      {/* 流水 */}
      <Panel title="Recent calls" className="mt-3">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr><th className="py-1 text-left font-medium">Time</th><th className="text-left font-medium">Model</th>
                <th className="text-left font-medium">Kind</th><th className="text-right font-medium">In</th>
                <th className="text-right font-medium">Out</th><th className="text-right font-medium">¥</th></tr>
            </thead>
            <tbody>
              {recent.map((r, i) => (
                <tr key={i} className="border-t">
                  <td className="whitespace-nowrap py-1.5 text-muted-foreground">{r.ts}</td>
                  <td>{r.model}</td>
                  <td className="text-muted-foreground">{r.kind}</td>
                  <td className="text-right tabular-nums">{num(r.in_tokens)}</td>
                  <td className="text-right tabular-nums">{num(r.out_tokens)}</td>
                  <td className="text-right tabular-nums">{yuan(r.cost_yuan)}</td>
                </tr>
              ))}
              {!recent.length && <tr><td colSpan={6} className="py-4 text-center text-xs text-muted-foreground">No data yet</td></tr>}
            </tbody>
          </table>
        </div>
      </Panel>
    </PageContainer>
  );
}

function Card({ icon: Icon, label, value, sub }: { icon: ComponentType<{ className?: string }>; label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground"><Icon className="size-3.5" />{label}</div>
      <div className="text-2xl font-semibold leading-none">{value}</div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function Panel({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={"rounded-lg border bg-card p-4 " + (className ?? "")}>
      <div className="mb-2 text-sm font-semibold">{title}</div>
      {children}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="flex h-[160px] items-center justify-center text-sm text-muted-foreground">{text}</div>;
}

function CountBars({ rows }: { rows: { k: string; n: number }[] }) {
  if (!rows.length) return <Empty text="No data yet" />;
  const max = Math.max(...rows.map((r) => r.n), 1);
  return (
    <div className="space-y-1.5">
      {rows.map((r) => (
        <div key={r.k} className="flex items-center gap-2 text-sm">
          <div className="w-32 truncate" title={r.k}>{r.k || "—"}</div>
          <div className="h-2 flex-1 rounded bg-muted"><div className="h-2 rounded bg-primary" style={{ width: `${(r.n / max) * 100}%` }} /></div>
          <div className="w-8 text-right tabular-nums text-muted-foreground">{r.n}</div>
        </div>
      ))}
    </div>
  );
}

function Bars({ data }: { data: UsagePoint[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((e) => setW(Math.floor(e[0].contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div ref={ref} className="h-[180px] w-full">
      {w > 0 && (
        <BarChart width={w} height={180} data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
          <XAxis dataKey="d" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
          <Tooltip formatter={(v) => "¥" + Number(v ?? 0).toFixed(4)}
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)", background: "var(--card)" }} />
          <Bar dataKey="yuan" radius={[4, 4, 0, 0]}>{data.map((_, i) => <Cell key={i} fill="#1D4E89" />)}</Bar>
        </BarChart>
      )}
    </div>
  );
}
