// 相对时间：后端 added_at/updated_at 为秒级时间戳(time.time())。
export function relativeTime(ts: number): string {
  if (!ts) return "";
  const ms = ts < 1e12 ? ts * 1000 : ts;
  const diff = Date.now() - ms;
  const s = Math.floor(diff / 1000);
  if (s < 60) return "just now";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(ms).toLocaleDateString("en-US");
}
