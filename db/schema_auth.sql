-- ============================================================
-- 用户系统 - 数据库 Schema
-- 依赖: Supabase Auth (auth.users) + 已有 accounts/videos/ai_analysis 表
--
-- 新增 4 张表:
--   1. tenants        — 租户 (组织/工作空间)
--   2. profiles       — 用户档案 (扩展 auth.users, 关联租户)
--   3. tenant_members — 租户成员关系 (多用户共属一个租户)
--   4. api_usage      — API 调用额度记录 (按天/按接口)
--
-- 多租户数据隔离:
--   accounts / videos / ai_analysis 新增 tenant_id 字段
--   RLS 策略按 tenant_id 隔离, 用户只能访问自己租户的数据
-- ============================================================

-- ------------------------------------------------------------
-- 1. tenants — 租户表
--    每个租户 = 一个独立的工作空间 (如某公司/某团队)
--    用户注册时自动创建一个个人租户, 也可被邀请加入其他租户
-- ------------------------------------------------------------
create table if not exists tenants (
  id            uuid        primary key default gen_random_uuid(),

  -- 租户信息
  name          text        not null,                       -- 租户名称
  slug          text        unique not null,                -- URL 友好标识 (如 my-company)
  plan          text        not null default 'free',        -- 'free' | 'pro' | 'enterprise'

  -- 额度配置 (按 plan 自动设置, 也可手动调整)
  -- free: 100次/天, pro: 1000次/天, enterprise: 10000次/天
  daily_quota   integer     not null default 100,           -- 每日 API 调用上限
  monthly_quota integer     not null default 3000,         -- 每月 API 调用上限

  -- 状态
  is_active     boolean     not null default true,
  settings      jsonb       default '{}'::jsonb,            -- 租户级配置 (通知/AI模型偏好等)

  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create or replace function trg_tenants_set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists set_updated_at on tenants;
create trigger set_updated_at
  before update on tenants
  for each row execute function trg_tenants_set_updated_at();

create index if not exists idx_tenants_slug on tenants(slug);


-- ------------------------------------------------------------
-- 2. profiles — 用户档案
--    扩展 Supabase auth.users, 每个用户关联一个当前租户
-- ------------------------------------------------------------
create table if not exists profiles (
  id            uuid        primary key references auth.users(id) on delete cascade,

  -- 用户信息
  username      text        unique,                          -- 用户名
  full_name     text,                                        -- 显示名
  avatar_url    text,                                        -- 头像
  bio           text,                                        -- 个人简介

  -- 当前活跃租户 (用户可在多个租户间切换)
  current_tenant_id uuid references tenants(id) on delete set null,

  -- 个人 API Key (用于调用后端 API, 非必须, 也可用 Supabase JWT)
  api_key       text        unique,

  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create or replace function trg_profiles_set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists set_updated_at on profiles;
create trigger set_updated_at
  before update on profiles
  for each row execute function trg_profiles_set_updated_at();

-- 注册时自动创建 profile (通过 trigger 监听 auth.users)
create or replace function handle_new_user()
returns trigger as $$
declare
  new_tenant_id uuid;
begin
  -- 为新用户创建个人租户
  insert into tenants (name, slug, plan, daily_quota, monthly_quota)
  values (
    coalesce(new.raw_user_meta_data->>'full_name', new.email) || ' 的空间',
    'user-' || substring(new.id::text, 1, 8),
    'free',
    100,
    3000
  )
  returning id into new_tenant_id;

  -- 创建用户档案
  insert into profiles (id, username, full_name, current_tenant_id, api_key)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'username', split_part(new.email, '@', 1)),
    coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
    new_tenant_id,
    encode(gen_random_bytes(24), 'hex')  -- 生成 48 字符随机 API Key
  );

  -- 加入租户为 owner
  insert into tenant_members (tenant_id, user_id, role)
  values (new_tenant_id, new.id, 'owner');

  return new;
end;
$$ language plpgsql security definer;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();


-- ------------------------------------------------------------
-- 3. tenant_members — 租户成员关系
--    一个租户可有多个成员, 一个用户可属多个租户
-- ------------------------------------------------------------
create table if not exists tenant_members (
  id            uuid        primary key default gen_random_uuid(),

  tenant_id     uuid        not null references tenants(id) on delete cascade,
  user_id       uuid        not null references auth.users(id) on delete cascade,

  -- 角色: owner (所有者) | admin (管理员) | member (普通成员)
  role          text        not null default 'member',

  -- 加入时间
  joined_at     timestamptz not null default now(),

  unique (tenant_id, user_id)
);

