// components/profile/QuotaTab.tsx — API 额度展示
"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

interface Quota {
  tenant_id: string;
  plan: string;
  daily_quota: number;
  monthly_quota: number;
  today_used: number;
  month_used: number;
  today_remaining: number;
  month_remaining: number;
  today_reset_at: string;
}

export default function QuotaTab() {
  const { session, tenant } = useAuth();
  const [quota, setQuota] = useState<Quota | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchQuota = async () => {
    try {
      const res = await fetch("/be/auth/quota", {
        headers: { Authorization: `Bearer ${session?.access_token}` },
      });
      if (res.ok) setQuota(await res.json());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQuota();
  }, [tenant?.id]);

  if (loading) return <div className="py-8 text-center text-sm text-slate-400">加载中...</div>;
  if (!quota) return <div className="py-8 text-center text-sm text-slate-400">暂无额度数据</div>;

  const dailyPct = Math.min(100, (quota.today_used / quota.daily_quota) * 100);
  const monthlyPct = Math.min(100, (quota.month_used / quota.monthly_quota) * 100);

  const planColors: Record<string, string> = {
    free: "bg-slate-100 text-slate-600",
    pro: "bg-blue-50 text-blue-600",
    enterprise: "bg-purple-50 text-purple-600",
  };

  return (
    <div className="space-y-6">
      {/* Plan 信息 */}
      <div className="flex items-center justify-between">
        <div>
          <span className="text-sm font-semibold text-slate-900">当前套餐</span>
          <span
            className={`ml-2 rounded px-2 py-0.5 text-xs font-medium ${
              planColors[quota.plan] || planColors.free
            }`}
          >
            {quota.plan}
          </span>
        </div>
        <button
          onClick={fetchQuota}
          className="text-sm text-slate-400 hover:text-slate-600"
        >
          刷新
        </button>
      </div>

      {/* 日额度 */}
      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-sm font-medium text-slate-700">今日用量</span>
          <span className="text-sm text-slate-500">
            {quota.today_used} / {quota.daily_quota} 次
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full transition-all ${
              dailyPct >= 90 ? "bg-red-500" : dailyPct >= 70 ? "bg-amber-500" : "bg-brand-500"
            }`}
            style={{ width: `${dailyPct}%` }}
          />
        </div>
        <div className="mt-1 flex justify-between text-xs text-slate-400">
          <span>剩余 {quota.today_remaining} 次</span>
          <span>重置: {new Date(quota.today_reset_at).toLocaleString("zh-CN")}</span>
        </div>
      </div>

      {/* 月额度 */}
      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-sm font-medium text-slate-700">本月用量</span>
          <span className="text-sm text-slate-500">
            {quota.month_used} / {quota.monthly_quota} 次
          </span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full transition-all ${
              monthlyPct >= 90 ? "bg-red-500" : monthlyPct >= 70 ? "bg-amber-500" : "bg-brand-500"
            }`}
            style={{ width: `${monthlyPct}%` }}
          />
        </div>
        <div className="mt-1 text-xs text-slate-400">
          剩余 {quota.month_remaining} 次
        </div>
      </div>

      {/* 说明 */}
      <div className="rounded-lg bg-slate-50 p-4 text-xs text-slate-500">
        <p className="mb-1 font-medium text-slate-600">额度说明:</p>
        <p>· 每次 API 调用 (爬虫/分析/策略生成) 消耗 1 次额度</p>
        <p>· 日额度每天 00:00 (北京时间) 重置</p>
        <p>· 月额度按自然月计算</p>
        <p>· 超出额度返回 HTTP 429, 可升级套餐获取更多调用次数</p>
      </div>
    </div>
  );
}
