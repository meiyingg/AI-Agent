"use client";

import { useEffect, useRef, useState } from "react";
import {
  Database,
  Upload,
  Trash2,
  Loader2,
  FileText,
  FileAudio,
  Video,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { PageContainer } from "@/components/views/page-container";
import {
  uploadKb,
  listKbDocs,
  deleteKbDoc,
  getKbJob,
  type KbDoc,
} from "@/lib/api";

const KIND_ICON = { doc: FileText, audio: FileAudio, video: Video } as const;
const KIND_LABEL = { doc: "文档", audio: "音频", video: "视频" } as const;
const ACCEPT = ".txt,.md,.pdf,.docx,.mp3,.wav,.m4a,.aac,.flac,.ogg,.mp4,.mov,.mkv,.avi,.webm";

interface Job {
  name: string;
  status: "processing" | "error";
  error?: string;
}

export function KnowledgeView() {
  const [docs, setDocs] = useState<KbDoc[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [drag, setDrag] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [err, setErr] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    setDocs(await listKbDocs());
    setLoading(false);
  }
  useEffect(() => {
    refresh();
  }, []);

  function pollJob(jobId: string, name: string) {
    const timer = setInterval(async () => {
      const s = await getKbJob(jobId);
      if (s.status === "done") {
        clearInterval(timer);
        setJobs((j) => j.filter((x) => x.name !== name));
        refresh();
      } else if (s.status === "error" || s.status === "unknown") {
        clearInterval(timer);
        setJobs((j) => j.map((x) => (x.name === name ? { ...x, status: "error", error: s.error } : x)));
      }
    }, 3000);
  }

  async function handleFiles(files: File[]) {
    if (!files.length) return;
    setErr("");
    setUploading(true);
    try {
      const results = await uploadKb(files);
      const processing = results.filter((r) => r.status === "processing" && r.job_id);
      const errs = results.filter((r) => r.status === "error");
      setJobs((j) => [
        ...j,
        ...processing.map((r) => ({ name: r.name, status: "processing" as const })),
        ...errs.map((r) => ({ name: r.name, status: "error" as const, error: r.error })),
      ]);
      processing.forEach((r) => pollJob(r.job_id!, r.name));
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
    }
  }

  const totalChars = docs.reduce((s, d) => s + (d.chars || 0), 0);
  const totalChunks = docs.reduce((s, d) => s + (d.chunks || 0), 0);

  return (
    <PageContainer
      title="公司知识库"
      subtitle="上传公司内部资料（文档 / 音视频），自动入 RAG 供「内部知识 Agent」检索。文件只存本地。"
      icon={Database}
    >
      {/* 统计 */}
      <div className="mb-4 grid grid-cols-3 gap-3">
        <Stat label="文件" value={docs.length} />
        <Stat label="总字数" value={totalChars.toLocaleString()} />
        <Stat label="向量分块" value={totalChunks} />
      </div>

      {/* 上传区 */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          handleFiles(Array.from(e.dataTransfer.files));
        }}
        className={cn(
          "mb-3 flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-dashed p-8 text-center transition-colors",
          drag ? "border-primary bg-primary/5" : "border-border hover:bg-accent/40",
        )}
      >
        {uploading ? (
          <Loader2 className="size-7 animate-spin text-primary" />
        ) : (
          <Upload className="size-7 text-muted-foreground" />
        )}
        <div className="text-sm font-medium">拖拽文件到此，或点击上传</div>
        <div className="text-xs text-muted-foreground">
          文档 txt/md/pdf/docx · 音频 mp3/wav/m4a · 视频 mp4/mov（音视频自动转写）
        </div>
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        hidden
        onChange={(e) => {
          handleFiles(Array.from(e.target.files || []));
          e.target.value = "";
        }}
      />

      {err && (
        <div className="mb-3 flex items-start gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          <AlertCircle className="mt-0.5 size-4 shrink-0" />
          <span>{err}</span>
        </div>
      )}

      {jobs.map((j, i) => (
        <div key={i} className="mb-2 flex items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-sm">
          {j.status === "processing" ? (
            <Loader2 className="size-4 shrink-0 animate-spin text-primary" />
          ) : (
            <AlertCircle className="size-4 shrink-0 text-destructive" />
          )}
          <span className="truncate">{j.name}</span>
          <span className="ml-auto shrink-0 text-xs text-muted-foreground">
            {j.status === "processing" ? "转写入库中…" : j.error || "失败"}
          </span>
        </div>
      ))}

      {/* 文件表格 */}
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left font-medium">文件</th>
              <th className="px-3 py-2 text-left font-medium">类型</th>
              <th className="px-3 py-2 text-right font-medium">字数</th>
              <th className="px-3 py-2 text-right font-medium">分块</th>
              <th className="w-10 px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="py-8 text-center">
                  <Loader2 className="mx-auto size-5 animate-spin text-muted-foreground" />
                </td>
              </tr>
            ) : docs.length === 0 ? (
              <tr>
                <td colSpan={5} className="py-8 text-center text-xs text-muted-foreground">
                  还没有资料，拖拽或点击上方上传。
                </td>
              </tr>
            ) : (
              docs.map((d) => {
                const Icon = KIND_ICON[d.kind] ?? FileText;
                return (
                  <tr key={d.id} className="border-t">
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Icon className="size-4 shrink-0 text-primary" />
                        <span className="truncate">{d.name}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{KIND_LABEL[d.kind] ?? d.kind}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{d.chars}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{d.chunks}</td>
                    <td className="px-3 py-2">
                      <button
                        onClick={async () => {
                          await deleteKbDoc(d.id);
                          refresh();
                        }}
                        className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                        title="删除"
                      >
                        <Trash2 className="size-4" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </PageContainer>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="text-xl font-semibold">{value}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