create index if not exists idx_members_tenant on tenant_members(tenant_id);
create index if not exists idx_members_user   on tenant_members(user_id);


-- ------------------------------------------------------------
-- 4. api_usage — API 调用额度记录
--    每次调用 API 时插入一条, 用于统计和限制
-- ------------------------------------------------------------
create table if not exists api_usage (
  id            uuid        primary key default gen_random_uuid(),

  user_id       uuid        references auth.users(id) on delete cascade,
  tenant_id     uuid        references tenants(id) on delete cascade,

  -- 调用信息
  endpoint      text        not null,                        -- '/pipeline' | '/crawl' | '/analyze' 等
  method        text        not null default 'POST',          -- 'GET' | 'POST' | ...
  status_code   integer     not null default 200,

  -- Token 消耗 (AI 接口才有)
  prompt_tokens     integer default 0,
  completion_tokens integer default 0,

  -- 调用时间
  called_at     timestamptz not null default now()
);

-- 索引: 按租户+日期查询 (额度检查)
create index if not exists idx_usage_tenant_day on api_usage(tenant_id, called_at desc);
create index if not exists idx_usage_user_day   on api_usage(user_id, called_at desc);
create index if not exists idx_usage_endpoint   on api_usage(endpoint);


-- ============================================================
-- 5. 多租户数据隔离: 为已有表添加 tenant_id
-- ============================================================

-- accounts 表添加 tenant_id
do $$ begin
  if not exists (select 1 from information_schema.columns
    where table_name = 'accounts' and column_name = 'tenant_id') then
    alter table accounts add column tenant_id uuid references tenants(id) on delete set null;
  end if;
end $$;

-- videos 表添加 tenant_id
do $$ begin
  if not exists (select 1 from information_schema.columns
    where table_name = 'videos' and column_name = 'tenant_id') then
    alter table videos add column tenant_id uuid references tenants(id) on delete set null;
  end if;
end $$;

-- ai_analysis 表添加 tenant_id
do $$ begin
  if not exists (select 1 from information_schema.columns
    where table_name = 'ai_analysis' and column_name = 'tenant_id') then
    alter table ai_analysis add column tenant_id uuid references tenants(id) on delete set null;
  end if;
end $$;

-- 索引
create index if not exists idx_accounts_tenant on accounts(tenant_id) where tenant_id is not null;
create index if not exists idx_videos_tenant   on videos(tenant_id)   where tenant_id is not null;
create index if not exists idx_analysis_tenant on ai_analysis(tenant_id) where tenant_id is not null;


-- ============================================================
-- 6. RLS: 多租户隔离策略
--    替换之前的 "public access" 策略为基于 tenant_id 的隔离
-- ============================================================

-- ---- profiles: 用户只能看自己的 profile ----
alter table profiles enable row level security;
drop policy if exists "profiles_self_select" on profiles;
drop policy if exists "profiles_self_update" on profiles;
create policy "profiles_self_select" on profiles for select using (auth.uid() = id);
create policy "profiles_self_update" on profiles for update using (auth.uid() = id);

-- ---- tenants: 租户成员可见 ----
alter table tenants enable row level security;
drop policy if exists "tenants_member_select" on tenants;
create policy "tenants_member_select" on tenants for select
  using (
    exists (
      select 1 from tenant_members
      where tenant_members.tenant_id = tenants.id
      and tenant_members.user_id = auth.uid()
    )
  );

-- ---- tenant_members: 成员可见同租户的成员列表 ----
alter table tenant_members enable row level security;
drop policy if exists "members_self_or_tenant" on tenant_members;
create policy "members_self_or_tenant" on tenant_members for select
  using (
    user_id = auth.uid()
    or exists (
      select 1 from tenant_members tm2
      where tm2.tenant_id = tenant_members.tenant_id
      and tm2.user_id = auth.uid()
    )
  );

-- ---- api_usage: 用户只能看自己的调用记录 ----
alter table api_usage enable row level security;
drop policy if exists "usage_self_select" on api_usage;
drop policy if exists "usage_self_insert" on api_usage;
create policy "usage_self_select" on api_usage for select using (user_id = auth.uid());
create policy "usage_self_insert" on api_usage for insert with check (user_id = auth.uid());

