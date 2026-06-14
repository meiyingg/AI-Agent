"use client";

import { useEffect, useRef, useState } from "react";

// 软件出场动画：每次启动 App 播一次。
// Tauri 每次打开是新 webview 会话 → 每次启动都播；网页同一标签会话内只播一次(刷新不重复打扰)，
// 关标签后重开 / 新标签 / 无痕窗口算新会话会再播。带 ?intro=1 或 #intro 可强制重播(测试/分享)。
const SEEN_KEY = "mia.intro.seen";

export function Intro() {
  // 关键：默认 false。若初始就显示，再在 effect 里发现"已看过"而隐藏，会闪一帧。
  // 所以挂载后(能读 sessionStorage 时)再决定是否播放。
  const [show, setShow] = useState(false);
  const [fading, setFading] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const doneRef = useRef(false); // 防止 onEnded/超时/点击 重复触发收尾

  function finish() {
    if (doneRef.current) return;
    doneRef.current = true;
    try {
      sessionStorage.setItem(SEEN_KEY, "1");
    } catch {
      /* 隐私模式下 sessionStorage 不可用，忽略 */
    }
    setFading(true);
    setTimeout(() => setShow(false), 500); // 等淡出过渡结束再卸载
  }

  // 挂载后判断是否播放：本会话没看过、或被 ?intro 强制 → 显示。
  useEffect(() => {
    let seen = false;
    try {
      seen = !!sessionStorage.getItem(SEEN_KEY);
    } catch {
      /* ignore */
    }
    const params = new URLSearchParams(window.location.search);
    const forced = params.has("intro") || window.location.hash === "#intro";
    if (forced || !seen) setShow(true);
  }, []);

  // show 变 true、<video> 挂载后再触发播放 + 兜底超时。
  useEffect(() => {
    if (!show) return;
    const v = videoRef.current;
    if (v) {
      v.muted = true; // 自动播放策略要求静音；React 的 muted 属性有时不落 DOM，这里兜底
      // 主动播放；即便被浏览器拦截也不立即收尾(避免一闪而过)，交给 onEnded / 兜底超时处理。
      v.play().catch(() => {});
    }
    // 兜底：万一 onEnded 不触发(加载慢等)，到时强制收起。视频约 5s，留足余量。
    const timer = setTimeout(finish, 8000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [show]);

  if (!show) return null;

  return (
    <div
      onClick={finish}
      role="presentation"
      // 填充背景：纯白。
      style={{ background: "#ffffff" }}
      className={`fixed inset-0 z-[100] flex items-center justify-center transition-opacity duration-500 ${
        fading ? "opacity-0" : "opacity-100"
      }`}
    >
      <video
        ref={videoRef}
        src="/intro.mp4"
        autoPlay
        muted
        playsInline
        preload="auto"
        onEnded={finish}
        onError={finish}
        // contain 完整显示动画(不放大裁切)：非 16:9 屏幕(尤其手机竖屏)上下留浅灰边，
        // 与视频背景同色、融合自然；保证 logo 与文案完整可见。
        className="h-full w-full object-contain"
      />
    </div>
  );
}
