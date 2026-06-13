"use client";

import { useEffect, useRef, useState } from "react";

// 软件出场动画：每次启动 App 播一次。
// Tauri 每次打开是新 webview 会话 → 每次启动都播；网页每个标签会话播一次，刷新不重复打扰。
const SEEN_KEY = "mia.intro.seen";

export function Intro() {
  // 初始即显示，保证 App 一启动先看到动画，不会闪过登录/主界面。
  const [show, setShow] = useState(true);
  const [fading, setFading] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const doneRef = useRef(false); // 防止 onEnded/超时/点击 重复触发收尾

  function finish() {
    if (doneRef.current) return;
    doneRef.current = true;
    try {
      sessionStorage.setItem(SEEN_KEY, "1");
    } catch {
      /* 隐私模式下 sessionStorage 可能不可用，忽略 */
    }
    setFading(true);
    setTimeout(() => setShow(false), 500); // 等淡出过渡结束再卸载
  }

  useEffect(() => {
    // 本会话已看过 → 立即收起（不重复播放）
    if (sessionStorage.getItem(SEEN_KEY)) {
      setShow(false);
      return;
    }
    const v = videoRef.current;
    if (v) {
      v.muted = true; // 自动播放策略要求静音；React 的 muted 属性有时不落到 DOM，这里兜底
      v.play().catch(() => finish()); // 自动播放被拦截 → 直接跳过，绝不卡黑屏
    }
    // 兜底：万一视频加载失败 / onEnded 不触发，到时强制收起（视频 ~5s，留足余量）
    const timer = setTimeout(finish, 7000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!show) return null;

  return (
    <div
      onClick={finish}
      role="presentation"
      // 底色取自动画实际背景(浅灰渐变 #D7D6D9→#AAB0B6),让非 16:9 屏幕上的留白与画面无缝衔接，
      // 也避免视频解码前的一瞬黑屏。
      style={{ background: "linear-gradient(135deg, #DAD9DC 0%, #AFB1B6 100%)" }}
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
        // cover 铺满全屏：动画主体居中、两侧是大片空白背景，裁掉的只是空白，
        // 竖屏手机也无黑边/接缝，logo 与文案完整可见。
        className="h-full w-full object-cover"
      />
      <button
        onClick={(e) => {
          e.stopPropagation();
          finish();
        }}
        className="absolute bottom-6 right-6 rounded-full border border-black/10 bg-black/5 px-4 py-1.5 text-xs text-neutral-600 backdrop-blur-sm transition-colors hover:bg-black/10 hover:text-neutral-900"
      >
        跳过
      </button>
    </div>
  );
}