-- ---- accounts: 按租户隔离 ----
drop policy if exists "public access" on accounts;
drop policy if exists "accounts_tenant_select" on accounts;
drop policy if exists "accounts_tenant_insert" on accounts;
drop policy if exists "accounts_tenant_update" on accounts;
drop policy if exists "accounts_tenant_delete" on accounts;
create policy "accounts_tenant_select" on accounts for select
  using (
    tenant_id is null  -- 兼容旧数据 (无租户的可读)
    or exists (
      select 1 from tenant_members
      where tenant_members.tenant_id = accounts.tenant_id
      and tenant_members.user_id = auth.uid()
    )
  );
create policy "accounts_tenant_insert" on accounts for insert
  with check (
    tenant_id is null
    or exists (
      select 1 from tenant_members
      where tenant_members.tenant_id = accounts.tenant_id
      and tenant_members.user_id = auth.uid()
    )
  );
create policy "accounts_tenant_update" on accounts for update
  using (
    tenant_id is null
    or exists (
      select 1 from tenant_members
      where tenant_members.tenant_id = accounts.tenant_id
      and tenant_members.user_id = auth.uid()
    )
  );
create policy "accounts_tenant_delete" on accounts for delete
  using (
    tenant_id is null
    or exists (
      select 1 from tenant_members
      where tenant_members.tenant_id = accounts.tenant_id
      and tenant_members.user_id = auth.uid()
    )
  );

-- ---- videos: 按租户隔离 (通过 account_id 关联) ----
drop policy if exists "public access" on videos;
drop policy if exists "videos_tenant_all" on videos;
create policy "videos_tenant_all" on videos for all
  using (
    exists (
      select 1 from accounts
      where accounts.id = videos.account_id
      and (
        accounts.tenant_id is null
        or exists (
          select 1 from tenant_members
          where tenant_members.tenant_id = accounts.tenant_id
          and tenant_members.user_id = auth.uid()
        )
      )
    )
  )
  with check (
    exists (
      select 1 from accounts
      where accounts.id = videos.account_id
      and (
        accounts.tenant_id is null
        or exists (
          select 1 from tenant_members
          where tenant_members.tenant_id = accounts.tenant_id
          and tenant_members.user_id = auth.uid()
        )
      )
    )
  );

-- ---- ai_analysis: 按租户隔离 ----
drop policy if exists "public access" on ai_analysis;
drop policy if exists "analysis_tenant_all" on ai_analysis;
create policy "analysis_tenant_all" on ai_analysis for all
  using (
    tenant_id is null
    or exists (
      select 1 from tenant_members
      where tenant_members.tenant_id = ai_analysis.tenant_id
      and tenant_members.user_id = auth.uid()
    )
  )
  with check (
    tenant_id is null
    or exists (
      select 1 from tenant_members
      where tenant_members.tenant_id = ai_analysis.tenant_id
      and tenant_members.user_id = auth.uid()
    )
  );

-- ---- metrics_snapshots / alerts / notifications: 按租户隔离 ----
-- 为异常检测表也添加 tenant_id (可选, 兼容旧数据)
do $$ begin
  if not exists (select 1 from information_schema.columns
    where table_name = 'alerts' and column_name = 'tenant_id') then
    alter table alerts add column tenant_id uuid references tenants(id) on delete set null;
  end if;
end $$;

drop policy if exists "public access" on metrics_snapshots;
drop policy if exists "public access" on alerts;
drop policy if exists "public access" on notifications;

-- 演示阶段仍开放 (生产环境需按 tenant_id 收紧)
create policy "public access" on metrics_snapshots for all using (true) with check (true);
create policy "public access" on notifications     for all using (true) with check (true);

-- alerts: 按 tenant_id 隔离 (兼容旧数据)
drop policy if exists "alerts_tenant_select" on alerts;
create policy "alerts_tenant_select" on alerts for select
  using (
    tenant_id is null
    or exists (
      select 1 from tenant_members
      where tenant_members.tenant_id = alerts.tenant_id
      and tenant_members.user_id = auth.uid()
    )
  );


-- ============================================================
-- 7. 视图: 今日额度统计 (便于后端快速查询)
-- ============================================================
create or replace view v_daily_usage as
select
  tenant_id,
  date_trunc('day', called_at) as usage_date,
  count(*) as total_calls,
  sum(prompt_tokens) as total_prompt_tokens,
  sum(completion_tokens) as total_completion_tokens
from api_usage
group by tenant_id, date_trunc('day', called_at);


-- ============================================================
-- 完. 执行后:
--   1. 用户注册时自动创建租户 + profile + tenant_members(owner)
--   2. 已有表数据 tenant_id=NULL, 兼容旧数据
--   3. 新数据需在后端写入时带上 tenant_id
-- ============================================================
