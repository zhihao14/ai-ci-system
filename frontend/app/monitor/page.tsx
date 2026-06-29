// app/monitor/page.tsx — Glassmorphism 实时监控页面
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import { Loader2, Radio, Zap } from "lucide-react";
import RealtimeStatus from "@/components/monitor/RealtimeStatus";
import { Button } from "@/components/ui/button";

export default function MonitorPage() {
  const router = useRouter();
  const [triggering, setTriggering] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);

  const handleTrigger = async () => {
    setTriggering(true);
    setRunResult(null);
    try {
      const res = await fetch("/be/monitor/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_accounts: 20, max_videos: 10, analyze: true }),
      });
      const data = await res.json();
      setRunResult(`监控轮次已触发, 扫描 ${data.stats?.total || 0} 个账号`);
    } catch (e) {
      setRunResult(`请求失败: ${e}`);
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div className="relative z-10 min-h-screen overflow-hidden">
      {/* 顶栏 */}
      <motion.header
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-dark flex h-14 items-center justify-between px-6"
      >
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 shadow-lg shadow-emerald-500/20">
            <Radio className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-semibold text-white">实时监控</span>
        </div>
        <Button variant="glass" size="sm" onClick={() => router.push("/dashboard")}>
          Dashboard →
        </Button>
      </motion.header>

      <main className="mx-auto max-w-3xl px-6 py-6">
        {/* 触发栏 */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-border mb-4 flex items-center justify-between p-5"
        >
          <div>
            <h2 className="text-sm font-semibold text-white">自动监控调度</h2>
            <p className="mt-0.5 text-xs text-slate-500">
              手动触发一轮监控, 实时查看采集和分析进度
            </p>
          </div>
          <Button onClick={handleTrigger} disabled={triggering}>
            {triggering ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Zap className="w-3.5 h-3.5" />
            )}
            {triggering ? "触发中..." : "立即监控"}
          </Button>
        </motion.div>

        {/* 触发结果 */}
        {runResult && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass mb-4 rounded-xl bg-brand-500/10 px-4 py-2.5 text-sm text-brand-300"
          >
            {runResult}
          </motion.div>
        )}

        {/* 实时状态 */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-border p-6"
        >
          <h3 className="mb-4 text-sm font-semibold text-white">实时状态</h3>
          <RealtimeStatus />
        </motion.div>
      </main>
    </div>
  );
}
