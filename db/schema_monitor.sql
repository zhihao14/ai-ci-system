-- ============================================================
-- 自动监控调度系统 - 数据库 Schema
-- 依赖: accounts / videos / ai_analysis 表已存在
--
-- 新增 2 张表:
--   1. monitor_runs     — 监控轮次记录 (每 30 分钟一轮)
--   2. monitor_tasks    — 单账号监控任务记录 (每轮 N 个账号 = N 条)
--
-- 用途:
--   - 记录每轮自动监控的执行状态 (成功/失败/跳过)
--   - 追踪每个账号的采集+分析结果
--   - 便于前端展示监控历史和排查问题
-- ============================================================

-- ------------------------------------------------------------
-- 1. monitor_runs — 监控轮次
--    每 30 分钟自动触发一轮, 记录整体执行情况
-- ------------------------------------------------------------
create table if not exists monitor_runs (
  id            uuid        primary key default gen_random_uuid(),

  -- 轮次信息
  run_type      text        not null default 'scheduled',  -- 'scheduled' (定时) | 'manual' (手动触发)
  status        text        not null default 'running',    -- 'running' | 'success' | 'failed' | 'partial'

  -- 统计
  total_accounts   integer  not null default 0,            -- 本轮扫描账号总数
  crawled_accounts integer  not null default 0,            -- 成功采集账号数
  failed_accounts  integer  not null default 0,             -- 采集失败账号数
  skipped_accounts integer  not null default 0,            -- 跳过账号数 (如无新视频)
  new_videos       integer  not null default 0,            -- 新增视频总数
  analyzed_videos  integer  not null default 0,            -- AI 分析视频数
  total_tokens      integer  not null default 0,           -- AI 消耗 token 总数

  -- 错误信息 (整体)
  error         text,

  -- 时间
  started_at    timestamptz not null default now(),
  finished_at   timestamptz
);

create index if not exists idx_runs_started on monitor_runs(started_at desc);
create index if not exists idx_runs_status  on monitor_runs(status);


-- ------------------------------------------------------------
-- 2. monitor_tasks — 单账号监控任务
--    每轮监控对每个账号生成一条记录
-- ------------------------------------------------------------
create table if not exists monitor_tasks (
  id            uuid        primary key default gen_random_uuid(),

  run_id        uuid        not null references monitor_runs(id) on delete cascade,
  account_id    uuid        references accounts(id) on delete set null,

  -- 账号信息快照 (避免 join, 便于历史查询)
  platform      text,
  account_name  text,

  -- 任务状态
  status        text        not null default 'pending',  -- 'pending' | 'running' | 'success' | 'failed' | 'skipped'

  -- 采集结果
  crawled_count  integer   default 0,                    -- 爬取到的视频数
  new_count       integer   default 0,                   -- 新增视频数 (DB 中不存在的)
  video_ids       jsonb     default '[]'::jsonb,          -- 新增视频 ID 列表

  -- AI 分析结果
  analysis_id    uuid,                                    -- ai_analysis 表的记录 ID
  analysis_type  text,                                    -- 'viral' | 'content'
  analysis_status text,                                  -- 'success' | 'failed' | 'skipped'
  prompt_tokens   integer  default 0,
  completion_tokens integer default 0,

  -- 错误
  crawl_error    text,
  analysis_error text,

  -- 耗时 (毫秒)
  crawl_duration_ms   integer,
  analysis_duration_ms integer,

  started_at    timestamptz not null default now(),
  finished_at   timestamptz
);

create index if not exists idx_tasks_run     on monitor_tasks(run_id);
create index if not exists idx_tasks_account on monitor_tasks(account_id);
create index if not exists idx_tasks_status  on monitor_tasks(status);


-- ------------------------------------------------------------
-- 3. RLS (演示开放)
-- ------------------------------------------------------------
alter table monitor_runs  enable row level security;
alter table monitor_tasks enable row level security;

drop policy if exists "public access" on monitor_runs;
drop policy if exists "public access" on monitor_tasks;
create policy "public access" on monitor_runs  for all using (true) with check (true);
create policy "public access" on monitor_tasks for all using (true) with check (true);


-- ------------------------------------------------------------
-- 4. 视图: 账号最后监控时间 (便于查询哪些账号很久没监控)
-- ------------------------------------------------------------
create or replace view v_account_last_monitor as
select
  a.id as account_id,
  a.platform,
  a.name as account_name,
  max(mt.started_at) as last_monitored_at,
  max(mt.new_count) as last_new_count,
  count(mt.id) as total_runs
from accounts a
left join monitor_tasks mt on mt.account_id = a.id
group by a.id, a.platform, a.name;


-- ============================================================
-- 完. 执行后可通过 SELECT * FROM monitor_runs ORDER BY started_at DESC LIMIT 10; 查看监控历史
-- ============================================================
