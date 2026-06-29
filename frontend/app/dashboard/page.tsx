"use client";

// dashboard/page.tsx — Glassmorphism Dashboard (Framer Motion + Recharts)
import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, Cell, Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis } from "recharts";
import { Plus, Zap, Loader2, CheckCircle2, XCircle, Activity, Radio, Video as VideoIcon } from "lucide-react";
import Sidebar, { type NavKey } from "@/components/dashboard/Sidebar";
import StatsBar from "@/components/dashboard/StatsBar";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn, formatNumber } from "@/lib/utils";
import type { Account, Video, ViralAnalysis, ModelOption } from "./types";

// ============================================================
// 模拟图表数据
// ============================================================
const platformData = [
  { name: "抖音", value: 45, color: "#a78bfa" },
  { name: "小红书", value: 30, color: "#f472b6" },
  { name: "YouTube", value: 15, color: "#ef4444" },
  { name: "TikTok", value: 10, color: "#22d3ee" },
];

const radarData = [
  { metric: "互动率", value: 85 },
  { metric: "完播率", value: 72 },
  { metric: "转发率", value: 68 },
  { metric: "涨粉率", value: 91 },
  { metric: "爆款率", value: 76 },
  { metric: "转化率", value: 64 },
];

export default function DashboardPage() {
  const [nav, setNav] = useState<NavKey>("overview");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [videos, setVideos] = useState<Video[]>([]);
  const [analysis, setAnalysis] = useState<ViralAnalysis | null>(null);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [selectedModel, setSelectedModel] = useState("auto");
  const [activeAccountId, setActiveAccountId] = useState<string | null>(null);
  const [videosLoading, setVideosLoading] = useState(false);
  const [crawling, setCrawling] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: "ok" | "err" } | null>(null);
  const [selectedVideoIds, setSelectedVideoIds] = useState<Set<string>>(new Set());

  const fetchAccounts = useCallback(async () => {
    try {
      const res = await fetch("/be/accounts/accounts");
      if (res.ok) setAccounts(await res.json());
    } catch {}
  }, []);

  const fetchVideos = useCallback(async (accountId: string) => {
    setVideosLoading(true);
    try {
      const res = await fetch(`/be/accounts/videos/${accountId}`);
      if (res.ok) setVideos(await res.json());
      else setVideos([]);
    } catch { setVideos([]); }
    finally { setVideosLoading(false); }
  }, []);

  const fetchModels = useCallback(async () => {
    try {
      const res = await fetch("/be/viral/models");
      if (res.ok) {
        const data = await res.json();
        setModels(data.models || []);
      }
    } catch {}
  }, []);

  useEffect(() => { fetchAccounts(); fetchModels(); }, [fetchAccounts, fetchModels]);

  const showToast = (msg: string, type: "ok" | "err" = "ok") => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  };

  const handleSelectAccount = (id: string) => {
    setActiveAccountId(id);
    fetchVideos(id);
    setNav("videos");
  };

  const handleAddAccount = async (data: { platform: string; platform_uid: string; name: string; follower_count: number }) => {
    const res = await fetch("/be/accounts/add_account", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
    if (!res.ok) throw new Error("添加失败");
    showToast("账号添加成功");
    await fetchAccounts();
  };

  const handleCrawl = async (accountId: string) => {
    setCrawling(true);
    showToast("爬虫已启动...");
    try {
      const res = await fetch("/be/accounts/crawl_account", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ account_id: accountId, max_videos: 20 }) });
      const data = await res.json();
      showToast(`爬取完成, 新增 ${data.crawled} 条`);
      await fetchVideos(accountId);
      await fetchAccounts();
    } catch { showToast("爬取失败", "err"); }
    finally { setCrawling(false); }
  };

  const handleAnalyze = async () => {
    if (selectedVideoIds.size === 0) return;
    setAnalyzing(true); setNav("viral"); setAnalysis(null);
    const selectedVideos = videos.filter(v => selectedVideoIds.has(v.id)).map(v => ({
      title: v.title, like_count: v.like_count, comment_count: v.comment_count,
      share_count: v.share_count, view_count: v.view_count, published_at: v.published_at,
    }));
    try {
      const res = await fetch("/be/viral/analyze_viral", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ videos: selectedVideos, model: selectedModel, save_to_db: true, account_id: activeAccountId }) });
      if (!res.ok) throw new Error("分析失败");
      setAnalysis(await res.json());
      showToast("分析完成");
    } catch { showToast("分析失败", "err"); }
    finally { setAnalyzing(false); }
  };

  const totalLikes = videos.reduce((sum, v) => sum + v.like_count, 0);
  const stats = { accountCount: accounts.length, videoCount: videos.length, totalLikes, analysisCount: analysis ? 1 : 0 };

  return (
    <div className="relative z-10 flex h-screen overflow-hidden">
      <Sidebar active={nav} onNavigate={setNav} accountCount={accounts.length} videoCount={videos.length} />

      <div className="flex flex-1 flex-col overflow-hidden">
        {/* 顶栏 */}
        <motion.header
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-dark flex h-14 shrink-0 items-center justify-between px-6"
        >
          <div className="flex items-center gap-3">
            <h1 className="text-[15px] font-semibold tracking-tight text-white">
              {nav === "overview" && "概览"}
              {nav === "accounts" && "账号管理"}
              {nav === "videos" && "视频数据"}
              {nav === "viral" && "爆款分析"}
              {nav === "monitor" && "实时监控"}
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="glass" size="sm" onClick={() => setNav("monitor")}>
              <Radio className="w-3.5 h-3.5" />
              实时监控
            </Button>
            {models.length > 0 && (
              <select
                value={selectedModel}
                onChange={(e) => setSelectedModel(e.target.value)}
                className="glass rounded-lg px-2.5 py-1 text-[12px] text-slate-300 outline-none cursor-pointer"
              >
                {models.map(m => <option key={m.id} value={m.id} className="bg-slate-900">{m.label}</option>)}
              </select>
            )}
          </div>
        </motion.header>

        {/* 内容区 */}
        <div className="flex-1 overflow-hidden">
          <AnimatePresence mode="wait">
            {nav === "overview" && (
              <motion.div key="overview" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="h-full overflow-y-auto px-6 py-5">
                <StatsBar stats={stats} />

                {/* 图表区 */}
                <div className="mt-5 grid grid-cols-1 gap-4 lg:grid-cols-2">
                  {/* 平台分布 */}
                  <motion.div
                    initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
                    className="glass-border p-5"
                  >
                    <div className="mb-3 flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-white">平台分布</h3>
                      <Badge variant="glass">{accounts.length} 账号</Badge>
                    </div>
                    <div className="h-[200px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={platformData}>
                          <defs>
                            {platformData.map((d, i) => (
                              <linearGradient key={i} id={`bar-${i}`} x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={d.color} stopOpacity={0.8} />
                                <stop offset="100%" stopColor={d.color} stopOpacity={0.2} />
                              </linearGradient>
                            ))}
                          </defs>
                          <XAxis dataKey="name" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} />
                          <Tooltip cursor={{ fill: "rgba(255,255,255,0.05)" }} />
                          <Bar dataKey="value" radius={[8, 8, 0, 0]} animationDuration={1200}>
                            {platformData.map((_, i) => <Cell key={i} fill={`url(#bar-${i})`} />)}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </motion.div>

                  {/* 性能雷达 */}
                  <motion.div
                    initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}
                    className="glass-border p-5"
                  >
                    <div className="mb-3 flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-white">内容性能</h3>
                      <Badge variant="gradient"><Activity className="w-3 h-3 mr-1" /> 实时</Badge>
                    </div>
                    <div className="h-[200px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <RadarChart data={radarData}>
                          <PolarGrid stroke="rgba(255,255,255,0.1)" />
                          <PolarAngleAxis dataKey="metric" tick={{ fill: "#64748b", fontSize: 11 }} />
                          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                          <Radar
                            dataKey="value"
                            stroke="#8b5cf6" strokeWidth={2}
                            fill="rgba(139,92,246,0.2)"
                            animationDuration={1500}
                          />
                        </RadarChart>
                      </ResponsiveContainer>
                    </div>
                  </motion.div>
                </div>

                {/* 账号列表 */}
                <motion.div
                  initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }}
                  className="glass-border mt-4 p-5"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <h3 className="text-sm font-semibold text-white">监控账号</h3>
                    <Button size="sm" variant="glass" onClick={() => setModalOpen(true)}>
                      <Plus className="w-3.5 h-3.5" /> 添加
                    </Button>
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {accounts.length === 0 ? (
                      <p className="col-span-full py-8 text-center text-sm text-slate-500">
                        暂无账号, 点击"添加"开始
                      </p>
                    ) : (
                      accounts.slice(0, 6).map((acc, i) => (
                        <motion.div
                          key={acc.id}
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: i * 0.05 }}
                          whileHover={{ scale: 1.03, y: -2 }}
                          onClick={() => handleSelectAccount(acc.id)}
                          className={cn(
                            "glass cursor-pointer rounded-xl p-3 transition-all",
                            activeAccountId === acc.id && "ring-1 ring-brand-400/50"
                          )}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-purple-500 to-pink-500 text-xs">
                                {acc.platform?.[0]?.toUpperCase() || "U"}
                              </div>
                              <div>
                                <p className="text-sm font-medium text-white">{acc.name}</p>
                                <p className="text-[10px] text-slate-500">{acc.platform}</p>
                              </div>
                            </div>
                            {acc.follower_count > 0 && (
                              <span className="text-xs text-slate-400">{formatNumber(acc.follower_count)}粉</span>
                            )}
                          </div>
                        </motion.div>
                      ))
                    )}
                  </div>
                </motion.div>
              </motion.div>
            )}

            {nav === "videos" && (
              <motion.div key="videos" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} className="grid h-full grid-cols-1 lg:grid-cols-[300px_1fr]">
                {/* 账号选择 */}
                <div className="glass-dark border-r border-white/5 overflow-y-auto p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-400">选择账号</span>
                    <Button size="sm" variant="ghost" onClick={() => setModalOpen(true)}>
                      <Plus className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                  <div className="space-y-2">
                    {accounts.map((acc, i) => (
                      <motion.button
                        key={acc.id}
                        initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.03 }}
                        onClick={() => handleSelectAccount(acc.id)}
                        className={cn(
                          "w-full rounded-xl p-3 text-left transition-all",
                          activeAccountId === acc.id ? "glass-border ring-1 ring-brand-400/30" : "hover:bg-white/5"
                        )}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 text-[10px] font-bold text-white">
                              {acc.platform?.[0]?.toUpperCase() || "U"}
                            </div>
                            <span className="text-sm text-slate-200">{acc.name}</span>
                          </div>
                          {crawling && activeAccountId === acc.id && (
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-400" />
                          )}
                        </div>
                      </motion.button>
                    ))}
                  </div>
                </div>

                {/* 视频列表 */}
                <div className="overflow-y-auto p-4">
                  {activeAccountId && (
                    <div className="mb-3 flex items-center justify-between">
                      <Button size="sm" onClick={() => handleCrawl(activeAccountId)} disabled={crawling}>
                        {crawling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Zap className="w-3.5 h-3.5" />}
                        {crawling ? "采集中..." : "采集视频"}
                      </Button>
                      {selectedVideoIds.size > 0 && (
                        <Button size="sm" variant="glass" onClick={handleAnalyze} disabled={analyzing}>
                          {analyzing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Activity className="w-3.5 h-3.5" />}
                          分析 ({selectedVideoIds.size})
                        </Button>
                      )}
                    </div>
                  )}

                  {videosLoading ? (
                    <div className="flex items-center justify-center py-20">
                      <Loader2 className="w-8 h-8 animate-spin text-brand-400" />
                    </div>
                  ) : videos.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-20 text-slate-500">
                      <VideoIcon className="w-12 h-12 mb-2 opacity-30" />
                      <p className="text-sm">选择账号后查看视频</p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 gap-2">
                      {videos.map((v, i) => (
                        <motion.div
                          key={v.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: i * 0.03 }}
                          whileHover={{ scale: 1.01 }}
                          onClick={() => {
                            const next = new Set(selectedVideoIds);
                            next.has(v.id) ? next.delete(v.id) : next.add(v.id);
                            setSelectedVideoIds(next);
                          }}
                          className={cn(
                            "glass cursor-pointer rounded-xl p-3 transition-all",
                            selectedVideoIds.has(v.id) && "ring-1 ring-brand-400/50 bg-brand-500/10"
                          )}
                        >
                          <div className="flex items-start gap-3">
                            <div className={cn(
                              "mt-0.5 flex h-4 w-4 items-center justify-center rounded border transition-all",
                              selectedVideoIds.has(v.id) ? "border-brand-400 bg-brand-500" : "border-white/20"
                            )}>
                              {selectedVideoIds.has(v.id) && <CheckCircle2 className="w-3 h-3 text-white" />}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-sm text-slate-200 line-clamp-1">{v.title}</p>
                              <div className="mt-1 flex items-center gap-3 text-[11px] text-slate-500">
                                <span>{formatNumber(v.like_count)} 赞</span>
                                <span>{formatNumber(v.comment_count)} 评</span>
                                <span>{formatNumber(v.share_count)} 转</span>
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            )}

            {nav === "viral" && (
              <motion.div key="viral" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="h-full overflow-y-auto p-6">
                {analyzing ? (
                  <div className="flex flex-col items-center justify-center py-20">
                    <motion.div
                      animate={{ rotate: 360 }}
                      transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                    >
                      <div className="h-16 w-16 rounded-full border-4 border-brand-500/20 border-t-brand-500" />
                    </motion.div>
                    <p className="mt-4 text-sm text-slate-400">AI 分析中...</p>
                  </div>
                ) : analysis ? (
                  <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
                    {/* 概览 */}
                    <div className="glass-border p-5">
                      <div className="mb-2 flex items-center gap-2">
                        <Badge variant="gradient"><Zap className="w-3 h-3 mr-1" />{analysis.provider}</Badge>
                        <span className="text-xs text-slate-500">{analysis.model_used}</span>
                      </div>
                      <p className="text-sm text-slate-300">{analysis.overview}</p>
                    </div>

                    {/* 爆款原因 */}
                    {analysis.viral_reasons?.length > 0 && (
                      <div className="glass-border p-5">
                        <h3 className="mb-3 text-sm font-semibold text-white">爆款原因</h3>
                        <div className="space-y-2">
                          {analysis.viral_reasons.map((r, i) => (
                            <motion.div
                              key={i}
                              initial={{ opacity: 0, x: -20 }}
                              animate={{ opacity: 1, x: 0 }}
                              transition={{ delay: i * 0.1 }}
                              className="glass rounded-lg p-3"
                            >
                              <div className="flex items-center gap-2 mb-1">
                                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-gradient-to-br from-orange-500 to-red-500 text-[10px] font-bold text-white">
                                  {i + 1}
                                </span>
                                <span className="text-sm font-medium text-white">{r.factor}</span>
                              </div>
                              <p className="ml-7 text-xs text-slate-400">{r.detail}</p>
                            </motion.div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* 选题建议 */}
                    {analysis.topic_suggestions?.length > 0 && (
                      <div className="glass-border p-5">
                        <h3 className="mb-3 text-sm font-semibold text-white">选题建议</h3>
                        <div className="flex flex-wrap gap-2">
                          {analysis.topic_suggestions.map((t, i) => (
                            <motion.div
                              key={i}
                              initial={{ opacity: 0, scale: 0.8 }}
                              animate={{ opacity: 1, scale: 1 }}
                              transition={{ delay: i * 0.05 }}
                              whileHover={{ scale: 1.05 }}
                            >
                              <Badge variant="gradient" className="cursor-pointer text-xs">
                                {t.title}
                              </Badge>
                            </motion.div>
                          ))}
                        </div>
                      </div>
                    )}
                  </motion.div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-20 text-slate-500">
                    <Activity className="w-12 h-12 mb-2 opacity-30" />
                    <p className="text-sm">选择视频后开始 AI 分析</p>
                  </div>
                )}
              </motion.div>
            )}

            {nav === "monitor" && (
              <motion.div key="monitor" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="h-full overflow-y-auto p-6">
                <RealtimeMonitorEmbed />
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Toast */}
      <AnimatePresence>
        {toast && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2"
          >
            <div className={cn(
              "glass-dark flex items-center gap-2 rounded-xl px-4 py-2.5 shadow-2xl",
              toast.type === "ok" ? "ring-1 ring-emerald-500/30" : "ring-1 ring-red-500/30"
            )}>
              {toast.type === "ok" ? (
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              ) : (
                <XCircle className="w-4 h-4 text-red-400" />
              )}
              <span className="text-sm text-white">{toast.msg}</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// 实时监控嵌入组件
function RealtimeMonitorEmbed() {
  const [triggering, setTriggering] = useState(false);
  const [status, setStatus] = useState<string>("空闲");

  const handleTrigger = async () => {
    setTriggering(true);
    setStatus("触发中...");
    try {
      await fetch("/be/monitor/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ max_accounts: 20, max_videos: 10, analyze: true }),
      });
      setStatus("监控已触发");
    } catch {
      setStatus("触发失败");
    } finally {
      setTriggering(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="glass-border flex items-center justify-between p-4">
        <div>
          <h3 className="text-sm font-semibold text-white">自动监控</h3>
          <p className="text-xs text-slate-500">{status}</p>
        </div>
        <Button onClick={handleTrigger} disabled={triggering}>
          {triggering ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Radio className="w-3.5 h-3.5" />}
          {triggering ? "触发中..." : "立即监控"}
        </Button>
      </div>
      <div className="glass-border p-5">
        <RealtimeStatusEmbed />
      </div>
    </div>
  );
}

function RealtimeStatusEmbed() {
  // 简化的实时状态展示
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="h-2 w-2 rounded-full bg-slate-500" />
        <span className="text-sm text-slate-400">等待 WebSocket 连接...</span>
      </div>
      <p className="text-xs text-slate-500">
        前往 <a href="/monitor" className="text-brand-400 hover:underline">实时监控页面</a> 查看完整实时状态
      </p>
    </div>
  );
}
