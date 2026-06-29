// components/profile/UsageTab.tsx — API 调用记录
"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

interface UsageRecord {
  id: string;
  endpoint: string;
  method: string;
  status_code: number;
  prompt_tokens: number;
  completion_tokens: number;
  called_at: string;
}

export default function UsageTab() {
  const { session } = useAuth();
  const [records, setRecords] = useState<UsageRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [endpointFilter, setEndpointFilter] = useState("");

  const fetchUsage = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ limit: "50" });
      if (endpointFilter) params.set("endpoint", endpointFilter);
      const res = await fetch(`/be/auth/usage?${params}`, {
        headers: { Authorization: `Bearer ${session?.access_token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setRecords(data.items || []);
        setTotal(data.total || 0);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsage();
  }, []);

  const statusColor = (code: number) => {
    if (code >= 200 && code < 300) return "text-green-600 bg-green-50";
    if (code >= 400 && code < 500) return "text-amber-600 bg-amber-50";
    if (code >= 500) return "text-red-600 bg-red-50";
    return "text-slate-600 bg-slate-50";
  };

  return (
    <div className="space-y-4">
      {/* 筛选 */}
      <div className="flex items-center gap-2">
        <input
          value={endpointFilter}
          onChange={(e) => setEndpointFilter(e.target.value)}
          placeholder="按 endpoint 筛选 (如 /pipeline)"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-brand-500"
          onKeyDown={(e) => e.key === "Enter" && fetchUsage()}
        />
        <button
          onClick={fetchUsage}
          className="rounded-lg bg-brand-600 px-4 py-1.5 text-sm text-white hover:bg-brand-700"
        >
          查询
        </button>
      </div>

      <div className="text-xs text-slate-400">
        共 {total} 条记录, 显示最近 {records.length} 条
      </div>

      {/* 表格 */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs text-slate-400">
              <th className="px-3 py-2 text-left font-normal">时间</th>
              <th className="px-3 py-2 text-left font-normal">Endpoint</th>
              <th className="px-3 py-2 text-center font-normal">方法</th>
              <th className="px-3 py-2 text-center font-normal">状态</th>
              <th className="px-3 py-2 text-right font-normal">Prompt</th>
              <th className="px-3 py-2 text-right font-normal">Completion</th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr key={r.id} className="border-b border-slate-50 hover:bg-slate-50">
                <td className="px-3 py-2 text-xs text-slate-500">
                  {new Date(r.called_at).toLocaleString("zh-CN")}
                </td>
                <td className="px-3 py-2 font-mono text-xs text-slate-700">{r.endpoint}</td>
                <td className="px-3 py-2 text-center text-xs text-slate-500">{r.method}</td>
                <td className="px-3 py-2 text-center">
                  <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${statusColor(r.status_code)}`}>
                    {r.status_code}
                  </span>
                </td>
                <td className="px-3 py-2 text-right text-xs text-slate-500">
                  {r.prompt_tokens || "-"}
                </td>
                <td className="px-3 py-2 text-right text-xs text-slate-500">
                  {r.completion_tokens || "-"}
                </td>
              </tr>
            ))}
            {records.length === 0 && (
              <tr>
                <td colSpan={6} className="py-8 text-center text-sm text-slate-400">
                  {loading ? "加载中..." : "暂无调用记录"}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
