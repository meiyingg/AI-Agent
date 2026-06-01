"use client";

import { useEffect, useRef, useState, type ComponentType } from "react";
import {
  Brain,
  Globe,
  Calculator,
  BookOpen,
  FileText,
  CheckCircle2,
  Loader2,
  TrendingUp,
  Lightbulb,
  AlertTriangle,
  Target,
  Link2,
  Sparkles,
  Cpu,
  CornerDownRight,
  Wrench,
  ChevronRight,
  ArrowDownRight,
  FileDown,
  Copy,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Report, Findings } from "@/lib/api";
import { exportReportPdf } from "@/lib/export-pdf";
import { Markdown } from "@/components/markdown";
import { MermaidView } from "@/components/mermaid-view";
import { buildDiagrams } from "@/lib/diagrams";

export type PhaseStatus = "running" | "done";
export interface ToolHit {
  name: string;
  count: number;
}
export type Activity =
  | { kind: "thought"; text: string }
  | { kind: "tool"; tool: string; args?: Record<string, unknown> }
  | { kind: "result"; tool: string; preview: string };
export interface PhaseItem {
  id: string;
  kind: "phase";
  agent: string;
  label: string;
  status: PhaseStatus;
  tools: ToolHit[];
  activities: Activity[];
  reasoning?: string; // qwq-plus 原生思考链 (流式累积)
  detail?: string;
}
export interface RouteItem {
  id: string;
  kind: "route";
  label: string;
}
export type TimelineItem = PhaseItem | RouteItem;

export interface RunState {
  mode?: "general" | "advisory";
  items: TimelineItem[];
  report: Report | null;
  findings?: Findings;
  active: boolean;
}

const AGENT_ICON: Record<string, ComponentType<{ className?: string }>> = {
  triage: Brain,
  research: Globe,
  analysis: Calculator,
  knowledge: BookOpen,
  advisor: FileText,
  general: Sparkles,
};

const TOOL_LABEL: Record<string, string> = {
  tavily_search: "Web Search",
  search_meeting_minutes: "Search Minutes",
  market_snapshot: "Market Snapshot",
  estimate_roi: "Estimate ROI",
  risk_score: "Risk Score",
  cost_estimate: "Cost Estimate",
  compare_options: "Compare Options",
  policy_incentive: "Policy Incentives",
  generate_decision_report: "Generate Report",
};

