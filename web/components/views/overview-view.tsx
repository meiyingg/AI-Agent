"use client";

import { useEffect, useState, type ComponentType } from "react";
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
import { PageContainer } from "@/components/views/page-container";
import { getStats, type Stats } from "@/lib/api";

export function OverviewView({ onNavigate }: { onNavigate: (v: string) => void }) {
  const [stats, setStats] = useState<Stats | null>(null);
  useEffect(() => {
    getStats().then(setStats);
  }, []);

  return (
    <PageContainer title="概览" subtitle="商会企业投资顾问 · 多 Agent + 高级 RAG + 长期记忆" icon={LayoutDashboard}>
      {/* 指标 */}
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard icon={Database} label="知识库文件" value={stats?.kb.files ?? "—"} sub={`${(stats?.kb.chars ?? 0).toLocaleString()} 字`} />
        <StatCard icon={FileText} label="向量分块" value={stats?.kb.chunks ?? "—"} />
        <StatCard icon={MessageSquare} label="历史会话" value={stats?.threads ?? "—"} />
        <StatCard
          icon={Building2}
          label="企业档案"
          value={stats ? (stats.profile.has ? "已设置" : "未设置") : "—"}
          sub={`${stats?.profile.facts ?? 0} 条事实`}
        />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {/* 模型概况 */}
        <div className="rounded-lg border bg-card p-4">
          <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
            <Cpu className="size-4 text-primary" /> 模型概况
          </div>
          <ModelRow k="对话 / 报告" v={stats?.models.chat} />
          <ModelRow k="推理 (思考链)" v={stats?.models.reasoning} />
          <ModelRow k="向量化" v={stats?.models.embedding} />
        </div>

        {/* 快捷入口 */}
        <div className="rounded-lg border bg-card p-4">
          <div className="mb-2 text-sm font-semibold">快捷入口</div>
          <div className="grid grid-cols-2 gap-2">
            <Quick icon={MessageSquare} label="开始对话" onClick={() => onNavigate("chat")} />
            <Quick icon={Upload} label="上传资料" onClick={() => onNavigate("knowledge")} />
            <Quick icon={Building2} label="编辑档案" onClick={() => onNavigate("profile")} />
            <Quick icon={Settings} label="设置" onClick={() => onNavigate("settings")} />
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
        提示：上传公司内部资料到「知识库」，问答时「内部知识 Agent」会自动检索；投资决策类问题会启动多 Agent
        并行调研（行业调研 + 量化分析），右侧工作台实时显示思考链。
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
