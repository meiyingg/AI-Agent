// 导出投资报告为 PDF：用 Typora 主题(phycat-prussian) 渲染 + 浏览器打印另存。
import { marked } from "marked";
import type { Report, Findings } from "./api";
import { buildDiagrams, renderMermaid } from "./diagrams";

function esc(s: string): string {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function list(items?: string[]): string {
  if (!items || items.length === 0) return "";
  return `<ul>${items.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>`;
}

function sourceList(items?: string[]): string {
  if (!items || items.length === 0) return "";
  const li = items.map((s) => {
    const m = s.match(/https?:\/\/\S+/);
    if (m) {
      const url = m[0];
      const label = esc(s.replace(url, "").replace(/[：:\s]+$/, "")) || url;
      return `<li><a href="${url}">${label}</a></li>`;
    }
    return `<li>${esc(s)}</li>`;
  });
  return `<ul>${li.join("")}</ul>`;
}

function mdToHtml(t?: string): string {
  if (!t || !t.trim()) return "";
  try {
    return marked.parse(t, { async: false }) as string;
  } catch {
    return `<p>${esc(t)}</p>`;
  }
}

export function buildReportHtml(
  report: Report,
  question: string,
  date: string,
  findings?: Findings,
  diagrams?: { title: string; svg: string }[],
): string {
  const sec = (title: string, items?: string[]) =>
    items && items.length ? `<h2>${title}</h2>${list(items)}` : "";

  const metricsHtml =
    report.metrics && Object.keys(report.metrics).length
      ? `<h2>Key Metrics</h2><table>${Object.entries(report.metrics)
          .map(([k, v]) => `<tr><td><strong>${esc(k)}</strong></td><td>${esc(String(v))}</td></tr>`)
          .join("")}</table>`
      : "";
  const analysisHtml =
    report.analysis && report.analysis.trim() ? `<h2>Detailed Analysis</h2>${mdToHtml(report.analysis)}` : "";
  const diagramsHtml = (diagrams || [])
    .map((d) => `<h3>${esc(d.title)}</h3><div class="mmd">${d.svg}</div>`)
    .join("");

  const appendixParts = [
    findings?.research && `<h3>Industry Research</h3>${mdToHtml(findings.research)}`,
    findings?.analysis && `<h3>Quant Analysis</h3>${mdToHtml(findings.analysis)}`,
    findings?.internal && `<h3>Internal Knowledge</h3>${mdToHtml(findings.internal)}`,
  ].filter(Boolean);
  const appendix = appendixParts.length ? `<h2>Appendix · Research Details</h2>${appendixParts.join("")}` : "";

  return `
    <h1>Investment Recommendation Report</h1>
    <p><em>Question: ${esc(question)}　·　Date: ${date}</em></p>
    <p><strong>Decision:</strong> ${esc(report.decision || "—")}　｜　<strong>Confidence:</strong> ${esc(report.confidence || "—")}</p>
    <blockquote>${esc(report.summary || "")}</blockquote>
    ${metricsHtml}
    ${analysisHtml}
    ${diagramsHtml}
    ${sec("Rationale", report.rationale)}
    ${sec("Opportunities", report.opportunities)}
    ${sec("Risks", report.risks)}
    ${sec("Next Steps", report.actions)}
    ${report.sources && report.sources.length ? `<h2>Sources</h2>${sourceList(report.sources)}` : ""}
    ${appendix}
  `;
}

export async function exportReportPdf(report: Report, question: string, findings?: Findings): Promise<void> {
  // 先同步开窗(保住用户手势, 防弹窗拦截)，再异步渲染图表后填充
  const w = window.open("", "_blank", "width=900,height=1000");
  if (!w) {
    alert("The browser blocked the pop-up. Please allow pop-ups and try again.");
    return;
  }
  w.document.write(
    "<!doctype html><html><body style='font-family:sans-serif;padding:40px;color:#555'>Generating report…</body></html>",
  );

  const date = new Date().toLocaleDateString("en-US");
  const rendered: { title: string; svg: string }[] = [];
  for (const d of buildDiagrams(report)) {
    try {
      rendered.push({ title: d.title, svg: await renderMermaid(d.code) });
    } catch {
      /* 单张图失败跳过 */
    }
  }
  const inner = buildReportHtml(report, question, date, findings, rendered);
  const cssHref = `${location.origin}/themes/phycat-prussian.css`;
  w.document.open();
  w.document.write(`<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Investment Recommendation Report</title>
<link rel="stylesheet" href="${cssHref}">
<style>
  @page { margin: 18mm 16mm; }
  html, body { margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  .mmd { text-align: center; margin: 8px 0; }
  .mmd svg { max-width: 100%; height: auto; }
</style>
</head>
<body><div id="write">${inner}</div></body></html>`);
  w.document.close();

  let printed = false;
  const go = () => {
    if (printed || w.closed) return;
    printed = true;
    try {
      w.focus();
      w.print();
    } catch {
      /* ignore */
    }
  };
  w.onload = () => {
    try {
      w.document.fonts.ready.then(() => setTimeout(go, 250));
    } catch {
      setTimeout(go, 600);
    }
  };
  setTimeout(go, 2000);
}
