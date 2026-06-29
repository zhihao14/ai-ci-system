// lib.ts - Dashboard 工具函数

// 数字格式化: 1000 -> 1k, 10000 -> 1w
export function formatNumber(n: number): string {
  if (n >= 100000000) return (n / 100000000).toFixed(1).replace(".0", "") + "亿";
  if (n >= 10000) return (n / 10000).toFixed(1).replace(".0", "") + "w";
  if (n >= 1000) return (n / 1000).toFixed(1).replace(".0", "") + "k";
  return String(n);
}

// 时间格式化
export function formatDate(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" });
}

export function formatDateTime(s: string | null): string {
  if (!s) return "—";
  const d = new Date(s);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("zh-CN", {
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

// 平台徽标颜色
export function platformColor(p: string): string {
  switch (p.toLowerCase()) {
    case "douyin": return "bg-slate-900 text-white";
    case "tiktok": return "bg-slate-800 text-white";
    case "youtube": return "bg-red-50 text-red-600";
    case "bilibili": return "bg-pink-50 text-pink-600";
    default: return "bg-slate-100 text-slate-600";
  }
}

// 互动率
export function engagementRate(v: { like_count: number; view_count: number }): string {
  if (!v.view_count || v.view_count === 0) return "—";
  return ((v.like_count / v.view_count) * 100).toFixed(1) + "%";
}
