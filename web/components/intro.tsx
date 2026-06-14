"use client";

import { useEffect, useRef, useState } from "react";

// 软件出场动画：每次启动 App 播一次视频。
// Tauri 每次打开是新 webview 会话 → 每次启动都播；网页同一标签会话内只播一次(刷新不重复打扰)，
// 关标签后重开 / 新标签 / 无痕窗口算新会话会再播。带 ?intro=1 或 #intro 可强制重播(测试/分享)。
const SEEN_KEY = "mia.intro.seen";

export function Intro() {
  // 关键：默认 false。若初始就显示，再在 effect 里发现"已看过"而隐藏，会闪一帧。
  // 所以挂载后(能读 sessionStorage 时)再决定是否播放。
  const [show, setShow] = useState(false);
  const [fading, setFading] = useState(false);
  const [ready, setReady] = useState(false); // 视频真正开始播帧才显示，避免露出缓冲中的怪异首帧
  const videoRef = useRef<HTMLVideoElement>(null);
  const doneRef = useRef(false); // 防止 onEnded/超时/点击 重复触发收尾
  const durRef = useRef(0);
  const endTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function finish() {
    if (doneRef.current) return;
    doneRef.current = true;
    if (endTimer.current) clearTimeout(endTimer.current);
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
      // 主动播放；即便被浏览器拦截也不立即收尾(避免一闪而过)，交给 onPlaying/onEnded/兜底处理。
      v.play().catch(() => {});
    }
    // 硬兜底：极端情况下(完全无法播且事件都不触发)，最长 15s 后强制收起。
    // 比视频时长(~5s)+缓冲留足余量，避免把"还在缓冲、即将播放"的视频提前掐成"一闪进主页"。
    const hard = setTimeout(finish, 15000);
    return () => clearTimeout(hard);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [show]);

  if (!show) return null;

  return (
    <div
      onClick={finish}
      role="presentation"
      // 填充背景：纯白。缓冲期间只露这层白底(而非视频的黑底/怪异首帧)。
      style={{ background: "#ffffff" }}
      className={`fixed inset-0 z-[100] flex items-center justify-center transition-opacity duration-500 ${
        fading ? "opacity-0" : "opacity-100"
      }`}
    >
      {/* 视频缓冲期间(尤其国内加载慢)显示小加载转圈，避免长时间白屏；视频一播(ready)即淡出。 */}
      <div
        className={`pointer-events-none absolute inset-0 flex items-center justify-center transition-opacity duration-300 ${
          ready ? "opacity-0" : "opacity-100"
        }`}
      >
        <span className="size-8 animate-spin rounded-full border-2 border-zinc-200 border-t-zinc-500" />
      </div>
      <video
        ref={videoRef}
        src="/intro.mp4"
        autoPlay
        muted
        playsInline
        preload="auto"
        onLoadedMetadata={(e) => {
          durRef.current = e.currentTarget.duration;
        }}
        onPlaying={() => {
          setReady(true); // 真正开始播帧 → 淡入(此前 opacity:0，只露白底，不露缓冲怪首帧)
          const d = durRef.current;
          if (d && isFinite(d) && !endTimer.current) {
            // 以视频时长为准收尾，防 onEnded 在个别 webview 不触发而干等硬兜底。
            endTimer.current = setTimeout(finish, d * 1000 + 800);
          }
        }}
        onEnded={finish}
        onError={finish}
        // 视频最多占视口 75%(电脑端按高、手机端按宽各约 75%)，居中、四周留白 → 更小更清楚。
        // contain 保持比例不裁切；opacity 受 ready 控制：缓冲/未就绪时透明，播起来才淡入。
        className="max-h-[75%] max-w-[75%] object-contain transition-opacity duration-300"
        style={{ opacity: ready ? 1 : 0 }}
      />
    </div>
  );
}
