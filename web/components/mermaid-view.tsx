"use client";

import { useEffect, useState } from "react";
import { renderMermaid } from "@/lib/diagrams";

// 网页里渲染一段 mermaid 代码为 SVG。
export function MermaidView({ code }: { code: string }) {
  const [svg, setSvg] = useState("");
  useEffect(() => {
    let alive = true;
    renderMermaid(code)
      .then((s) => alive && setSvg(s))
      .catch(() => alive && setSvg(""));
    return () => {
      alive = false;
    };
  }, [code]);

  if (!svg) return null;
  return (
    <div
      className="my-1 flex justify-center overflow-x-auto rounded-lg border bg-background p-2 [&_svg]:max-w-full"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
