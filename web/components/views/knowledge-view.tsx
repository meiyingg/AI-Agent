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
  Search,
  Eye,
  X,
  Download,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { relativeTime } from "@/lib/format";
import { useNotifications } from "@/lib/notifications";
import { Button } from "@/components/ui/button";
import { PageContainer } from "@/components/views/page-container";
import {
  uploadKb,
  listKbDocs,
  deleteKbDoc,
  getKbJob,
  searchKb,
  getKbDocText,
  getKbDocOriginal,
  type KbDoc,
  type KbChunk,
} from "@/lib/api";

const KIND_ICON = { doc: FileText, audio: FileAudio, video: Video } as const;
const KIND_LABEL = { doc: "Document", audio: "Audio", video: "Video" } as const;
const ACCEPT = ".txt,.md,.pdf,.docx,.xlsx,.mp3,.wav,.m4a,.aac,.flac,.ogg,.mp4,.mov,.mkv,.avi,.webm";

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
  const [q, setQ] = useState("");
  const [results, setResults] = useState<KbChunk[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [viewing, setViewing] = useState<{ doc: KbDoc; text: string; loading: boolean } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const { notify } = useNotifications();

  async function openDoc(d: KbDoc) {
    setViewing({ doc: d, text: "", loading: true });
    const text = await getKbDocText(d.id);
    setViewing({ doc: d, text, loading: false });
  }

  async function downloadDoc(d: KbDoc) {
    const url = await getKbDocOriginal(d.id);
    if (url) window.open(url, "_blank");
    else toast.error("Original file not available");
  }

  async function onSearch() {
    if (!q.trim()) return;
    setSearching(true);
    try {
      setResults(await searchKb(q.trim()));
    } finally {
      setSearching(false);
    }
  }

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
        toast.success(`${name} transcribed and indexed`);
        notify({ title: "Transcription done", desc: `${name} transcribed and added to the knowledge base` });
        refresh();
      } else if (s.status === "error" || s.status === "unknown") {
        clearInterval(timer);
        setJobs((j) => j.map((x) => (x.name === name ? { ...x, status: "error", error: s.error } : x)));
        toast.error(`${name} transcription failed`);
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
      const done = results.filter((r) => r.status === "done").length;
      setJobs((j) => [
        ...j,
        ...processing.map((r) => ({ name: r.name, status: "processing" as const })),
        ...errs.map((r) => ({ name: r.name, status: "error" as const, error: r.error })),
      ]);
      if (done) {
        toast.success(`Indexed ${done} file(s)`);
        notify({ title: "Materials indexed", desc: `${done} document(s) added to the knowledge base` });
      }
      if (processing.length) toast.info(`Transcribing ${processing.length} media file(s)…`);
      errs.forEach((r) => toast.error(`${r.name}: ${r.error || "processing failed"}`));
      processing.forEach((r) => pollJob(r.job_id!, r.name));
      await refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setErr(msg);
      toast.error(msg);
    } finally {
      setUploading(false);
    }
  }

  function confirmDelete(d: KbDoc) {
    toast(`Delete "${d.name}"?`, {
      action: {
        label: "Delete",
        onClick: async () => {
          await deleteKbDoc(d.id);
          toast.success("Deleted");
          refresh();
        },
      },
    });
  }

  const totalChars = docs.reduce((s, d) => s + (d.chars || 0), 0);
  const totalChunks = docs.reduce((s, d) => s + (d.chunks || 0), 0);

  return (
    <PageContainer
      title="Knowledge Base"
      subtitle="Upload internal company materials (documents / audio-video); they're auto-indexed into RAG for the Internal-Knowledge agent. Files stay local only."
      icon={Database}
    >
      {/* 统计 */}
      <div className="mb-4 grid grid-cols-3 gap-3">
        <Stat label="Files" value={docs.length} />
        <Stat label="Total chars" value={totalChars.toLocaleString()} />
        <Stat label="Vector chunks" value={totalChunks} />
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
        <div className="text-sm font-medium">Drag files here, or click to upload</div>
        <div className="text-xs text-muted-foreground">
          Documents txt/md/pdf/docx/xlsx · Audio mp3/wav/m4a · Video mp4/mov (media auto-transcribed)
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
            {j.status === "processing" ? "Transcribing & indexing…" : j.error || "failed"}
          </span>
        </div>
      ))}

      {/* RAG 检索预览 */}
      <div className="mb-4 rounded-lg border bg-card p-4">
        <div className="mb-2 flex flex-wrap items-center gap-x-1.5 text-sm font-semibold">
          <Search className="size-4 text-primary" /> Retrieval preview
          <span className="text-xs font-normal text-muted-foreground">Enter a question to see the snippets RAG actually hits (hybrid retrieval + rerank)</span>
        </div>
        <div className="flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSearch()}
            placeholder="e.g. What is the travel reimbursement cap?"
            className="flex-1 rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-1 focus:ring-primary"
          />
          <Button onClick={onSearch} disabled={searching || !q.trim()} className="gap-1.5">
            {searching ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
            Search
          </Button>
        </div>
        {results !== null && (
          <div className="mt-3 space-y-2">
            {results.length === 0 ? (
              <p className="text-xs text-muted-foreground">No relevant snippets found (the KB may be empty or unrelated to the question).</p>
            ) : (
              results.map((c, i) => (
                <div key={i} className="rounded-md border bg-muted/30 p-2.5 text-xs">
                  <div className="mb-1 flex items-center gap-1 font-medium text-primary/80">
                    <FileText className="size-3" /> {c.source} · Hit #{i + 1}
                  </div>
                  <div className="line-clamp-4 whitespace-pre-wrap leading-relaxed text-foreground/80">{c.text}</div>
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* 文件表格 */}
      <div className="overflow-hidden rounded-lg border">
        <table className="w-full text-sm">
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th className="px-3 py-2 text-left font-medium">File</th>
              <th className="px-3 py-2 text-left font-medium">Type</th>
              <th className="px-3 py-2 text-right font-medium">Chars</th>
              <th className="px-3 py-2 text-right font-medium">Chunks</th>
              <th className="px-3 py-2 text-right font-medium">Added</th>
              <th className="w-16 px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={6} className="py-8 text-center">
                  <Loader2 className="mx-auto size-5 animate-spin text-muted-foreground" />
                </td>
              </tr>
            ) : docs.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-xs text-muted-foreground">
                  No materials yet — drag or click above to upload.
                </td>
              </tr>
            ) : (
              docs.map((d) => {
                const Icon = KIND_ICON[d.kind] ?? FileText;
                return (
                  <tr key={d.id} className="border-t">
                    <td className="px-3 py-2">
                      <button
                        onClick={() => openDoc(d)}
                        className="flex max-w-full items-center gap-2 text-left hover:text-primary"
                        title="View content"
                      >
                        <Icon className="size-4 shrink-0 text-primary" />
                        <span className="truncate hover:underline">{d.name}</span>
                      </button>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{KIND_LABEL[d.kind] ?? d.kind}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{d.chars}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{d.chunks}</td>
                    <td className="px-3 py-2 text-right text-xs text-muted-foreground">{relativeTime(d.added_at)}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center justify-end gap-0.5">
                        <button
                          onClick={() => openDoc(d)}
                          className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                          title="View content"
                        >
                          <Eye className="size-4" />
                        </button>
                        {d.r2_key && (
                          <button
                            onClick={() => downloadDoc(d)}
                            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                            title="Download original"
                          >
                            <Download className="size-4" />
                          </button>
                        )}
                        <button
                          onClick={() => confirmDelete(d)}
                          className="rounded p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                          title="Delete"
                        >
                          <Trash2 className="size-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* 内容查看弹窗 */}
      {viewing && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
          onClick={() => setViewing(null)}
        >
          <div
            className="flex max-h-[80vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border bg-card shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between gap-3 border-b px-4 py-3">
              <div className="flex min-w-0 items-center gap-2">
                <FileText className="size-4 shrink-0 text-primary" />
                <span className="truncate text-sm font-semibold">{viewing.doc.name}</span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {viewing.doc.chars} chars · {viewing.doc.chunks} chunks
                </span>
              </div>
              <button
                onClick={() => setViewing(null)}
                className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
                title="Close"
              >
                <X className="size-4" />
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto p-4">
              {viewing.loading ? (
                <div className="flex justify-center py-10">
                  <Loader2 className="size-5 animate-spin text-muted-foreground" />
                </div>
              ) : viewing.text ? (
                <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-foreground/90">
                  {viewing.text}
                </pre>
              ) : (
                <p className="py-10 text-center text-sm text-muted-foreground">Unable to read content (the text may have been deleted).</p>
              )}
            </div>
            <div className="border-t px-4 py-2 text-[11px] text-muted-foreground">
              This is the text the system extracted from the original file and that the AI actually retrieves (transcript for media).
            </div>
          </div>
        </div>
      )}
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
