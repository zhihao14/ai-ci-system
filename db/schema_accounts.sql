-- ============================================================
-- AI 竞争情报系统 - 数据库设计模块
-- 数据库: Supabase (PostgreSQL 15+)
-- 说明: 3 张核心表 + 外键关系, 在 Supabase SQL Editor 整体执行
--
-- 表关系 (ER):
--
--   accounts (1) ───────< (N) videos
--      │                       │
--      │  1                    │  1
--      └──────────────────< (N) ai_analysis
--
--   - 一个账号(account)可发布多条视频(video)
--   - 一个账号可直接关联多条账号级 AI 分析(ai_analysis)
--   - 一条视频也可关联多条视频级 AI 分析(ai_analysis)
--   因此 ai_analysis 同时持有两个可空外键: account_id 与 video_id,
--   二者至少有一个非空 (CHECK 约束)
-- ============================================================


-- ------------------------------------------------------------
-- 0. 扩展: gen_random_uuid() 需要 pgcrypto (Supabase 默认已启用)
-- ------------------------------------------------------------
create extension if not exists pgcrypto;


-- ------------------------------------------------------------
-- 1. accounts —— 竞争对手账号
--    一个账号 = 某平台上的一个竞品主体 (如某品牌抖音号)
-- ------------------------------------------------------------
create table if not exists accounts (
  -- 主键: UUID, 应用层不传, 由 DB 生成
  id            uuid        primary key default gen_random_uuid(),

  -- 业务唯一键: 平台 + 平台内账号 ID, 防止重复入库
  platform      text        not null,                       -- 'douyin' | 'tiktok' | 'youtube' | ...
  platform_uid  text        not null,                       -- 该平台内的账号唯一 ID
  unique (platform, platform_uid),

  -- 账号基础信息
  name          text        not null,                       -- 昵称/展示名
  handle        text,                                       -- @账号 (可空)
  avatar_url    text,                                       -- 头像 URL
  bio           text,                                       -- 简介
  follower_count integer     default 0,                    -- 粉丝数 (快照)
  following_count integer   default 0,                      -- 关注数 (快照)

  -- 时间字段: 均带时区, created_at 由 DB 自动填充
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- updated_at 自动维护: 更新时刷新
create or replace function trg_accounts_set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists set_updated_at on accounts;
create trigger set_updated_at
  before update on accounts
  for each row execute function trg_accounts_set_updated_at();

-- 查询常用索引
create index if not exists idx_accounts_platform on accounts(platform);


-- ------------------------------------------------------------
-- 2. videos —— 视频数据
--    归属于某个 account, 记录视频元信息与统计快照
-- ------------------------------------------------------------
create table if not exists videos (
  id            uuid        primary key default gen_random_uuid(),

  -- 外键: 视频归属的账号; 账号删除时连带删除其视频 (cascade)
  account_id    uuid        not null references accounts(id) on delete cascade,

  -- 平台内视频唯一 ID (同账号下唯一), 防重复爬取
  platform_vid  text        not null,
  unique (account_id, platform_vid),

  -- 视频内容
  title         text,
  description   text,
  cover_url     text,                                       -- 封面
  video_url     text,                                       -- 播放地址 (可空, 平台可能不提供)
  duration_sec  integer,                                    -- 时长(秒)

  -- 统计快照 (爬取时刻)
  view_count    bigint      default 0,
  like_count    bigint      default 0,
  comment_count bigint      default 0,
  share_count   bigint      default 0,

  -- 发布时间 (平台显示), 区别于入库 created_at
  published_at  timestamptz,

  -- 时间字段
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create or replace function trg_videos_set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists set_updated_at on videos;
create trigger set_updated_at
  before update on videos
  for each row execute function trg_videos_set_updated_at();

-- 查询常用索引
create index if not exists idx_videos_account      on videos(account_id);
create index if not exists idx_videos_published    on videos(published_at desc);
create index if not exists idx_videos_created      on videos(created_at desc);


-- ------------------------------------------------------------
-- 3. ai_analysis —— AI 分析结果
--    可挂在 account 级别 (账号画像), 也可挂在 video 级别 (单条视频分析)
--    两个外键至少填一个
-- ------------------------------------------------------------
create table if not exists ai_analysis (
  id            uuid        primary key default gen_random_uuid(),

  -- 外键 A: 账号级分析 (可空)
  account_id    uuid        references accounts(id) on delete cascade,

  -- 外键 B: 视频级分析 (可空)
  video_id      uuid        references videos(id)   on delete cascade,

  -- 约束: 账号级和视频级不能同时为空 (至少分析一个对象)
  check (account_id is not null or video_id is not null),

  -- 分析内容
  analysis_type text        not null,                       -- 'account_profile' | 'video_content' | 'trend' ...
  summary       text,                                       -- AI 概述
  result        jsonb       not null default '{}'::jsonb,  -- AI 完整结构化结果 (灵活 schema)
  ai_provider   text,                                       -- 'deepseek' | 'claude'
  ai_model      text,                                       -- 具体模型名
  prompt_tokens integer,                                    -- 输入 token (成本核算)
  completion_tokens integer,                                -- 输出 token

  -- 时间字段
  created_at    timestamptz not null default now()
  -- 注意: AI 分析结果视为不可变快照, 不设 updated_at
);

-- 查询常用索引
create index if not exists idx_ai_account       on ai_analysis(account_id) where account_id is not null;
create index if not exists idx_ai_video         on ai_analysis(video_id)   where video_id   is not null;
create index if not exists idx_ai_type_created on ai_analysis(analysis_type, created_at desc);


-- ------------------------------------------------------------
-- 4. 行级安全 (RLS)
--    演示阶段开放读写; 生产环境请按业务收紧 (如仅限 authenticated)
-- ------------------------------------------------------------
alter table accounts     enable row level security;
alter table videos       enable row level security;
alter table ai_analysis  enable row level security;

drop policy if exists "public access" on accounts;
drop policy if exists "public access" on videos;
drop policy if exists "public access" on ai_analysis;

create policy "public access" on accounts    for all using (true) with check (true);
create policy "public access" on videos      for all using (true) with check (true);
create policy "public access" on ai_analysis for all using (true) with check (true);


-- ============================================================
-- 完. 执行后可通过 \d accounts; \d videos; \d ai_analysis; 查看结构
-- ============================================================
