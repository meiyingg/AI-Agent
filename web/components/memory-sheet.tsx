"use client";

import { useState, type ReactNode } from "react";
import { Building2, Loader2, Save, Brain } from "lucide-react";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
  SheetTrigger,
  SheetFooter,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getMemory, putMemory, type Profile } from "@/lib/api";

const EMPTY: Profile = { profile: "", preferences: "", facts: [], history: "" };

export function MemorySheet() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [p, setP] = useState<Profile>(EMPTY);
  const [factsText, setFactsText] = useState("");

  async function onOpenChange(next: boolean) {
    setOpen(next);
    if (next) {
      setLoading(true);
      try {
        const data = await getMemory();
        setP(data);
        setFactsText((data.facts || []).join("\n"));
      } finally {
        setLoading(false);
      }
    }
  }

  async function onSave() {
    setSaving(true);
    try {
      const facts = factsText
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      const saved = await putMemory({ ...p, facts });
      setP(saved);
      setFactsText((saved.facts || []).join("\n"));
      setOpen(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetTrigger render={<Button variant="outline" size="sm" className="gap-1.5" />}>
        <Building2 className="size-4" />
        企业档案
      </SheetTrigger>
      <SheetContent className="flex w-full flex-col gap-0 sm:max-w-md">
        <SheetHeader className="border-b">
          <SheetTitle className="flex items-center gap-2">
            <Brain className="size-4 text-primary" />
            企业长期档案
          </SheetTitle>
          <SheetDescription>
            跨会话记住的企业画像与偏好，会被注入到问答与投资建议中（长期记忆）。
          </SheetDescription>
        </SheetHeader>

        {loading ? (
          <div className="flex flex-1 items-center justify-center text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : (
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            <Field label="企业画像" hint="一句话：行业 / 主营 / 市场">
              <Textarea
                rows={2}
                value={p.profile}
                onChange={(e) => setP({ ...p, profile: e.target.value })}
                placeholder="如：一家钠离子电池储能制造商，主供东南亚市场"
              />
            </Field>
            <Field label="偏好" hint="风险偏好 / 关注点 / 约束">
              <Textarea
                rows={2}
                value={p.preferences}
                onChange={(e) => setP({ ...p, preferences: e.target.value })}
                placeholder="如：风险偏好保守，重视回本周期"
              />
            </Field>
            <Field label="关键事实" hint="每行一条，自动去重并限制条数">
              <Textarea
                rows={6}
                value={factsText}
                onChange={(e) => setFactsText(e.target.value)}
                placeholder={"主营钠离子电池储能\n目标市场东南亚\n规划年产能5GWh"}
                className="font-mono text-xs"
              />
            </Field>
            <Field label="历史结论摘要" hint="过往建议的浓缩（可留空）">
              <Textarea
                rows={3}
                value={p.history}
                onChange={(e) => setP({ ...p, history: e.target.value })}
                placeholder="如：曾建议以轻资产 PACK 方式进入吉打州"
              />
            </Field>
          </div>
        )}

        <SheetFooter className="border-t">
          <Button onClick={onSave} disabled={saving || loading} className="gap-1.5">
            {saving ? <Loader2 className="size-4 animate-spin" /> : <Save className="size-4" />}
            保存档案
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between">
        <label className="text-sm font-medium">{label}</label>
        {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
      </div>
      {children}
    </div>
  );
}
