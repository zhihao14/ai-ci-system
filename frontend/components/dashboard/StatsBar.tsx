// components/dashboard/StatsBar.tsx — 动画统计卡片 (Glassmorphism + Framer Motion + Recharts)
"use client";

import { motion } from "framer-motion";
import { Users, Video, Heart, Flame, TrendingUp, Sparkles } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { cn, formatNumber } from "@/lib/utils";

interface Stats {
  accountCount: number;
  videoCount: number;
  totalLikes: number;
  analysisCount: number;
}

// 生成迷你 sparkline 数据
function genSpark(seed: number, base: number) {
  return Array.from({ length: 8 }, (_, i) => ({
    v: Math.max(0, base + Math.sin(i * 0.8 + seed) * base * 0.3 + (Math.random() - 0.5) * base * 0.2),
  }));
}

export default function StatsBar({ stats }: { stats: Stats }) {
  const cards = [
    {
      label: "监控账号",
      value: stats.accountCount,
      icon: Users,
      gradient: "from-indigo-500 to-blue-500",
      glow: "shadow-indigo-500/20",
      chart: genSpark(1, 10),
      chartColor: "#818cf8",
      suffix: "",
    },
    {
      label: "视频总数",
      value: stats.videoCount,
      icon: Video,
      gradient: "from-cyan-500 to-blue-500",
      glow: "shadow-cyan-500/20",
      chart: genSpark(2, 20),
      chartColor: "#22d3ee",
      suffix: "",
    },
    {
      label: "累计点赞",
      value: formatNumber(stats.totalLikes),
      icon: Heart,
      gradient: "from-rose-500 to-pink-500",
      glow: "shadow-rose-500/20",
      chart: genSpark(3, 50),
      chartColor: "#fb7185",
      suffix: "",
    },
    {
      label: "AI 分析",
      value: stats.analysisCount,
      icon: Flame,
      gradient: "from-orange-500 to-red-500",
      glow: "shadow-orange-500/20",
      chart: genSpark(4, 5),
      chartColor: "#fb923c",
      suffix: "",
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
      {cards.map((c, i) => {
        const Icon = c.icon;
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.1, duration: 0.5 }}
            whileHover={{ y: -4, scale: 1.02 }}
            className="glass-border group relative overflow-hidden p-4"
          >
            {/* 发光背景 */}
            <div
              className={cn(
                "absolute -right-8 -top-8 h-24 w-24 rounded-full bg-gradient-to-br opacity-20 blur-2xl transition-opacity group-hover:opacity-40",
                c.gradient
              )}
            />

            {/* 图标 */}
            <div className="relative flex items-center justify-between">
              <div
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br shadow-lg",
                  c.gradient,
                  c.glow
                )}
              >
                <Icon className="w-5 h-5 text-white" />
              </div>
              <div className="flex items-center gap-1 text-[10px] text-emerald-400">
                <TrendingUp className="w-3 h-3" />
                <span>+12%</span>
              </div>
            </div>

            {/* 数值 */}
            <div className="relative mt-3">
              <motion.p
                key={c.value}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.1 + 0.3 }}
                className="text-2xl font-bold tracking-tight text-white"
              >
                {c.value}
                {c.suffix}
              </motion.p>
              <p className="text-[12px] text-slate-400">{c.label}</p>
            </div>

            {/* Sparkline */}
            <div className="relative mt-2 h-8">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={c.chart}>
                  <defs>
                    <linearGradient id={`spark-${i}`} x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={c.chartColor} stopOpacity={0.4} />
                        <stop offset="100%" stopColor={c.chartColor} stopOpacity={0} />
                      </linearGradient>
                  </defs>
                  <Area
                    type="monotone"
                    dataKey="v"
                    stroke={c.chartColor}
                    strokeWidth={1.5}
                    fill={`url(#spark-${i})`}
                    isAnimationActive={true}
                    animationDuration={1000}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
