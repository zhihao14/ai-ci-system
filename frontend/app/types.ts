// 前端类型定义, 与后端 IntelligenceReport 对齐

export interface ReportSummary {
  id: string;
  url: string;
  title: string | null;
  summary: string | null;
  ai_provider: string | null;
  created_at: string;
}

export interface Report extends ReportSummary {
  id: string;
  competitor_id: string | null;
  products: string[];
  pricing: string[];
  positioning: { market?: string; audience?: string; region?: string };
  strengths: string[];
  weaknesses: string[];
  recent_changes: string | null;
}
