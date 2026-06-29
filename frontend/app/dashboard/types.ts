// Dashboard 类型定义 - 与后端 models_accounts.py / models_viral.py 对齐

// ---- 账号 ----
export interface Account {
  id: string;
  platform: string;
  platform_uid: string;
  name: string;
  handle: string | null;
  avatar_url: string | null;
  bio: string | null;
  follower_count: number;
  following_count: number;
  created_at: string;
  updated_at: string;
}

// ---- 视频 ----
export interface Video {
  id: string;
  account_id: string;
  platform_vid: string;
  title: string | null;
  description: string | null;
  cover_url: string | null;
  video_url: string | null;
  duration_sec: number | null;
  view_count: number;
  like_count: number;
  comment_count: number;
  share_count: number;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

// ---- 爆款分析结果 ----
export interface ViralReason {
  factor: string;
  detail: string;
  evidence: string;
}

export interface TitlePattern {
  pattern: string;
  examples: string[];
  template: string;
}

export interface ContentTactic {
  name: string;
  description: string;
  frequency: string;
}

export interface TopicSuggestion {
  title: string;
  angle: string;
  why_works: string;
  target_platform: string;
}

export interface ViralAnalysis {
  overview: string;
  viral_reasons: ViralReason[];
  title_patterns: TitlePattern[];
  content_tactics: ContentTactic[];
  topic_suggestions: TopicSuggestion[];
  model_used: string;
  provider: string;
  prompt_tokens: number;
  completion_tokens: number;
}

// ---- 可用模型 ----
export interface ModelOption {
  id: string;
  label: string;
  provider: string;
}

// ---- 通用 API 响应 ----
export interface CrawlResult {
  account_id: string;
  account_name: string | null;
  crawled: number;
  videos: Video[];
}
