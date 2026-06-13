import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Tauri 打包要求前端是纯静态资源：导出到 web/out/，由 Tauri 的 WebView 直接加载。
  // 本项目是单路由纯客户端 SPA，全部数据通过 fetch 调云端后端，满足静态导出前提。
  output: "export",
  // 静态导出下没有 Next 图片优化服务器，关闭优化（项目用的是 lucide SVG，无 next/image，留作保险）。
  images: { unoptimized: true },
};

export default nextConfig;
