"use client";

import { useEffect, useRef, useState, type ComponentType } from "react";
import {
  LayoutDashboard,
  Database,
  MessageSquare,
  Building2,
  Cpu,
  FileText,
  Upload,
  Settings,
  ArrowRight,
} from "lucide-react";
import { PieChart, Pie, Cell, Tooltip } from "recharts";
import { PageContainer } from "@/components/views/page-container";
import { getStats, listKbDocs, listReports, type Stats, type KbDoc, type ReportSummary } from "@/lib/api";

const PIE = ["#1D4E89", "#6BA3CC", "#e2a23b", "#10b981", "#f43f5e"];

export function OverviewView({ onNavigate }: { onNavigate: (v: string) => void }) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [docs, setDocs] = useState<KbDoc[]>([]);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  useEffect(() => {
    getStats().then(setStats);
    listKbDocs().then(setDocs);
    listReports().then(setReports);
  }, []);

  const typeData = [
    { name: "Docs", value: docs.filter((d) => d.kind === "doc").length },
    { name: "Audio", value: docs.filter((d) => d.kind === "audio").length },
    { name: "Video", value: docs.filter((d) => d.kind === "video").length },
  ].filter((x) => x.value > 0);

  const decData = ["Enter", "Hold", "Avoid", "Exit"]
    .map((k) => ({ name: k, value: reports.filter((r) => (r.decision || "").includes(k)).length }))
    .filter((x) => x.value > 0);

  return (
    <PageContainer title="Overview" subtitle="Foodsta Kitchens AI Advisor · Multi-Agent + Advanced RAG + Long-term Memory" icon={LayoutDashboard}>
      {/* 指标 */}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard icon={Database} label="KB files" value={stats?.kb.files ?? "—"} sub={`${(stats?.kb.chars ?? 0).toLocaleString()} chars`} />
        <StatCard icon={FileText} label="Vector chunks" value={stats?.kb.chunks ?? "—"} />
        <StatCard icon={MessageSquare} label="Sessions" value={stats?.threads ?? "—"} />
        <StatCard
          icon={Building2}
          label="Company profile"
          value={stats ? (stats.profile.has ? "Set" : "Not set") : "—"}
          sub={`${stats?.profile.facts ?? 0} facts`}
        />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {/* 模型概况 */}
        <div className="rounded-lg border bg-card p-4">
          <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
            <Cpu className="size-4 text-primary" /> Models
          </div>
          <ModelRow k="Chat / Report" v={stats?.models.chat} />
          <ModelRow k="Reasoning (CoT)" v={stats?.models.reasoning} />
          <ModelRow k="Embedding" v={stats?.models.embedding} />
        </div>

        {/* 快捷入口 */}
        <div className="rounded-lg border bg-card p-4">
          <div className="mb-2 text-sm font-semibold">Quick actions</div>
          <div className="grid grid-cols-2 gap-2">
            <Quick icon={MessageSquare} label="Start chat" onClick={() => onNavigate("chat")} />
            <Quick icon={Upload} label="Upload" onClick={() => onNavigate("knowledge")} />
            <Quick icon={Building2} label="Edit profile" onClick={() => onNavigate("profile")} />
            <Quick icon={Settings} label="Settings" onClick={() => onNavigate("settings")} />
          </div>
        </div>
      </div>

      {/* 数据洞察 */}
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <ChartCard title="KB file types">
          {typeData.length ? (
            <Donut data={typeData} />
          ) : (
            <Empty text="No materials yet" />
          )}
        </ChartCard>
        <ChartCard title="Decisions distribution">
          {decData.length ? (
            <Donut data={decData} />
          ) : (
            <Empty text="No decisions yet" />
          )}
        </ChartCard>
      </div>

      <div className="mt-4 rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
        Tip: upload internal company materials to the Knowledge base, and the Internal-Knowledge agent retrieves them
        automatically during Q&A; investment-decision questions launch multi-agent parallel research (Industry Research +
        Quant Analysis), with the reasoning chain shown live in the worktable on the right.
      </div>
    </PageContainer>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string | number;
  sub?: string;
}) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-1 flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="size-3.5" />
        {label}
      </div>
      <div className="text-2xl font-semibold leading-none">{value}</div>
      {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
    </div>
  );
}

function ModelRow({ k, v }: { k: string; v?: string }) {
  return (
    <div className="flex items-center justify-between py-1 text-sm">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-mono text-xs">{v ?? "—"}</span>
    </div>
  );
}

function Quick({ icon: Icon, label, onClick }: { icon: ComponentType<{ className?: string }>; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2.5 text-sm transition-colors hover:bg-accent"
    >
      <Icon className="size-4 text-primary" />
      {label}
      <ArrowRight className="ml-auto size-3.5 text-muted-foreground" />
    </button>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-2 text-sm font-semibold">{title}</div>
      <div className="h-[180px]">{children}</div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">{text}</div>;
}

function Donut({ data }: { data: { name: string; value: number }[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => setW(Math.floor(entries[0].contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return (
    <div ref={ref} className="h-full w-full">
      {w > 0 && (
        <PieChart width={w} height={180}>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={42} outerRadius={68} paddingAngle={2} label={(e) => `${e.name} ${e.value}`} labelLine={false}>
            {data.map((_, i) => (
              <Cell key={i} fill={PIE[i % PIE.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{ fontSize: 12, borderRadius: 8, border: "1px solid var(--border)", background: "var(--card)", color: "var(--card-foreground)" }}
          />
        </PieChart>
      )}
    </div>
  );
}
