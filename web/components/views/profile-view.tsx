"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Building2, Loader2, Save, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { PageContainer } from "@/components/views/page-container";
import { getMemory, putMemory, type Profile } from "@/lib/api";

const EMPTY: Profile = { profile: "", preferences: "", facts: [], history: "" };

export function ProfileView() {
  const [p, setP] = useState<Profile>(EMPTY);
  const [factsText, setFactsText] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getMemory()
      .then((d) => {
        setP(d);
        setFactsText((d.facts || []).join("\n"));
      })
      .finally(() => setLoading(false));
  }, []);

  async function onSave() {
    setSaving(true);
    try {
      const facts = factsText.split("\n").map((s) => s.trim()).filter(Boolean);
      const r = await putMemory({ ...p, facts });
      setP(r);
      setFactsText((r.facts || []).join("\n"));
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageContainer
      title="企业档案"
      subtitle="长期记忆 · 跨会话记住的企业画像与偏好，会注入到问答与投资建议中。"
      icon={Building2}
      actions={
        <Button onClick={onSave} disabled={saving || loading} className="gap-1.5">
          {saving ? <Loader2 className="size-4 animate-spin" /> : saved ? <Check className="size-4" /> : <Save className="size-4" />}
          {saved ? "已保存" : "保存档案"}
        </Button>
      }
    >
      {loading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="space-y-4">
          <Field label="企业画像" hint="一句话：行业 / 主营 / 市场">
            <Textarea rows={2} value={p.profile} onChange={(e) => setP({ ...p, profile: e.target.value })}
              placeholder="如：一家钠离子电池储能制造商，主供东南亚市场" />
          </Field>
          <Field label="偏好" hint="风险偏好 / 关注点 / 约束">
            <Textarea rows={2} value={p.preferences} onChange={(e) => setP({ ...p, preferences: e.target.value })}
              placeholder="如：风险偏好保守，重视回本周期" />
          </Field>
          <Field label="关键事实" hint="每行一条，自动去重并限制条数">
            <Textarea rows={6} value={factsText} onChange={(e) => setFactsText(e.target.value)}
              className="font-mono text-xs"
              placeholder={"主营钠离子电池储能\n目标市场东南亚\n规划年产能5GWh"} />
          </Field>
          <Field label="历史结论摘要" hint="过往建议的浓缩（可留空）">
            <Textarea rows={3} value={p.history} onChange={(e) => setP({ ...p, history: e.target.value })}
              placeholder="如：曾建议以轻资产 PACK 方式进入吉打州" />
          </Field>
        </div>
      )}
    </PageContainer>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="mb-1.5 flex items-baseline justify-between">
        <label className="text-sm font-medium">{label}</label>
        {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
      </div>
      {children}
    </div>
  );
}
