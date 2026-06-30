-- ============================================================
-- AI Competitive Intelligence Platform - 智能分析模块
-- 在 Supabase SQL Editor 中执行此文件
-- ============================================================

-- 1) 视频分析表: 存储爬取的视频数据 + AI 分析结果
create table if not exists video_analyses (
  id              uuid primary key default gen_random_uuid(),
  competitor_id   uuid references competitors(id) on delete cascade,
  url             text not null,
  account_name    text,
  account_info    text,
  account_fields  jsonb,
  videos          jsonb,
  video_count     integer default 0,
  analysis        jsonb,
  ai_provider     text,
  created_at      timestamptz default now(),
  updated_at      timestamptz default now()
);

create index if not exists idx_va_competitor on video_analyses(competitor_id);
create index if not exists idx_va_created    on video_analyses(created_at desc);

-- 2) 内容模式表: Pattern Agent 产出
create table if not exists content_patterns (
  id                uuid primary key default gen_random_uuid(),
  video_analysis_id uuid references video_analyses(id) on delete cascade,
  competitor_id     uuid references competitors(id) on delete cascade,
  patterns          jsonb,
  confidence_score  float,
  ai_provider       text,
  created_at        timestamptz default now()
);

create index if not exists idx_cp_analysis   on content_patterns(video_analysis_id);
create index if not exists idx_cp_competitor on content_patterns(competitor_id);

-- 3) 竞争对手对比表: Comparison Agent 产出
create table if not exists competitor_comparisons (
  id              uuid primary key default gen_random_uuid(),
  analysis_ids    uuid[],
  comparison_data jsonb,
  ai_provider     text,
  created_at      timestamptz default now()
);

-- 4) 趋势预测表: Trend Agent 产出
create table if not exists trend_predictions (
  id              uuid primary key default gen_random_uuid(),
  video_analysis_id uuid references video_analyses(id) on delete cascade,
  competitor_id   uuid references competitors(id) on delete cascade,
  predictions     jsonb,
  confidence_score float,
  ai_provider     text,
  created_at      timestamptz default now()
);

create index if not exists idx_tp_competitor on trend_predictions(competitor_id);

-- 5) 增长策略表: Strategy Agent 产出
create table if not exists growth_strategies (
  id                uuid primary key default gen_random_uuid(),
  video_analysis_id uuid references video_analyses(id) on delete cascade,
  competitor_id     uuid references competitors(id) on delete cascade,
  strategy          jsonb,
  ai_provider       text,
  created_at        timestamptz default now()
);

create index if not exists idx_gs_competitor on growth_strategies(competitor_id);

-- 6) RAG 知识库表: 存储所有分析结果供语义检索
create table if not exists knowledge_base (
  id            uuid primary key default gen_random_uuid(),
  competitor_id uuid references competitors(id) on delete cascade,
  content_type  text not null,               -- 'analysis' | 'pattern' | 'trend' | 'strategy' | 'comparison'
  title         text,
  content       text not null,
  metadata      jsonb,
  search_vector tsvector generated always as (
    to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(content, ''))
  ) stored,
  created_at   timestamptz default now()
);

create index if not exists idx_kb_search     on knowledge_base using gin(search_vector);
create index if not exists idx_kb_competitor on knowledge_base(competitor_id);
create index if not exists idx_kb_type        on knowledge_base(content_type);
create index if not exists idx_kb_created     on knowledge_base(created_at desc);

-- 7) 行级安全 (RLS)
alter table video_analyses       enable row level security;
alter table content_patterns     enable row level security;
alter table competitor_comparisons enable row level security;
alter table trend_predictions   enable row level security;
alter table growth_strategies   enable row level security;
alter table knowledge_base      enable row level security;

drop policy if exists "public access" on video_analyses;
drop policy if exists "public access" on content_patterns;
drop policy if exists "public access" on competitor_comparisons;
drop policy if exists "public access" on trend_predictions;
drop policy if exists "public access" on growth_strategies;
drop policy if exists "public access" on knowledge_base;

create policy "public access" on video_analyses         for all using (true) with check (true);
create policy "public access" on content_patterns       for all using (true) with check (true);
create policy "public access" on competitor_comparisons  for all using (true) with check (true);
create policy "public access" on trend_predictions       for all using (true) with check (true);
create policy "public access" on growth_strategies       for all using (true) with check (true);
create policy "public access" on knowledge_base         for all using (true) with check (true);
