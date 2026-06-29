// components/profile/TenantTab.tsx — 租户管理
"use client";

import { useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";

interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  daily_quota: number;
  monthly_quota: number;
  member_role?: string;
}

interface Member {
  id: string;
  user_id: string;
  role: string;
  joined_at: string;
  username?: string;
  full_name?: string;
}

export default function TenantTab() {
  const { tenant, session, switchTenant } = useAuth();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchTenants = async () => {
    try {
      const res = await fetch("/be/auth/tenants", {
        headers: { Authorization: `Bearer ${session?.access_token}` },
      });
      const data = await res.json();
      setTenants(Array.isArray(data) ? data : []);
    } finally {
      setLoading(false);
    }
  };

  const fetchMembers = async (tenantId: string) => {
    const res = await fetch(`/be/auth/tenants/${tenantId}/members`, {
      headers: { Authorization: `Bearer ${session?.access_token}` },
    });
    const data = await res.json();
    setMembers(Array.isArray(data) ? data : []);
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  useEffect(() => {
    if (tenant?.id) fetchMembers(tenant.id);
  }, [tenant?.id]);

  const handleSwitch = async (tenantId: string) => {
    const { error } = await switchTenant(tenantId);
    if (error) alert(error);
    else await fetchTenants();
  };

  if (loading) return <div className="py-8 text-center text-sm text-slate-400">加载中...</div>;

  return (
    <div className="space-y-6">
      {/* 租户列表 */}
      <div>
        <h3 className="mb-3 text-sm font-semibold text-slate-900">我的工作空间</h3>
        <div className="space-y-2">
          {tenants.map((t) => (
            <div
              key={t.id}
              className={`flex items-center justify-between rounded-xl border p-4 ${
                tenant?.id === t.id
                  ? "border-brand-200 bg-brand-50"
                  : "border-slate-200 bg-white"
              }`}
            >
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-900">{t.name}</span>
                  {tenant?.id === t.id && (
                    <span className="rounded bg-brand-100 px-1.5 py-0.5 text-xs text-brand-600">
                      当前
                    </span>
                  )}
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                    {t.member_role || t.plan}
                  </span>
                </div>
                <div className="mt-1 text-xs text-slate-400">
                  slug: {t.slug} · 日额度: {t.daily_quota} · 月额度: {t.monthly_quota}
                </div>
              </div>
              {tenant?.id !== t.id && (
                <button
                  onClick={() => handleSwitch(t.id)}
                  className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                >
                  切换
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 成员列表 */}
      {tenant && (
        <div className="border-t border-slate-100 pt-6">
          <h3 className="mb-3 text-sm font-semibold text-slate-900">
            成员列表 ({members.length})
          </h3>
          <div className="space-y-1">
            {members.map((m) => (
              <div
                key={m.id}
                className="flex items-center justify-between rounded-lg px-3 py-2 hover:bg-slate-50"
              >
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-200 text-xs font-medium text-slate-600">
                    {(m.full_name || m.username || "U")[0].toUpperCase()}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-700">
                      {m.full_name || m.username || "用户"}
                    </p>
                  </div>
                </div>
                <span
                  className={`rounded px-2 py-0.5 text-xs ${
                    m.role === "owner"
                      ? "bg-amber-50 text-amber-600"
                      : m.role === "admin"
                      ? "bg-blue-50 text-blue-600"
                      : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {m.role}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
