"use client";

import { useEffect, useState, type ReactNode, type ComponentType } from "react";
import { useTheme } from "next-themes";
import { Settings, Cpu, Brain, Network, Database, Sun, Moon, Monitor, Info, ExternalLink, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { PageContainer } from "@/components/views/page-container";
import { getSettings, putSettings, type AppSettings } from "@/lib/api";

export function SettingsView() {
  const [s, setS] = useState<AppSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const { theme, setTheme } = useTheme();

  useEffect(() => {
    getSettings().then((d) => {
      setS(d);
      setLoading(false);
    });
  }, []);

  async function toggleMemory(key: string, val: boolean) {
    setS((prev) => (prev ? { ...prev, memory: { ...prev.memory, [key]: val } } : prev));
    await putSettings("memory", { [key]: val });
  }

  return (
    <PageContainer title="设置" subtitle="模型、记忆、多 Agent、外观与关于。" icon={Settings}>
      {loading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : !s ? (
        <div className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          后端未返回设置（可能未重启）。请 <code>Ctrl+C → python server/main.py</code> 重启后端后刷新。
        </div>
      ) : (
        <div className="space-y-4">
          <Card icon={Cpu} title="模型">
            <Row k="对话 / 分诊 / 报告" v={String(s.model.chat_model_name)} />
            <Row k="推理 (思考链)" v={String(s.model.reasoning_model_name)} />
            <Row k="向量化" v={String(s.model.embedding_model_name)} />
          </Card>

          <Card icon={Brain} title="记忆">
            <ToggleRow
              k="长期档案注入"
              desc="把企业档案作为背景注入问答与投资建议"
              on={!!s.memory.profile_inject}
              onChange={(v) => toggleMemory("profile_inject", v)}
            />
            <ToggleRow
              k="对话结束自动提炼"
              desc="自动从对话中提炼企业事实并入档案"
              on={!!s.memory.auto_extract}
              onChange={(v) => toggleMemory("auto_extract", v)}
            />
            <Row k="档案事实上限" v={String(s.memory.profile_max_facts ?? "-")} />
          </Card>

          <Card icon={Network} title="多 Agent">
            <Row k="最少调研专家数" v={String(s.multiagent.min_workers ?? "-")} />
            <Row k="递归上限" v={String(s.multiagent.recursion_limit ?? "-")} />
          </Card>

          <Card icon={Database} title="知识库 / 转写">
            <Row k="语音识别模型" v={String(s.kb.asr_model ?? "-")} />
            <Row k="分段秒数" v={String(s.kb.asr_segment_seconds ?? "-")} />
            <Row k="单文件上限(MB)" v={String(s.kb.max_upload_mb ?? "-")} />
          </Card>

          <Card icon={Sun} title="外观">
            <div className="flex items-center justify-between py-1.5">
              <span className="text-sm">主题</span>
              <div className="flex gap-1 rounded-lg border p-0.5">
                {[
                  { v: "light", Icon: Sun, label: "亮" },
                  { v: "dark", Icon: Moon, label: "暗" },
                  { v: "system", Icon: Monitor, label: "跟随" },
                ].map(({ v, Icon, label }) => (
                  <button
                    key={v}
                    onClick={() => setTheme(v)}
                    className={cn(
                      "flex items-center gap-1 rounded-md px-2.5 py-1 text-xs transition-colors",
                      theme === v ? "bg-primary text-primary-foreground" : "hover:bg-accent",
                    )}
                  >
                    <Icon className="size-3.5" />
                    {label}
                  </button>
                ))}
              </div>
            </div>
          </Card>

          <Card icon={Info} title="关于">
            <Row k="项目" v="商会企业投资顾问 · 多 Agent + RAG + 长期记忆" />
          </Card>

          <p className="px-1 text-xs text-muted-foreground">
            注：模型与参数为只读展示；开关即时生效并持久化。需要改模型名/参数可在 config/settings.yml 调整后重启后端。
          </p>
        </div>
      )}
    </PageContainer>
  );
}

function Card({ icon: Icon, title, children }: { icon: ComponentType<{ className?: string }>; title: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        <Icon className="size-4 text-primary" />
        {title}
      </div>
      <div className="divide-y">{children}</div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-muted-foreground">{k}</span>
      <span className="font-mono text-xs">{v}</span>
    </div>
  );
}

function ToggleRow({ k, desc, on, onChange }: { k: string; desc: string; on: boolean; onChange: (v: boolean) => void }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2">
      <div>
        <div className="text-sm">{k}</div>
        <div className="text-xs text-muted-foreground">{desc}</div>
      </div>
      <button
        onClick={() => onChange(!on)}
        className={cn("relative h-5 w-9 shrink-0 rounded-full transition-colors", on ? "bg-primary" : "bg-muted-foreground/30")}
      >
        <span className={cn("absolute top-0.5 size-4 rounded-full bg-white transition-all", on ? "left-[18px]" : "left-0.5")} />
      </button>
    </div>
  );
}
