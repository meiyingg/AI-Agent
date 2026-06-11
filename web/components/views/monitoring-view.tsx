"use client";

import { useEffect, useRef, useState, type ComponentType, type ReactNode } from "react";
import {
  Activity, DollarSign, Hash, MessageSquare, Calendar,
  TrendingUp, Cpu, Wrench, Clock, RefreshCw,
} from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell, ResponsiveContainer, CartesianGrid } from "recharts";
import { PageContainer } from "@/components/views/page-container";
import {
  getUsageSummary, getUsageTimeseries, getUsageRecent, getUsageTools,
  type UsageSummary, type UsagePoint, type UsageRecentRow, type ToolStats,
} from "@/lib/api";

const CNY_TO_SGD = 0.19; // 人民币 → 新币 近似汇率(按实时汇率调整即可)
const sgd = (n: number) => "S$" + ((n ?? 0) * CNY_TO_SGD).toFixed(4);
const num = (n: number) => (n ?? 0).toLocaleString();

export function MonitoringView() {
  const [sum, setSum] = useState<UsageSummary | null>(null);
  const [series, setSeries] = useState<UsagePoint[]>([]);
  const [recent, setRecent] = useState<UsageRecentRow[]>([]);
  const [tools, setTools] = useState<ToolStats>({ by_agent: [], by_tool: [] });
  const [loading, setLoading] = useState(false);

  async function refresh() {
    setLoading(true);
    try {
      const [s, ts, rc, tl] = await Promise.all([
        getUsageSummary(), getUsageTimeseries(14), getUsageRecent(30), getUsageTools(),
      ]);
      setSum(s); setSeries(ts); setRecent(rc); setTools(tl);
    } finally { setLoading(false); }
  }
  useEffect(() => { refresh(); }, []);

  const t = sum?.total;
  return (
    <PageContainer
      title="Monitoring"
      subtitle="LLM usage & real cost"
      icon={Activity}
      actions={
        <button
          onClick={refresh}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-accent active:scale-[0.97] disabled:opacity-50"
        >
          <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      }
    >
      {/* ── 指标卡 ── */}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard icon={DollarSign} label="Total cost" value={sgd(t?.yuan ?? 0)} />
        <StatCard icon={Hash} label="Total tokens" value={num((t?.in_tokens ?? 0) + (t?.out_tokens ?? 0))}
          sub={`in ${num(t?.in_tokens ?? 0)} · out ${num(t?.out_tokens ?? 0)}`} />
        <StatCard icon={MessageSquare} label="Calls" value={num(t?.calls ?? 0)} />
        <StatCard icon={Calendar} label="Today" value={sgd(sum?.today?.yuan ?? 0)}
          sub={`${num(sum?.today?.calls ?? 0)} calls`} />
      </div>

      {/* ── 图表 + 模型 ── */}
      <div className="grid gap-3 md:grid-cols-2">
        <Panel icon={TrendingUp} title="Daily cost (S$, last 14 days)">
          {series.length ? <CostChart data={series} /> : <Empty text="No data yet" />}
        </Panel>
        <Panel icon={Cpu} title="By model">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="pb-2 text-left text-xs font-medium text-muted-foreground">Model</th>
                  <th className="pb-2 text-right text-xs font-medium text-muted-foreground">Calls</th>
                  <th className="pb-2 text-right text-xs font-medium text-muted-foreground">In</th>
                  <th className="pb-2 text-right text-xs font-medium text-muted-foreground">Out</th>
                  <th className="pb-2 text-right text-xs font-medium text-muted-foreground">S$</th>
                </tr>
              </thead>
              <tbody>
                {(sum?.by_model ?? []).map((m, i) => (
                  <tr key={m.model} className={`transition-colors hover:bg-muted/50 ${i !== 0 ? "border-t" : ""}`}>
                    <td className="py-2 font-medium">{m.model}</td>
                    <td className="py-2 text-right tabular-nums text-muted-foreground">{num(m.calls)}</td>
                    <td className="py-2 text-right tabular-nums text-muted-foreground">{num(m.in_tokens)}</td>
                    <td className="py-2 text-right tabular-nums text-muted-foreground">{num(m.out_tokens)}</td>
                    <td className="py-2 text-right tabular-nums font-medium">{sgd(m.yuan)}</td>
                  </tr>
                ))}
                {!sum?.by_model?.length && (
                  <tr><td colSpan={5} className="py-6 text-center text-xs text-muted-foreground">No data yet</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      {/* ── 工具统计 ── */}
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <Panel icon={Activity} title="Calls by agent">
          <CountBars rows={tools.by_agent.map((r) => ({ k: r.agent, n: r.n }))} />
        </Panel>
        <Panel icon={Wrench} title="Calls by tool">
          <CountBars rows={tools.by_tool.map((r) => ({ k: r.tool, n: r.n }))} />
        </Panel>
      </div>

      {/* ── 流水 ── */}
      <Panel icon={Clock} title="Recent calls (last 30)" className="mt-3">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="pb-2 text-left text-xs font-medium text-muted-foreground">Time</th>
                <th className="pb-2 text-left text-xs font-medium text-muted-foreground">Model</th>
                <th className="pb-2 text-left text-xs font-medium text-muted-foreground">Kind</th>
                <th className="pb-2 text-right text-xs font-medium text-muted-foreground">In</th>
                <th className="pb-2 text-right text-xs font-medium text-muted-foreground">Out</th>
                <th className="pb-2 text-right text-xs font-medium text-muted-foreground">S$</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r, i) => (
                <tr key={i} className={`transition-colors hover:bg-muted/50 ${i !== 0 ? "border-t" : ""}`}>
                  <td className="whitespace-nowrap py-2 font-mono text-xs text-muted-foreground">{r.ts}</td>
                  <td className="py-2 font-medium">{r.model}</td>
                  <td className="py-2">
                    <span className="inline-block rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">{r.kind}</span>
                  </td>
                  <td className="py-2 text-right tabular-nums text-muted-foreground">{num(r.in_tokens)}</td>
                  <td className="py-2 text-right tabular-nums text-muted-foreground">{num(r.out_tokens)}</td>
                  <td className="py-2 text-right tabular-nums font-medium">{sgd(r.cost_yuan)}</td>
                </tr>
              ))}
              {!recent.length && (
                <tr><td colSpan={6} className="py-6 text-center text-xs text-muted-foreground">No data yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </PageContainer>
  );
}

/* ═══════════════ Sub-components ═══════════════ */

function StatCard({
  icon: Icon, label, value, sub,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string; value: string; sub?: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-4 transition-shadow hover:shadow-sm">
      <div className="mb-1.5 flex items-center gap-1.5 text-xs text-muted-foreground">
        <div className="flex size-6 items-center justify-center rounded-md bg-primary/10">
          <Icon className="size-3.5 text-primary" />
        </div>
        <span className="font-medium">{label}</span>
      </div>
      <div className="text-2xl font-semibold leading-none tracking-tight">{value}</div>
      {sub && <div className="mt-1.5 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function Panel({
  icon: Icon, title, children, className,
}: {
  icon?: ComponentType<{ className?: string }>;
  title: string; children: ReactNode; className?: string;
}) {
  return (
    <div className={`rounded-lg border bg-card p-4 ${className ?? ""}`}>
      <div className="mb-3 flex items-center gap-2">
        {Icon && (
          <div className="flex size-6 items-center justify-center rounded-md bg-primary/10">
            <Icon className="size-3.5 text-primary" />
          </div>
        )}
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      {children}
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return (
    <div className="flex h-[160px] items-center justify-center text-sm text-muted-foreground">{text}</div>
  );
}

function CountBars({ rows }: { rows: { k: string; n: number }[] }) {
  if (!rows.length) return <Empty text="No data yet" />;
  const max = Math.max(...rows.map((r) => r.n), 1);
  return (
    <div className="space-y-2.5">
      {rows.map((r) => (
        <div key={r.k}>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="max-w-[70%] truncate font-medium" title={r.k}>{r.k || "—"}</span>
            <span className="ml-2 shrink-0 tabular-nums text-xs text-muted-foreground">{r.n}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500 ease-out"
              style={{ width: `${Math.max((r.n / max) * 100, 3)}%`, opacity: 0.7 + 0.3 * (r.n / max) }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Pad missing dates to fill 14-day range ── */
function padSeries(raw: UsagePoint[], days = 14): UsagePoint[] {
  const map = new Map(raw.map((p) => [p.d, p]));
  const result: UsagePoint[] = [];
  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const dt = new Date(now);
    dt.setDate(dt.getDate() - i);
    const key = `${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
    result.push(map.get(key) ?? { d: key, yuan: 0, tokens: 0, calls: 0 });
  }
  return result;
}

function CostChart({ data }: { data: UsagePoint[] }) {
  const padded = padSeries(data).map((p) => ({ ...p, sgd: (p.yuan ?? 0) * CNY_TO_SGD }));
  return (
    <div className="h-[200px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={padded} margin={{ top: 8, right: 4, left: -12, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" opacity={0.4} vertical={false} />
          <XAxis dataKey="d" tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} interval={1} />
          <YAxis tick={{ fontSize: 10, fill: "var(--muted-foreground)" }} tickLine={false} axisLine={false} tickFormatter={(v) => "S$" + Number(v).toFixed(4)} />
          <Tooltip
            formatter={(v) => ["S$" + Number(v ?? 0).toFixed(4), "Cost"]}
            labelFormatter={(l) => `Date: ${l}`}
            contentStyle={{
              fontSize: 12, borderRadius: 8,
              border: "1px solid var(--border)",
              background: "var(--card)",
              color: "var(--card-foreground)",
            }}
          />
          <Bar dataKey="sgd" radius={[4, 4, 0, 0]} minPointSize={2}>
            {padded.map((p, i) => (
              <Cell key={i} fill={p.yuan > 0 ? "var(--primary)" : "var(--muted)"} opacity={p.yuan > 0 ? 0.75 : 0.3} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
