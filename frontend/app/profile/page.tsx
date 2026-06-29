// app/profile/page.tsx — 用户个人空间
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";

// ---- 子组件 ----
import ProfileTab from "@/components/profile/ProfileTab";
import TenantTab from "@/components/profile/TenantTab";
import QuotaTab from "@/components/profile/QuotaTab";
import UsageTab from "@/components/profile/UsageTab";

type Tab = "profile" | "tenant" | "quota" | "usage";

export default function ProfilePage() {
  const router = useRouter();
  const { user, profile, tenant, loading, signOut } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>("profile");

  // 未登录跳转
  useEffect(() => {
    if (!loading && !user) {
      router.push("/login");
    }
  }, [loading, user, router]);

  if (loading || !user) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-sm text-slate-400">加载中...</div>
      </div>
    );
  }

  const tabs: { key: Tab; label: string; icon: string }[] = [
    { key: "profile", label: "个人资料", icon: "👤" },
    { key: "tenant", label: "租户管理", icon: "🏢" },
    { key: "quota", label: "API 额度", icon: "📊" },
    { key: "usage", label: "调用记录", icon: "📜" },
  ];

  return (
    <div className="min-h-screen bg-slate-50">
      {/* 顶栏 */}
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
              CI
            </div>
            <span className="text-sm font-semibold text-slate-900">
              AI 竞争情报系统
            </span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push("/dashboard")}
              className="text-sm text-slate-500 transition hover:text-slate-900"
            >
              Dashboard →
            </button>
            <button
              onClick={() => signOut().then(() => router.push("/login"))}
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-50"
            >
              退出
            </button>
          </div>
        </div>
      </header>

      {/* 内容 */}
      <main className="mx-auto max-w-5xl px-6 py-8">
        {/* 用户信息卡片 */}
        <div className="mb-6 flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 text-2xl font-bold text-brand-600">
            {(profile?.full_name || profile?.username || user.email || "U")[0].toUpperCase()}
          </div>
          <div className="flex-1">
            <h1 className="text-lg font-bold text-slate-900">
              {profile?.full_name || profile?.username || "用户"}
            </h1>
            <p className="text-sm text-slate-500">{user.email}</p>
          </div>
          {tenant && (
            <div className="rounded-lg bg-slate-50 px-4 py-2 text-right">
              <div className="text-xs text-slate-400">当前租户</div>
              <div className="text-sm font-medium text-slate-700">{tenant.name}</div>
              <div className="mt-0.5">
                <span className="rounded bg-brand-50 px-1.5 py-0.5 text-xs font-medium text-brand-600">
                  {tenant.plan}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Tab 导航 */}
        <div className="mb-6 flex gap-1 border-b border-slate-200">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`relative px-4 py-2.5 text-sm font-medium transition ${
                activeTab === tab.key
                  ? "text-brand-600"
                  : "text-slate-500 hover:text-slate-700"
              }`}
            >
              <span className="mr-1.5">{tab.icon}</span>
              {tab.label}
              {activeTab === tab.key && (
                <span className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-brand-600" />
              )}
            </button>
          ))}
        </div>

        {/* Tab 内容 */}
        <div className="rounded-2xl border border-slate-200 bg-white p-6">
          {activeTab === "profile" && <ProfileTab />}
          {activeTab === "tenant" && <TenantTab />}
          {activeTab === "quota" && <QuotaTab />}
          {activeTab === "usage" && <UsageTab />}
        </div>
      </main>
    </div>
  );
}