export function Worktable({ run, question }: { run: RunState; question: string }) {
  const idle = !run.mode && !run.active && run.items.length === 0 && !run.report;

  return (
    <div className="flex h-full flex-col bg-muted/30">
      <div className="flex h-12 items-center justify-between border-b bg-background/60 px-4">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Cpu className="size-4 text-primary" />
          Agent Worktable
        </div>
        {run.mode && (
          <Badge variant={run.mode === "advisory" ? "default" : "secondary"}>
            {run.mode === "advisory" ? "Investment Decision" : "General Q&A"}
          </Badge>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {idle ? (
          <EmptyState />
        ) : (
          <div className="space-y-4">
            <Timeline items={run.items} />
            {run.report && <ReportCard report={run.report} question={question} findings={run.findings} />}
          </div>
        )}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-6 text-center">
      <div className="mb-3 flex size-12 items-center justify-center rounded-2xl bg-primary/10">
        <Cpu className="size-6 text-primary" />
      </div>
      <p className="text-sm font-medium">Multi-Agent Live Worktable</p>
      <p className="mt-1.5 max-w-xs text-xs leading-relaxed text-muted-foreground">
        Ask on the left. Investment-decision questions show the full process here in real time:
        <span className="text-foreground"> Intent Triage → Dispatch → Expert Research (incl. tool calls) → Structured Advice</span>.
      </p>
    </div>
  );
}

function Timeline({ items }: { items: TimelineItem[] }) {
  return (
    <div className="space-y-1">
      {items.map((it) =>
        it.kind === "route" ? (
          <div key={it.id} className="flex items-center gap-2 py-0.5 pl-1 text-xs text-muted-foreground">
            <CornerDownRight className="size-3.5" />
            {it.label}
          </div>
        ) : (
          <PhaseRow key={it.id} item={it} />
        ),
      )}
    </div>
  );
}

function PhaseRow({ item }: { item: PhaseItem }) {
  const Icon = AGENT_ICON[item.agent] ?? Cpu;
  const running = item.status === "running";
  const hasDetail = !!item.reasoning || item.activities.length > 0 || !!item.detail;
  // 默认：执行中自动展开(实时看工具调用)，完成后收起；用户点击后转为手动控制
  const [override, setOverride] = useState<boolean | null>(null);
  const open = hasDetail && (override ?? running);

  return (
    <div className="rounded-lg">
      <button
        type="button"
        disabled={!hasDetail}
        onClick={() => setOverride(!open)}
        className="flex w-full items-center gap-3 rounded-md py-1 text-left enabled:hover:bg-background/60"
      >
        <div
          className={cn(
            "flex size-7 shrink-0 items-center justify-center rounded-full border",
            running
              ? "border-primary/30 bg-primary/5 text-primary"
              : "border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-900 dark:bg-emerald-950",
          )}
        >
          {running ? <Loader2 className="size-3.5 animate-spin" /> : <Icon className="size-3.5" />}
        </div>
        <span className="text-sm font-medium">{item.label}</span>
        {running ? (
          <span className="text-xs text-muted-foreground">Running…</span>
        ) : (
          <CheckCircle2 className="size-3.5 text-emerald-500" />
        )}
        {hasDetail && (
          <ChevronRight
            className={cn("ml-auto size-4 text-muted-foreground transition-transform", open && "rotate-90")}
          />
        )}
      </button>

      {/* 折叠态：工具 chips（实时可见，无需展开） */}
      {!open && item.tools.length > 0 && (
        <div className="mb-1 ml-10 flex flex-wrap gap-1.5">
          {item.tools.map((t, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded-md border bg-background px-1.5 py-0.5 text-[11px] text-muted-foreground"
            >
              <Wrench className="size-3 text-primary/70" />
              {TOOL_LABEL[t.name] ?? t.name}
              {t.count > 1 && <span className="text-primary">×{t.count}</span>}
            </span>
          ))}
        </div>
      )}

      {/* 展开态：推理 / 工具入参 / 返回 / 结论 (长内容可二次展开) */}
      {open && (
        <div className="mb-2 ml-10 space-y-1.5 border-l pl-3 text-xs">
          {item.reasoning && <ReasoningPanel text={item.reasoning} running={item.status === "running"} />}
          {item.activities.map((a, i) => {
            if (a.kind === "thought")
              return (
                <div key={i} className="flex items-start gap-1.5 text-muted-foreground">
                  <Brain className="mt-0.5 size-3 shrink-0 text-primary/70" />
                  <ClampText text={a.text} />
                </div>
              );
            if (a.kind === "tool")
              return (
                <div key={i} className="flex flex-wrap items-center gap-1.5 text-muted-foreground">
                  <Wrench className="size-3 shrink-0 text-primary/70" />
                  <span className="font-medium text-foreground/80">{TOOL_LABEL[a.tool] ?? a.tool}</span>
                  {formatArgs(a.args) && <span>{formatArgs(a.args)}</span>}
                </div>
              );
            return (
              <div key={i} className="flex items-start gap-1.5 text-muted-foreground/80">
                <ArrowDownRight className="mt-0.5 size-3 shrink-0" />
                <ClampText text={a.preview} />
              </div>
            );
          })}
          {item.detail && (
            <div>
              <div className="mb-0.5 mt-1.5 flex items-center gap-1 font-medium text-foreground/70">
                <FileText className="size-3" /> Conclusion
              </div>
              <div className="max-h-60 overflow-y-auto whitespace-pre-wrap rounded-md bg-muted/60 p-2 leading-relaxed text-foreground/80">
                {item.detail}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatArgs(args?: Record<string, unknown>): string {
  if (!args || Object.keys(args).length === 0) return "";
  if (typeof args.query === "string") return `“${args.query}”`;
  try {
    const s = JSON.stringify(args);
    return s.length > 80 ? s.slice(0, 80) + "…" : s;
  } catch {
    return "";
  }
}

// 思考链面板：流式时自动跟随到底部；完成后从顶部可自由滚动阅读
function ReasoningPanel({ text, running }: { text: string; running: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (running && ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [text, running]);
  return (
    <div className="rounded-md bg-primary/5 p-2">
      <div className="mb-1 flex items-center gap-1 font-medium text-primary/80">
        <Brain className="size-3" /> Reasoning
      </div>
      <div
        ref={ref}
        className="max-h-64 overflow-y-auto whitespace-pre-wrap leading-relaxed text-muted-foreground"
      >
        {text}
        {running && (
          <span className="ml-0.5 inline-block h-3 w-[3px] animate-pulse bg-primary/60 align-middle" />
        )}
      </div>
    </div>
  );
}

// 长文本：默认夹两行，超长可点"展开全部/收起"
function ClampText({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 90;
  return (
    <div className="min-w-0 flex-1">
      <div className={cn("whitespace-pre-wrap break-words", !open && long && "line-clamp-2")}>{text}</div>
      {long && (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="mt-0.5 text-[11px] text-primary hover:underline"
        >
          {open ? "Collapse" : "Show all"}
        </button>
      )}
    </div>
  );
}

function reportToText(report: Report, question: string): string {
  const sec = (t: string, items?: string[]) =>
    items && items.length ? `\n## ${t}\n${items.map((x) => `- ${x}`).join("\n")}\n` : "";
  return (
    `# Investment Recommendation Report\n\nQuestion: ${question}\nDecision: ${report.decision} ｜ Confidence: ${report.confidence}\n\n${report.summary || ""}\n` +
    (report.analysis ? `\n## Detailed Analysis\n${report.analysis}\n` : "") +
    sec("Rationale", report.rationale) +
    sec("Opportunities", report.opportunities) +
    sec("Risks", report.risks) +
    sec("Next Steps", report.actions) +
    sec("Sources", report.sources)
  );
}

const DECISION_STYLE: Record<string, string> = {
  Enter: "bg-emerald-500 text-white",
  Hold: "bg-amber-500 text-white",
  Avoid: "bg-rose-500 text-white",
  Exit: "bg-rose-500 text-white",
};

export function ReportCard({ report, question, findings }: { report: Report; question: string; findings?: Findings }) {
  const decisionCls =
    DECISION_STYLE[report.decision?.trim()] ?? "bg-primary text-primary-foreground";
  const diagrams = buildDiagrams(report);

  return (
    <div className="rounded-xl border bg-background shadow-sm">
      <div className="flex flex-wrap items-center gap-2 border-b p-4">
        <FileText className="size-4 text-primary" />
        <span className="font-semibold">Investment Recommendation</span>
        <span className={cn("ml-1 rounded-md px-2 py-0.5 text-xs font-semibold", decisionCls)}>
          {report.decision || "—"}
        </span>
        {report.confidence && (
          <Badge variant="outline" className="text-xs">
            Confidence {report.confidence}
          </Badge>
        )}
        <div className="ml-auto flex gap-1.5">
          <Button
            variant="outline"
            size="sm"
            className="gap-1.5"
            onClick={() => {
              navigator.clipboard.writeText(reportToText(report, question));
              toast.success("Report copied");
            }}
          >
            <Copy className="size-4" /> Copy
          </Button>
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => exportReportPdf(report, question, findings)}>
            <FileDown className="size-4" /> Export PDF
          </Button>
        </div>
      </div>

      <div className="space-y-4 p-4">
        {report.summary && (
          <p className="text-sm leading-relaxed text-foreground/90">{report.summary}</p>
        )}
        {report.metrics && Object.keys(report.metrics).length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold">
              <TrendingUp className="size-4 text-primary" /> Key Metrics
            </div>
            <table className="w-full border-collapse text-xs">
              <tbody>
                {Object.entries(report.metrics).map(([k, v]) => (
                  <tr key={k}>
                    <td className="w-1/3 border bg-muted/40 px-2 py-1 font-medium">{k}</td>
                    <td className="border px-2 py-1">{String(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {report.analysis && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold">
              <FileText className="size-4 text-primary" /> Detailed Analysis
            </div>
            <Markdown>{report.analysis}</Markdown>
          </div>
        )}
        {diagrams.map((d, i) => (
          <div key={i}>
            <div className="mb-1 text-xs font-semibold text-muted-foreground">{d.title}</div>
            <MermaidView code={d.code} />
          </div>
        ))}
        <Section icon={TrendingUp} title="Rationale" items={report.rationale} />
        <Section icon={Lightbulb} title="Opportunities" items={report.opportunities} tone="emerald" />
        <Section icon={AlertTriangle} title="Risks" items={report.risks} tone="amber" />
        <Section icon={Target} title="Next Steps" items={report.actions} />
        <SourceSection items={report.sources} />
        <FindingsSection findings={findings} />
      </div>
    </div>
  );
}

function FindingsSection({ findings }: { findings?: Findings }) {
  if (!findings) return null;
  const items = (
    [
      ["Industry Research", findings.research],
      ["Quant Analysis", findings.analysis],
      ["Internal Knowledge", findings.internal],
    ] as [string, string | undefined][]
  ).filter(([, v]) => v && v.trim());
  if (!items.length) return null;
  return (
    <details className="rounded-lg border bg-muted/30 p-3">
      <summary className="cursor-pointer text-sm font-semibold text-foreground/80">
        Research details (click to expand)
      </summary>
      <div className="mt-2 space-y-3">
        {items.map(([t, v]) => (
          <div key={t}>
            <div className="mb-0.5 text-xs font-semibold text-primary/80">{t}</div>
            <Markdown>{v as string}</Markdown>
          </div>
        ))}
      </div>
    </details>
  );
}

function Section({
  icon: Icon,
  title,
  items,
  tone,
}: {
  icon: ComponentType<{ className?: string }>;
  title: string;
  items?: string[];
  tone?: "emerald" | "amber";
}) {
  if (!items || items.length === 0) return null;
  const toneCls =
    tone === "emerald" ? "text-emerald-500" : tone === "amber" ? "text-amber-500" : "text-primary";
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold">
        <Icon className={cn("size-4", toneCls)} />
        {title}
      </div>
      <ul className="space-y-1 pl-1">
        {items.map((it, i) => (
          <li key={i} className="flex gap-2 text-sm text-foreground/85">
            <span className="mt-2 size-1 shrink-0 rounded-full bg-muted-foreground/50" />
            <span>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SourceSection({ items }: { items?: string[] }) {
  if (!items || items.length === 0) return null;
  const linkOf = (s: string) => s.match(/https?:\/\/\S+/)?.[0] ?? null;
  return (
    <div>
      <div className="mb-1.5 flex items-center gap-1.5 text-sm font-semibold">
        <Link2 className="size-4 text-primary" />
        Sources
      </div>
      <ul className="space-y-1">
        {items.map((it, i) => {
          const url = linkOf(it);
          const label = url ? it.replace(url, "").replace(/[：:\s]+$/, "") : it;
          return (
            <li key={i} className="text-xs text-muted-foreground">
              {url ? (
                <a
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-primary underline underline-offset-2 hover:opacity-80"
                >
                  {label || url}
                </a>
              ) : (
                it
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
