"use client";

import { useEffect, useRef, useState } from "react";
import { Send, ArrowRight, FileText, Sparkles, Copy } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { Markdown } from "@/components/markdown";

export interface ChatMsg {
  id: string;
  role: "user" | "assistant";
  content: string;
  kind?: "text" | "report-pointer";
  decision?: string;
}

const EXAMPLES = [
  "What was the meeting decision on the cross-border logistics plan?",
  "Should our battery factory build a plant in Malaysia?",
  "Latest policies on sodium-ion batteries in Southeast Asia",
];

export function ChatPanel({
  messages,
  loading,
  onSend,
}: {
  messages: ChatMsg[];
  loading: boolean;
  onSend: (text: string) => void;
}) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function submit() {
    const t = input.trim();
    if (!t || loading) return;
    onSend(t);
    setInput("");
  }

  const last = messages[messages.length - 1];
  const showThinking = loading && (!last || last.role === "user");

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto px-4 py-5">
        {messages.length === 0 ? (
          <Empty onPick={(t) => onSend(t)} disabled={loading} />
        ) : (
          <div className="mx-auto flex max-w-2xl flex-col gap-4">
            {messages.map((m) => (
              <Bubble key={m.id} msg={m} />
            ))}
            {showThinking && <Thinking />}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      <div className="border-t bg-background p-3">
        <div className="mx-auto flex max-w-2xl items-end gap-2">
          <Textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Ask anything… (investment-decision questions launch multi-agent research)"
            rows={1}
            className="max-h-40 min-h-[44px] resize-none"
          />
          <Button onClick={submit} disabled={loading || !input.trim()} size="icon" className="size-11 shrink-0">
            <Send className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}

function Bubble({ msg }: { msg: ChatMsg }) {
  if (msg.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-primary px-3.5 py-2 text-sm text-primary-foreground">
          {msg.content}
        </div>
      </div>
    );
  }
  if (msg.kind === "report-pointer") {
    return (
      <div className="flex justify-start">
        <div className="flex max-w-[85%] items-center gap-2.5 rounded-2xl rounded-bl-sm border bg-card px-3.5 py-2.5 text-sm">
          <FileText className="size-4 text-primary" />
          <span>
            Generated an <span className="font-semibold">Investment Recommendation Report</span>
            {msg.decision ? ` (Decision: ${msg.decision})` : ""}
          </span>
          <span className="flex items-center gap-0.5 text-xs text-muted-foreground">
            See right <ArrowRight className="size-3" />
          </span>
        </div>
      </div>
    );
  }
  return (
    <div className="group flex justify-start">
      <div className="relative max-w-[85%] rounded-2xl rounded-bl-sm border bg-card px-3.5 py-2">
        {msg.content ? (
          <>
            <Markdown>{msg.content}</Markdown>
            <button
              onClick={() => {
                navigator.clipboard.writeText(msg.content);
                toast.success("Copied");
              }}
              className="absolute -right-2 -top-2 hidden rounded-md border bg-background p-1 text-muted-foreground shadow-sm hover:text-foreground group-hover:block"
              title="Copy"
            >
              <Copy className="size-3.5" />
            </button>
          </>
        ) : (
          <Dots />
        )}
      </div>
    </div>
  );
}

function Dots() {
  return (
    <div className="flex items-center gap-1.5 py-1">
      <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:-0.3s]" />
      <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60 [animation-delay:-0.15s]" />
      <span className="size-1.5 animate-bounce rounded-full bg-muted-foreground/60" />
    </div>
  );
}

function Thinking() {
  return (
    <div className="flex justify-start">
      <div className="rounded-2xl rounded-bl-sm border bg-card px-3.5 py-2">
        <Dots />
      </div>
    </div>
  );
}

function Empty({ onPick, disabled }: { onPick: (t: string) => void; disabled: boolean }) {
  return (
    <div className="mx-auto flex h-full max-w-2xl flex-col items-center justify-center text-center">
      <div className="mb-3 flex size-12 items-center justify-center rounded-2xl bg-primary/10">
        <Sparkles className="size-6 text-primary" />
      </div>
      <h2 className="text-lg font-semibold">Chamber Investment Advisor</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Look up meeting minutes / check industry news / get investment recommendations — the system decides how to answer.
      </p>
      <div className="mt-5 flex w-full flex-col gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            disabled={disabled}
            onClick={() => onPick(ex)}
            className={cn(
              "rounded-lg border bg-card px-3.5 py-2.5 text-left text-sm transition-colors hover:bg-accent",
              "disabled:opacity-50",
            )}
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  );
}
