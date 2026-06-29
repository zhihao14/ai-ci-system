// lib/supabase.ts — Supabase 客户端 (浏览器端)
// 使用 NEXT_PUBLIC_ 前缀环境变量 (客户端可见)
import { createClient, SupabaseClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

let _client: SupabaseClient | null = null;

export function getSupabase(): SupabaseClient {
  if (_client) return _client;
  if (!supabaseUrl || !supabaseAnonKey) {
    // 构建时无环境变量, 返回一个空壳客户端 (避免 SSG 报错)
    _client = createClient("https://placeholder.supabase.co", "placeholder-key");
    return _client;
  }
  _client = createClient(supabaseUrl, supabaseAnonKey);
  return _client;
}

export const supabase = getSupabase();
