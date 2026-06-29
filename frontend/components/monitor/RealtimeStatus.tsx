// components/monitor/RealtimeStatus.tsx — Glassmorphism 实时状态组件
"use client";

import { motion, AnimatePresence } from "framer-motion";
import { Loader2, CheckCircle2, XCircle, Brain, Radio, Sparkles, Zap } from "lucide-react";
import { useMonitorWebSocket, type AccountStatus } from "@/lib/useWebSocket";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

// 阶段图标 + 颜色
const STAGE_CONFIG = {
  idle: { icon: Radio, color: "text-slate-400", bg: "from-slate-500 to-slate-600" },
  crawling: { icon: Loader2, color: "text-blue-400", bg: "from-blue-500 to-cyan-500" },
  crawl_done: { icon: CheckCircle2, color: "text-emerald-400", bg: "from-emerald-500 to-teal-500" },
  analyzing: { icon: Brain, color: "text-purple-400", bg: "from-purple-500 to-fuchsia-500" },
  analysis_done: { icon: CheckCircle2, color: "text-emerald-400", bg: "from-emerald-500 to-teal-500" },
  done: { icon: Sparkles, color: "text-brand-400", bg: "from-brand-500 to-purple-500" },
} as const;

const STATUS_BADGE = {
  crawling: { label: "采集", variant: "default" as const },
  crawl_done: { label: "完成", variant: "success" as const },
  analyzing: { label: "分析", variant: "gradient" as const },
  analysis_done: { label: "完成", variant: "success" as const },
  error: { label: "失败", variant: "danger" as const },
} as const;

const PLATFORM_ICON: Record<string, string> = {
  douyin: "🎵",
  xiaohongshu: "📕",
  youtube: "▶",
  tiktok: "🎵",
};

