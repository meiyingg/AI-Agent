"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// 轻量 markdown 渲染 (不依赖 typography 插件, 手动给元素上样式)
export function Markdown({ children }: { children: string }) {
  return (
    <div className="text-sm leading-relaxed text-foreground/90 [word-break:break-word]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children }) => <p className="my-1.5">{children}</p>,
          ul: ({ children }) => (
            <ul className="my-1.5 list-disc space-y-1 pl-5">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="my-1.5 list-decimal space-y-1 pl-5">{children}</ol>
          ),
          li: ({ children }) => <li className="marker:text-muted-foreground">{children}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-foreground">{children}</strong>
          ),
          h1: ({ children }) => <h1 className="mt-2 mb-1.5 text-base font-bold">{children}</h1>,
          h2: ({ children }) => <h2 className="mt-2 mb-1 text-sm font-bold">{children}</h2>,
          h3: ({ children }) => <h3 className="mt-2 mb-1 text-sm font-semibold">{children}</h3>,
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-primary underline underline-offset-2 hover:opacity-80"
            >
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.8em]">
              {children}
            </code>
          ),
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse text-xs">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-muted/60">{children}</thead>,
          th: ({ children }) => (
            <th className="border px-2 py-1 text-left font-semibold">{children}</th>
          ),
          td: ({ children }) => <td className="border px-2 py-1 align-top">{children}</td>,
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
