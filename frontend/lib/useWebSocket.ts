// lib/useWebSocket.ts — WebSocket 实时通知 Hook
"use client";

import { useState, useEffect, useCallback, useRef } from "react";

// ---- 事件类型 ----
export interface WSEvent {
  type:
    | "connected"
    | "monitor_start"
    | "account_crawling"
    | "crawl_done"
    | "analysis_crawling"
    | "analysis_done"
    | "monitor_done"
    | "error"
    | "pong"
    | "subscribed";
  run_id?: string;
  run_type?: string;
  total_accounts?: number;
  account_name?: string;
  platform?: string;
  index?: number;
  total?: number;
  crawled?: number;
  new_count?: number;
  analyzed?: number;
  tokens?: number;
  duration_ms?: number;
  video_count?: number;
  stage?: string;
  error?: string;
  stats?: {
    total: number;
    crawled: number;
    failed: number;
    skipped: number;
    new_videos: number;
    analyzed: number;
    total_tokens: number;
  };
  status?: string;
  message?: string;
  timestamp?: string;
}

// ---- 账号监控状态 ----
export interface AccountStatus {
  name: string;
  platform: string;
  status: "crawling" | "crawl_done" | "analyzing" | "analysis_done" | "error";
  crawled?: number;
  new_count?: number;
  analyzed?: number;
  tokens?: number;
  error?: string;
  timestamp: string;
}

// ---- 整体监控状态 ----
export interface MonitorState {
  connected: boolean;
  run_id: string | null;
  is_monitoring: boolean;
  total_accounts: number;
  current_index: number;
  current_account: string;
  current_stage: string; // "idle" | "crawling" | "analyzing" | "done"
  accounts: AccountStatus[];
  events: WSEvent[];
  stats: {
    new_videos: number;
    analyzed: number;
    total_tokens: number;
    failed: number;
  };
}

const initialState: MonitorState = {
  connected: false,
  run_id: null,
  is_monitoring: false,
  total_accounts: 0,
  current_index: 0,
  current_account: "",
  current_stage: "idle",
  accounts: [],
  events: [],
  stats: { new_videos: 0, analyzed: 0, total_tokens: 0, failed: 0 },
};

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8010/ws";

export function useMonitorWebSocket(runId?: string) {
  const [state, setState] = useState<MonitorState>(initialState);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout>();

  // ---- 处理事件 ----
  const handleEvent = useCallback((event: WSEvent) => {
    setState((prev) => {
      const newEvents = [event, ...prev.events].slice(0, 50); // 保留最近 50 条

      switch (event.type) {
        case "connected":
          return { ...prev, connected: true, events: newEvents };

        case "monitor_start":
          return {
            ...prev,
            connected: true,
            is_monitoring: true,
            run_id: event.run_id || null,
            total_accounts: event.total_accounts || 0,
            current_index: 0,
            current_account: "",
            current_stage: "crawling",
            accounts: [],
            events: newEvents,
            stats: { new_videos: 0, analyzed: 0, total_tokens: 0, failed: 0 },
          };

        case "account_crawling":
          return {
            ...prev,
            is_monitoring: true,
            current_index: event.index || 0,
            current_account: event.account_name || "",
            current_stage: "crawling",
            accounts: [
              {
                name: event.account_name || "",
                platform: event.platform || "",
                status: "crawling",
                timestamp: event.timestamp || "",
              },
              ...prev.accounts.filter((a) => a.name !== event.account_name),
            ],
            events: newEvents,
          };

        case "crawl_done":
          return {
            ...prev,
            current_stage: "crawl_done",
            accounts: prev.accounts.map((a) =>
              a.name === event.account_name
                ? {
                    ...a,
                    status: "crawl_done",
                    crawled: event.crawled,
                    new_count: event.new_count,
                    timestamp: event.timestamp || "",
                  }
                : a
            ),
            stats: {
              ...prev.stats,
              new_videos: prev.stats.new_videos + (event.new_count || 0),
            },
            events: newEvents,
          };

        case "analysis_crawling":
          return {
            ...prev,
            current_stage: "analyzing",
            accounts: prev.accounts.map((a) =>
              a.name === event.account_name
                ? { ...a, status: "analyzing", timestamp: event.timestamp || "" }
                : a
            ),
            events: newEvents,
          };

        case "analysis_done":
          return {
            ...prev,
            current_stage: "analysis_done",
            accounts: prev.accounts.map((a) =>
              a.name === event.account_name
                ? {
                    ...a,
                    status: "analysis_done",
                    analyzed: event.analyzed,
                    tokens: event.tokens,
                    timestamp: event.timestamp || "",
                  }
                : a
            ),
            stats: {
              ...prev.stats,
              analyzed: prev.stats.analyzed + (event.analyzed || 0),
              total_tokens: prev.stats.total_tokens + (event.tokens || 0),
            },
            events: newEvents,
          };

        case "error":
          return {
            ...prev,
            accounts: prev.accounts.map((a) =>
              a.name === event.account_name
                ? {
                    ...a,
                    status: "error",
                    error: event.error,
                    timestamp: event.timestamp || "",
                  }
                : a
            ),
            stats: {
              ...prev.stats,
              failed: prev.stats.failed + 1,
            },
            events: newEvents,
          };

        case "monitor_done":
          return {
            ...prev,
            is_monitoring: false,
            current_stage: "done",
            events: newEvents,
            stats: event.stats
              ? {
                  new_videos: event.stats.new_videos,
                  analyzed: event.stats.analyzed,
                  total_tokens: event.stats.total_tokens,
                  failed: event.stats.failed,
                }
              : prev.stats,
          };

        default:
          return { ...prev, events: newEvents };
      }
    });
  }, []);

  // ---- 连接 WebSocket ----
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const url = runId ? `${WS_URL}?run_id=${runId}` : WS_URL;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log("[WS] 已连接");
    };

    ws.onmessage = (e) => {
      try {
        const event: WSEvent = JSON.parse(e.data);
        handleEvent(event);
      } catch (err) {
        console.error("[WS] 解析消息失败:", err);
      }
    };

    ws.onclose = () => {
      console.log("[WS] 连接断开, 3 秒后重连...");
      setState((prev) => ({ ...prev, connected: false }));
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
      console.error("[WS] 连接错误:", err);
    };
  }, [runId, handleEvent]);

  // ---- 发送消息 ----
  const sendMessage = useCallback((msg: object) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  // ---- 订阅特定 run_id ----
  const subscribe = useCallback((newRunId: string) => {
    sendMessage({ action: "subscribe", run_id: newRunId });
  }, [sendMessage]);

  // ---- 心跳 ----
  const ping = useCallback(() => {
    sendMessage({ action: "ping" });
  }, [sendMessage]);

  // ---- 初始化 ----
  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  // 定时心跳 (30 秒)
  useEffect(() => {
    const timer = setInterval(ping, 30000);
    return () => clearInterval(timer);
  }, [ping]);

  return { state, subscribe, ping, sendMessage };
}