export default function RealtimeStatus() {
  const { state } = useMonitorWebSocket();

  const stage = STAGE_CONFIG[state.current_stage as keyof typeof STAGE_CONFIG] || STAGE_CONFIG.idle;
  const StageIcon = stage.icon;

  return (
    <div className="space-y-4">
      {/* 连接状态 */}
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-2">
          <motion.span
            className="h-2.5 w-2.5 rounded-full"
            style={{ background: state.connected ? "#10b981" : "#64748b" }}
            animate={state.connected ? { scale: [1, 1.2, 1], opacity: [1, 0.6, 1] } : {}}
            transition={{ duration: 1.5, repeat: Infinity }}
          />
          <span className="text-sm text-slate-400">
            {state.connected ? "WebSocket 已连接" : "未连接"}
          </span>
        </div>
        <AnimatePresence mode="wait">
          {state.is_monitoring && (
            <motion.div
              key={state.current_stage}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
            >
              <Badge variant="gradient">
                <StageIcon className={cn("w-3 h-3 mr-1", state.current_stage === "crawling" && "animate-spin")} />
                {state.current_stage}
              </Badge>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>

      {/* 进度卡片 */}
      <AnimatePresence>
        {state.is_monitoring && (
          <motion.div
            initial={{ opacity: 0, y: 10, height: 0 }}
            animate={{ opacity: 1, y: 0, height: "auto" }}
            exit={{ opacity: 0, y: -10, height: 0 }}
            className="glass-border overflow-hidden p-4"
          >
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <motion.div
                  className={cn("flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br shadow-lg", stage.bg)}
                  animate={{ boxShadow: ["0 0 10px rgba(99,102,241,0.3)", "0 0 20px rgba(139,92,246,0.5)", "0 0 10px rgba(99,102,241,0.3)"] }}
                  transition={{ duration: 2, repeat: Infinity }}
                >
                  <StageIcon className={cn("w-4 h-4 text-white", state.current_stage === "crawling" && "animate-spin")} />
                </motion.div>
                <div>
                  <span className="text-sm font-semibold text-white">
                    {state.current_index}/{state.total_accounts}
                  </span>
                  <span className="ml-1 text-xs text-slate-500">账号</span>
                </div>
              </div>
              <span className="text-xs text-brand-300">
                {state.total_accounts > 0
                  ? Math.round((state.current_index / state.total_accounts) * 100)
                  : 0}%
              </span>
            </div>
            <Progress
              value={state.total_accounts > 0 ? (state.current_index / state.total_accounts) * 100 : 0}
              color="linear-gradient(90deg, #6366f1, #8b5cf6, #d946ef)"
            />
            <p className="mt-2 text-sm text-slate-300">
              <StageIcon className={cn("w-3.5 h-3.5 inline mr-1.5", state.current_stage === "crawling" && "animate-spin")} />
              {state.current_account || "..."}
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 统计卡片 */}
      <AnimatePresence>
        {(state.stats.new_videos > 0 || state.stats.analyzed > 0 || state.is_monitoring) && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            className="grid grid-cols-4 gap-3"
          >
            {[
              { label: "新视频", value: state.stats.new_videos, gradient: "from-blue-500/20 to-cyan-500/10", text: "text-blue-300" },
              { label: "已分析", value: state.stats.analyzed, gradient: "from-purple-500/20 to-fuchsia-500/10", text: "text-purple-300" },
              { label: "Token", value: state.stats.total_tokens, gradient: "from-amber-500/20 to-orange-500/10", text: "text-amber-300" },
              { label: "失败", value: state.stats.failed, gradient: "from-red-500/20 to-rose-500/10", text: "text-red-300" },
            ].map((stat, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className={cn("glass rounded-xl bg-gradient-to-br p-3 text-center", stat.gradient)}
              >
                <motion.p
                  key={stat.value}
                  initial={{ scale: 0.5, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  className={cn("text-xl font-bold", stat.text)}
                >
                  {stat.value}
                </motion.p>
                <p className="mt-0.5 text-[10px] text-slate-400">{stat.label}</p>
              </motion.div>
            ))}
          </motion.div>
        )}
      </AnimatePresence>

      {/* 账号状态列表 */}
      <AnimatePresence>
        {state.accounts.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
              账号监控状态
            </h4>
            <div className="space-y-1.5">
              <AnimatePresence>
                {state.accounts.slice(0, 10).map((acc, i) => {
                  const badge = STATUS_BADGE[acc.status as keyof typeof STATUS_BADGE];
                  return (
                    <motion.div
                      key={acc.name + i}
                      layout
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 20 }}
                      transition={{ delay: i * 0.03 }}
                      whileHover={{ scale: 1.02 }}
                      className="glass flex items-center justify-between rounded-xl px-3 py-2"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="text-sm">{PLATFORM_ICON[acc.platform] || "📱"}</span>
                        <span className="text-sm text-slate-200">{acc.name}</span>
                        {(acc.status === "crawling" || acc.status === "analyzing") && (
                          <Loader2 className="w-3 h-3 animate-spin text-brand-400" />
                        )}
                        {acc.status === "error" && (
                          <XCircle className="w-3 h-3 text-red-400" />
                        )}
                        {acc.status === "crawl_done" && (
                          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                        )}
                        {acc.status === "analysis_done" && (
                          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {acc.crawled !== undefined && (
                          <span className="text-[10px] text-slate-500">
                            {acc.new_count} 新 / {acc.crawled} 条
                          </span>
                        )}
                        {acc.tokens !== undefined && acc.tokens > 0 && (
                          <span className="text-[10px] text-amber-500/70">{acc.tokens} tok</span>
                        )}
                        {badge && (
                          <Badge variant={badge.variant} className="text-[10px]">
                            {badge.label}
                          </Badge>
                        )}
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 实时事件流 */}
      <AnimatePresence>
        {state.events.length > 0 && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <h4 className="mb-2 text-xs font-medium uppercase tracking-wider text-slate-500">
              实时事件
            </h4>
            <div className="max-h-48 space-y-1 overflow-y-auto">
              <AnimatePresence initial={false}>
                {state.events.slice(0, 15).map((ev, i) => (
                  <motion.div
                    key={i + (ev.timestamp || "")}
                    initial={{ opacity: 0, y: -10, height: 0 }}
                    animate={{ opacity: 1, y: 0, height: "auto" }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className={cn(
                      "flex items-start gap-2 rounded-lg px-3 py-1.5 text-xs",
                      ev.type === "error" ? "bg-red-500/10" : "bg-white/5"
                    )}
                  >
                    <span className="shrink-0 text-slate-500">
                      {ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString("zh-CN") : ""}
                    </span>
                    <span className={cn(
                      "flex-1",
                      ev.type === "error" ? "text-red-300" : "text-slate-400"
                    )}>
                      {ev.message}
                    </span>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* 空状态 */}
      {!state.is_monitoring && state.events.length === 0 && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="py-16 text-center"
        >
          <motion.div
            animate={{ y: [0, -8, 0] }}
            transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
            className="mb-3 inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500/20 to-purple-500/20"
          >
            <Radio className="w-8 h-8 text-brand-400" />
          </motion.div>
          <p className="text-sm text-slate-400">等待监控事件...</p>
          <p className="mt-1 text-xs text-slate-600">触发监控后, 实时状态将在此显示</p>
        </motion.div>
      )}

      {/* 完成动画 */}
      <AnimatePresence>
        {state.current_stage === "done" && (
          <motion.div
            initial={{ opacity: 0, scale: 0.5 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0 }}
            className="glass-border flex items-center justify-center gap-2 p-4"
          >
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 200, delay: 0.1 }}
            >
              <CheckCircle2 className="w-6 h-6 text-emerald-400" />
            </motion.div>
            <span className="text-sm font-medium text-white">监控完成</span>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
