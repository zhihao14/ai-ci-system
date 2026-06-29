// lib/auth-context.tsx — 全局认证上下文
"use client";

import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { Session, User } from "@supabase/supabase-js";
import { supabase } from "./supabase";

// ---- 类型 ----
interface Profile {
  id: string;
  username: string | null;
  full_name: string | null;
  avatar_url: string | null;
  bio: string | null;
  current_tenant_id: string | null;
  api_key: string | null;
}

interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  daily_quota: number;
  monthly_quota: number;
}

interface AuthContextType {
  user: User | null;
  session: Session | null;
  profile: Profile | null;
  tenant: Tenant | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: string | null }>;
  signUp: (email: string, password: string, fullName?: string) => Promise<{ error: string | null }>;
  signOut: () => Promise<void>;
  refreshProfile: () => Promise<void>;
  switchTenant: (tenantId: string) => Promise<{ error: string | null }>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ---- Provider ----
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [loading, setLoading] = useState(true);

  // 拉取 profile + tenant
  const fetchProfile = useCallback(async (session: Session | null) => {
    if (!session?.access_token) {
      setProfile(null);
      setTenant(null);
      return;
    }

    try {
      // 调后端获取 profile + tenant
      const res = await fetch("/be/auth/auth/me", {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setProfile(data.profile);
        setTenant(data.tenant);
      }
    } catch {
      // 后端未启动时, 降级为只保存 session
      setProfile(null);
      setTenant(null);
    }
  }, []);

  // 初始化: 监听 auth 状态变化
  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setUser(data.session?.user ?? null);
      fetchProfile(data.session).finally(() => setLoading(false));
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setUser(newSession?.user ?? null);
      fetchProfile(newSession);
    });

    return () => listener.subscription.unsubscribe();
  }, [fetchProfile]);

  // ---- 操作方法 ----
  const signIn = async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return { error: error?.message ?? null };
  };

  const signUp = async (email: string, password: string, fullName?: string) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { full_name: fullName } },
    });
    return { error: error?.message ?? null };
  };

  const signOut = async () => {
    await supabase.auth.signOut();
    setProfile(null);
    setTenant(null);
  };

  const refreshProfile = async () => {
    await fetchProfile(session);
  };

  const switchTenant = async (tenantId: string) => {
    if (!session?.access_token) return { error: "未登录" };
    try {
      const res = await fetch(`/be/auth/tenants/${tenantId}/switch`, {
        method: "POST",
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (!res.ok) {
        const err = await res.json();
        return { error: err.detail || "切换租户失败" };
      }
      const data = await res.json();
      setTenant(data.tenant);
      return { error: null };
    } catch (e) {
      return { error: String(e) };
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        session,
        profile,
        tenant,
        loading,
        signIn,
        signUp,
        signOut,
        refreshProfile,
        switchTenant,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ---- Hook ----
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth 必须在 AuthProvider 内使用");
  return ctx;
}
