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
      ? `<h2>关键指标</h2><table>${Object.entries(report.metrics)
          .map(([k, v]) => `<tr><td><strong>${esc(k)}</strong></td><td>${esc(String(v))}</td></tr>`)
          .join("")}</table>`
      : "";
  const analysisHtml =
    report.analysis && report.analysis.trim() ? `<h2>详细分析</h2>${mdToHtml(report.analysis)}` : "";
  const diagramsHtml = (diagrams || [])
    .map((d) => `<h3>${esc(d.title)}</h3><div class="mmd">${d.svg}</div>`)
    .join("");

  const appendixParts = [
    findings?.research && `<h3>行业调研</h3>${mdToHtml(findings.research)}`,
    findings?.analysis && `<h3>量化分析</h3>${mdToHtml(findings.analysis)}`,
    findings?.internal && `<h3>内部知识</h3>${mdToHtml(findings.internal)}`,
  ].filter(Boolean);
  const appendix = appendixParts.length ? `<h2>附录 · 调研详情</h2>${appendixParts.join("")}` : "";

  return `
    <h1>投资建议报告</h1>
    <p><em>企业问题：${esc(question)}　·　生成日期：${date}</em></p>
    <p><strong>结论：</strong>${esc(report.decision || "—")}　｜　<strong>置信度：</strong>${esc(report.confidence || "—")}</p>
    <blockquote>${esc(report.summary || "")}</blockquote>
    ${metricsHtml}
    ${analysisHtml}
    ${diagramsHtml}
    ${sec("依据", report.rationale)}
    ${sec("机会", report.opportunities)}
    ${sec("风险", report.risks)}
    ${sec("下一步行动", report.actions)}
    ${report.sources && report.sources.length ? `<h2>参考来源</h2>${sourceList(report.sources)}` : ""}
    ${appendix}
  `;
}

export async function exportReportPdf(report: Report, question: string, findings?: Findings): Promise<void> {
  // 先同步开窗(保住用户手势, 防弹窗拦截)，再异步渲染图表后填充
  const w = window.open("", "_blank", "width=900,height=1000");
  if (!w) {
    alert("浏览器拦截了弹窗，请允许弹窗后重试。");
    return;
  }
  w.document.write(
    "<!doctype html><html><body style='font-family:sans-serif;padding:40px;color:#555'>正在生成报告…</body></html>",
  );

  const date = new Date().toLocaleDateString("zh-CN");
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
<html lang="zh-CN"><head><meta charset="utf-8">
<title>投资建议报告</title>
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
