// 从报告数据确定性生成 mermaid 可视化 + 渲染为 SVG (网页与 PDF 共用)。
import mermaid from "mermaid";
import type { Report } from "./api";

export interface Diagram {
  title: string;
  code: string;
}

function clean(s: string, max = 26): string {
  let t = String(s).replace(/["[\]{}()|<>#;]/g, " ").replace(/\s+/g, " ").trim();
  if (t.length > max) t = t.slice(0, max) + "…";
  return t;
}

// 甘特图任务名不能含 ':' 等，单独清洗
function cleanGantt(s: string, n: number, max = 14): string {
  let t = String(s).replace(/[:：,，#;|<>"[\]{}()]/g, " ").replace(/\s+/g, " ").trim();
  if (t.length > max) t = t.slice(0, max) + "…";
  return `${n}. ${t}`;
}

export function buildDiagrams(report: Report): Diagram[] {
  const out: Diagram[] = [];

  const opps = (report.opportunities || []).slice(0, 4);
  const risks = (report.risks || []).slice(0, 4);
  if (opps.length || risks.length) {
    const L = ["flowchart LR", `  D["决策：${clean(report.decision || "—", 10)}"]:::dec`];
    if (opps.length) {
      L.push(`  Oh(["机会"]):::ohead`, `  D --> Oh`);
      opps.forEach((o, i) => L.push(`  O${i}["${clean(o)}"]:::opp`, `  Oh --> O${i}`));
    }
    if (risks.length) {
      L.push(`  Rh(["风险"]):::rhead`, `  D --> Rh`);
      risks.forEach((r, i) => L.push(`  R${i}["${clean(r)}"]:::risk`, `  Rh --> R${i}`));
    }
    L.push(
      "  classDef dec fill:#1D4E89,color:#fff,stroke:#1D4E89",
      "  classDef ohead fill:#6BA3CC,color:#fff,stroke:#1D4E89",
      "  classDef rhead fill:#e2a23b,color:#fff,stroke:#b45309",
      "  classDef opp fill:#E1EDF5,stroke:#6BA3CC,color:#003153",
      "  classDef risk fill:#fdecec,stroke:#dc2626,color:#7f1d1d",
    );
    out.push({ title: "机会 · 风险", code: L.join("\n") });
  }

  const actions = (report.actions || []).slice(0, 6);
  if (actions.length) {
    const L = [
      "gantt",
      "  dateFormat YYYY-MM-DD",
      "  axisFormat %m月",
      "  title 落地时间线 示意",
      "  section 实施",
    ];
    actions.forEach((a, i) => {
      const start = `2026-${String(i + 1).padStart(2, "0")}-01`;
      L.push(`  ${cleanGantt(a, i + 1)} :a${i}, ${start}, 30d`);
    });
    out.push({ title: "落地时间线", code: L.join("\n") });
  }

  return out;
}

let _init = false;
function ensureInit() {
  if (_init) return;
  mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose", fontFamily: "inherit" });
  _init = true;
}

export async function renderMermaid(code: string): Promise<string> {
  ensureInit();
  const id = "mmd-" + Math.random().toString(36).slice(2);
  const { svg } = await mermaid.render(id, code);
  return svg;
}
