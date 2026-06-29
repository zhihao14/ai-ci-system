// components/dashboard/Sidebar.tsx — Glassmorphism 侧边栏 + Framer Motion
"use client";

import { motion } from "framer-motion";
import { LayoutDashboard, Users, Video, Flame, Sparkles, Radio } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export type NavKey = "overview" | "accounts" | "videos" | "viral" | "monitor";

interface NavItem {
  key: NavKey;
  label: string;
  icon: React.ReactNode;
  badge?: number;
  gradient: string;
}

export default function Sidebar({
  active,
  onNavigate,
  accountCount,
  videoCount,
}: {
  active: NavKey;
  onNavigate: (key: NavKey) => void;
  accountCount: number;
  videoCount: number;
}) {
  const items: NavItem[] = [
    { key: "overview", label: "概览", icon: <LayoutDashboard className="w-[18px] h-[18px]" />, gradient: "from-indigo-500 to-blue-500" },
    { key: "accounts", label: "账号", icon: <Users className="w-[18px] h-[18px]" />, badge: accountCount, gradient: "from-purple-500 to-pink-500" },
    { key: "videos", label: "视频", icon: <Video className="w-[18px] h-[18px]" />, badge: videoCount, gradient: "from-cyan-500 to-blue-500" },
    { key: "viral", label: "爆款分析", icon: <Flame className="w-[18px] h-[18px]" />, gradient: "from-orange-500 to-red-500" },
    { key: "monitor", label: "实时监控", icon: <Radio className="w-[18px] h-[18px]" />, gradient: "from-emerald-500 to-teal-500" },
  ];

  return (
    <aside className="glass-dark flex w-[240px] shrink-0 flex-col rounded-r-3xl">
      {/* Logo */}
      <motion.div
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5 }}
        className="flex items-center gap-3 px-5 py-5"
      >
        <div className="relative">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-purple-600 shadow-lg shadow-brand-500/30">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div className="absolute inset-0 rounded-xl bg-brand-400/30 blur-lg -z-10" />
        </div>
        <div>
          <span className="gradient-text text-[15px] font-bold tracking-tight">CI Insight</span>
          <p className="text-[10px] text-slate-500">AI Competitive Intelligence</p>
        </div>
      </motion.div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-2">
        <p className="mb-2 px-3 text-[10px] font-medium uppercase tracking-wider text-slate-500">
          导航
        </p>
        <div className="space-y-1">
          {items.map((item, i) => {
            const isActive = active === item.key;
            return (
              <motion.button
                key={item.key}
                onClick={() => onNavigate(item.key)}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 + 0.1 }}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                className={`group relative flex w-full items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium transition-all ${
                  isActive
                    ? "text-white"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {/* 激活态背景 */}
                {isActive && (
                  <motion.div
                    layoutId="active-nav"
                    className="absolute inset-0 rounded-xl bg-gradient-to-r from-white/10 to-white/5 border border-white/10"
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  />
                )}
                {/* 图标 */}
                <span className={`relative z-10 flex h-7 w-7 items-center justify-center rounded-lg transition-all ${
                  isActive
                    ? `bg-gradient-to-br ${item.gradient} shadow-lg`
                    : "bg-white/5 group-hover:bg-white/10"
                }`}>
                  {item.icon}
                </span>
                <span className="relative z-10 flex-1 text-left">{item.label}</span>
                {item.badge !== undefined && item.badge > 0 && (
                  <Badge variant={isActive ? "gradient" : "glass"} className="relative z-10">
                    {item.badge}
                  </Badge>
                )}
                {/* 激活态左侧光条 */}
                {isActive && (
                  <motion.div
                    layoutId="active-indicator"
                    className={`absolute -left-3 top-1/2 h-8 w-1 -translate-y-1/2 rounded-full bg-gradient-to-b ${item.gradient}`}
                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                  />
                )}
              </motion.button>
            );
          })}
        </div>
      </nav>

      {/* Footer */}
      <div className="border-t border-white/5 px-4 py-3">
        <div className="glass flex items-center gap-2.5 rounded-xl px-3 py-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-gradient-to-br from-brand-400 to-purple-600 text-[11px] font-bold text-white">
            A
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-[12px] font-medium text-slate-300">Admin</p>
            <p className="truncate text-[10px] text-slate-500">竞争情报系统</p>
          </div>
          <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
        </div>
      </div>
    </aside>
  );
}
