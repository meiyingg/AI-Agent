"use client";

import { useEffect, useState, type ReactNode } from "react";
import { toast } from "sonner";
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
      toast.success("Company profile saved");
      setTimeout(() => setSaved(false), 2000);
    } catch {
      toast.error("Save failed, please retry");
    } finally {
      setSaving(false);
    }
  }

  return (
    <PageContainer
      title="Company Profile"
      subtitle="Long-term memory · the company profile and preferences remembered across sessions, injected into Q&A and investment advice."
      icon={Building2}
      actions={
        <Button onClick={onSave} disabled={saving || loading} className="gap-1.5">
          {saving ? <Loader2 className="size-4 animate-spin" /> : saved ? <Check className="size-4" /> : <Save className="size-4" />}
          {saved ? "Saved" : "Save Profile"}
        </Button>
      }
    >
      {loading ? (
        <div className="flex justify-center py-10">
          <Loader2 className="size-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="space-y-4">
          <Field label="Company profile" hint="One line: industry / main business / markets">
            <Textarea rows={2} value={p.profile} onChange={(e) => setP({ ...p, profile: e.target.value })}
              placeholder="e.g. A cloud-kitchen operator running multiple virtual F&B brands across Singapore" />
          </Field>
          <Field label="Preferences" hint="Risk appetite / focus / constraints">
            <Textarea rows={2} value={p.preferences} onChange={(e) => setP({ ...p, preferences: e.target.value })}
              placeholder="e.g. Conservative risk appetite, focused on payback period" />
          </Field>
          <Field label="Key facts" hint="One per line; auto-deduplicated and capped">
            <Textarea rows={6} value={factsText} onChange={(e) => setFactsText(e.target.value)}
              className="font-mono text-xs"
              placeholder={"Core business: cloud kitchens · multiple virtual F&B brands\nMarkets: Singapore (+ SEA)\nKitchens: K1 Central · K2 East · K4 West"} />
          </Field>
          <Field label="Past conclusions summary" hint="A digest of previous advice (optional)">
            <Textarea rows={3} value={p.history} onChange={(e) => setP({ ...p, history: e.target.value })}
              placeholder="e.g. Previously approved a 6-week healthy-bowl pilot on the K2 kitchen" />
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
