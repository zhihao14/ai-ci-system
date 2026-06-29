-- ============================================================
-- 异常增长检测系统 - 数据库 Schema
-- 在 Supabase SQL Editor 中执行 (依赖 accounts / videos 表已存在)
--
-- 3 张新表:
--   1. metrics_snapshots  — 指标快照 (定时采集, 用于计算增长率)
--   2. alerts              — 异常告警记录
--   3. notifications       — 通知发送记录
-- ============================================================

-- ------------------------------------------------------------
-- 1. metrics_snapshots — 指标快照表
--    每隔 N 分钟为每条视频/账号拍一次快照, 记录当时的计数
--    通过相邻快照的差值计算增长率
-- ------------------------------------------------------------
create table if not exists metrics_snapshots (
  id            uuid        primary key default gen_random_uuid(),

  -- 关联对象: 视频级 或 账号级 (二选一)
  video_id      uuid        references videos(id)   on delete cascade,
  account_id    uuid        references accounts(id)  on delete cascade,
  check (video_id is not null or account_id is not null),

  -- 快照类型
  snapshot_type text        not null,   -- 'video' | 'account'

  -- 视频指标快照
  like_count    bigint      default 0,
  comment_count bigint      default 0,
  share_count   bigint      default 0,
  view_count    bigint      default 0,

  -- 账号指标快照
  follower_count bigint     default 0,

  -- 采样时间
  captured_at   timestamptz not null default now()
);

-- 索引: 按对象 + 时间查询 (计算增长率时用)
create index if not exists idx_snap_video_time   on metrics_snapshots(video_id, captured_at desc) where video_id is not null;
create index if not exists idx_snap_account_time  on metrics_snapshots(account_id, captured_at desc) where account_id is not null;
create index if not exists idx_snap_type_time     on metrics_snapshots(snapshot_type, captured_at desc);
-- 自动清理: 保留 7 天快照 (通过 cron 或应用层删除)
create index if not exists idx_snap_captured      on metrics_snapshots(captured_at);


-- ------------------------------------------------------------
-- 2. alerts — 异常告警表
--    检测到异常时插入一条, 记录异常详情
-- ------------------------------------------------------------
create table if not exists alerts (
  id            uuid        primary key default gen_random_uuid(),

  -- 关联对象
  video_id      uuid        references videos(id)   on delete cascade,
  account_id    uuid        references accounts(id)  on delete cascade,

  -- 告警信息
  alert_type    text        not null,   -- 'like_growth' | 'comment_growth' | 'follower_growth'
  severity      text        not null default 'medium',  -- 'low' | 'medium' | 'high' | 'critical'
  metric_name   text        not null,   -- 'likes' | 'comments' | 'followers'
  current_value bigint      not null,   -- 当前值
  growth_value  bigint      not null,   -- 增长量 (2小时内)
  growth_rate   double precision,       -- 增长率 (倍数, 如 3.5 = 比正常高3.5倍)
  z_score      double precision,        -- Z-score (标准差倍数)
  window_hours  integer     not null default 2,  -- 检测窗口 (小时)

  -- 状态
  is_viral      boolean     not null default false,  -- 是否标记为爆款
  status        text        not null default 'active',  -- 'active' | 'acknowledged' | 'resolved'
  message       text,                  -- 人类可读描述

  created_at    timestamptz not null default now()
);

create index if not exists idx_alerts_created    on alerts(created_at desc);
create index if not exists idx_alerts_status     on alerts(status);
create index if not exists idx_alerts_video      on alerts(video_id) where video_id is not null;
create index if not exists idx_alerts_account    on alerts(account_id) where account_id is not null;
create index if not exists idx_alerts_viral      on alerts(is_viral) where is_viral = true;


-- ------------------------------------------------------------
-- 3. notifications — 通知记录表
--    每次告警触发通知时记录, 避免重复发送
-- ------------------------------------------------------------
create table if not exists notifications (
  id            uuid        primary key default gen_random_uuid(),
  alert_id      uuid        references alerts(id) on delete cascade,

  -- 通知渠道
  channel       text        not null,   -- 'webhook' | 'email' | 'in_app'
  recipient     text,                   -- 接收者 (URL / 邮箱 / 用户ID)
  payload       jsonb,                  -- 通知内容

  -- 状态
  status        text        not null default 'pending',  -- 'pending' | 'sent' | 'failed'
  error         text,
  sent_at       timestamptz,

  created_at    timestamptz not null default now()
);

create index if not exists idx_notif_status on notifications(status);
create index if not exists idx_notif_alert on notifications(alert_id);


-- ------------------------------------------------------------
-- 4. RLS (演示开放)
-- ------------------------------------------------------------
alter table metrics_snapshots enable row level security;
alter table alerts            enable row level security;
alter table notifications     enable row level security;

drop policy if exists "public access" on metrics_snapshots;
drop policy if exists "public access" on alerts;
drop policy if exists "public access" on notifications;
create policy "public access" on metrics_snapshots for all using (true) with check (true);
create policy "public access" on alerts            for all using (true) with check (true);
create policy "public access" on notifications     for all using (true) with check (true);


-- ------------------------------------------------------------
-- 5. 视频表新增 is_viral 字段 (若不存在)
-- ------------------------------------------------------------
do $$
begin
  if not exists (select 1 from information_schema.columns
    where table_name = 'videos' and column_name = 'is_viral') then
    alter table videos add column is_viral boolean default false;
  end if;
end $$;

-- ------------------------------------------------------------
-- 6. 账号表新增 is_anomalous 字段
-- ------------------------------------------------------------
do $$
begin
  if not exists (select 1 from information_schema.columns
    where table_name = 'accounts' and column_name = 'is_anomalous') then
    alter table accounts add column is_anomalous boolean default false;
  end if;
end $$;
