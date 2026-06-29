-- ============================================================
-- AI 竞争情报系统 - 模块: 竞争对手网站情报分析
-- 在 Supabase SQL Editor 中执行此文件
-- ============================================================

-- 1) 竞争对手基础信息表
create table if not exists competitors (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,                 -- 竞争对手名称
  url         text not null unique,          -- 官网地址
  created_at  timestamptz default now()
);

-- 2) 情报报告表: 存储 AI 生成的结构化情报
create table if not exists intelligence_reports (
  id              uuid primary key default gen_random_uuid(),
  competitor_id   uuid references competitors(id) on delete cascade,
  url             text not null,             -- 被分析的页面 URL
  title           text,                     -- 页面标题
  raw_content     text,                     -- 爬取到的页面正文(用于溯源)
  summary         text,                     -- AI 概述
  products        jsonb,                    -- 产品/服务列表
  pricing         jsonb,                    -- 定价信息
  positioning     jsonb,                    -- 市场定位/目标客群
  strengths       text[],                  -- 优势 (SWOT-S)
  weaknesses      text[],                  -- 劣势 (SWOT-W)
  recent_changes  text,                     -- 检测到的近期变化
  ai_provider     text,                     -- 'deepseek' | 'claude'
  created_at      timestamptz default now()
);

-- 3) 索引: 提升按竞争对手、按时间查询的速度
create index if not exists idx_reports_competitor on intelligence_reports(competitor_id);
create index if not exists idx_reports_created    on intelligence_reports(created_at desc);

-- 4) 行级安全 (RLS): 演示阶段开放读写, 生产环境请按业务收紧
alter table competitors          enable row level security;
alter table intelligence_reports  enable row level security;

drop policy if exists "public access" on competitors;
drop policy if exists "public access" on intelligence_reports;
create policy "public access" on competitors          for all using (true) with check (true);
create policy "public access" on intelligence_reports for all using (true) with check (true);
