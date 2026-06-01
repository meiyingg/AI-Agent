"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { FileText, Trash2, Loader2, ArrowLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { relativeTime } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/views/page-container";
import { ReportCard } from "@/components/worktable";
import { listReports, getReport, deleteReport, type ReportSummary, type ReportDetail } from "@/lib/api";

const DECISION_STYLE: Record<string, string> = {
  Enter: "bg-emerald-500 text-white",
  Hold: "bg-amber-500 text-white",
  Avoid: "bg-rose-500 text-white",
  Exit: "bg-rose-500 text-white",
};

export function ReportsView() {
  const [list, setList] = useState<ReportSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<ReportDetail | null>(null);

  async function refresh() {
    setLoading(true);
    setList(await listReports());
    setLoading(false);
  }
  useEffect(() => {
    refresh();
  }, []);

  async function open(id: string) {
    const d = await getReport(id);
    if (d) setDetail(d);
    else toast.error("Record no longer exists");
  }

  function confirmDelete(r: ReportSummary) {
    toast("Delete this decision record?", {
      action: {
        label: "Delete",
        onClick: async () => {
          await deleteReport(r.id);
          toast.success("Deleted");
          refresh();
        },
      },
    });
  }

  if (detail) {
    return (
      <PageContainer
        title="Decision Record"
        subtitle={detail.question}
        icon={FileText}
        actions={
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setDetail(null)}>
            <ArrowLeft className="size-4" /> Back to list
          </Button>
        }
      >
        <ReportCard report={detail.report} question={detail.question} findings={detail.findings} />
      </PageContainer>
    );
  }

  return (
    <PageContainer title="Decisions" subtitle="History of investment recommendation reports; review each multi-agent decision." icon={FileText}>
      {loading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : list.length === 0 ? (
        <div className="rounded-lg border border-dashed py-10 text-center text-sm text-muted-foreground">
          No decision records yet. Ask an investment-decision question in Chat (e.g. &quot;Should we build a plant in Malaysia?&quot;) to generate one.
        </div>
      ) : (
        <div className="space-y-2">
          {list.map((r) => (
            <div key={r.id} className="flex items-center gap-3 rounded-lg border bg-card p-3 transition-colors hover:bg-accent/40">
              <span
                className={cn(
                  "shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold",
                  DECISION_STYLE[r.decision] ?? "bg-primary text-primary-foreground",
                )}
              >
                {r.decision || "—"}
              </span>
              <button onClick={() => open(r.id)} className="min-w-0 flex-1 text-left">
                <div className="truncate text-sm">{r.question}</div>
                <div className="text-xs text-muted-foreground">
                  Confidence {r.confidence || "—"} · {relativeTime(r.created_at)}
                </div>
              </button>
              <button
                onClick={() => confirmDelete(r)}
                className="shrink-0 rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                title="Delete"
              >
                <Trash2 className="size-4" />
              </button>
              <ChevronRight onClick={() => open(r.id)} className="size-4 shrink-0 cursor-pointer text-muted-foreground" />
            </div>
          ))}
        </div>
      )}
    </PageContainer>
  );
}
