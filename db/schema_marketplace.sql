-- ============================================================
-- API Marketplace - 数据库 Schema
-- 允许外部开发者通过 API Key 接入系统
--
-- 新增 3 张表:
--   1. api_keys          — 开发者 API Key (独立于用户系统的 profiles.api_key)
--   2. marketplace_logs  — API 调用日志 (每次调用一条)
--   3. api_products      — 开放 API 产品目录 (定价/描述/限流)
--
-- 依赖: 已有 accounts / videos / ai_analysis 表
-- ============================================================

-- ------------------------------------------------------------
-- 1. api_keys — 开发者 API Key
--    每个开发者可注册多个 Key (如不同项目用不同 Key)
-- ------------------------------------------------------------
create table if not exists api_keys (
  id            uuid        primary key default gen_random_uuid(),

  -- Key 信息
  key           text        unique not null,                -- API Key (如 mk_xxxx...)
  name          text        not null,                       -- Key 名称 (如 "我的项目")
  description   text,                                       -- 描述

  -- 关联用户 (可选, 如关联则可在 Dashboard 管理)
  user_id       uuid        references auth.users(id) on delete set null,
  tenant_id     uuid        references tenants(id) on delete set null,

  -- 套餐
  plan          text        not null default 'free',        -- 'free' | 'pro' | 'enterprise'

  -- 限流配置
  rate_limit_per_min   integer not null default 10,        -- 每分钟调用上限
  rate_limit_per_day   integer not null default 100,       -- 每日调用上限

  -- 允许调用的 API (数组)
  allowed_apis  jsonb       default '["analyze_video","competitor_monitor","generate_strategy"]'::jsonb,

  -- 状态
  is_active     boolean     not null default true,
  expires_at    timestamptz,                                -- 过期时间 (NULL = 永不过期)

  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  last_used_at  timestamptz
);

-- 索引
create index if not exists idx_api_keys_key    on api_keys(key);
create index if not exists idx_api_keys_user   on api_keys(user_id);
create index if not exists idx_api_keys_tenant on api_keys(tenant_id);

-- 自动更新 updated_at
create or replace function trg_api_keys_set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists set_updated_at on api_keys;
create trigger set_updated_at
  before update on api_keys
  for each row execute function trg_api_keys_set_updated_at();


-- ------------------------------------------------------------
-- 2. marketplace_logs — API 调用日志
--    每次外部调用记录一条, 用于计费和排查
-- ------------------------------------------------------------
create table if not exists marketplace_logs (
  id            uuid        primary key default gen_random_uuid(),

  api_key_id    uuid        references api_keys(id) on delete set null,
  api_key_name  text,                                       -- Key 名称快照

  -- 调用信息
  api_name      text        not null,                       -- 'analyze_video' | 'competitor_monitor' | 'generate_strategy'
  endpoint      text        not null,                       -- '/v1/analyze_video'
  method        text        not null default 'POST',

  -- 请求信息 (摘要)
  request_summary  jsonb,                                  -- 请求参数摘要 (不含敏感数据)

  -- 响应信息
  status_code   integer     not null default 200,
  response_time_ms integer,                                -- 耗时

  -- AI Token 消耗
  prompt_tokens     integer default 0,
  completion_tokens integer default 0,

  -- 错误
  error         text,

  -- 调用者信息
  client_ip     text,
  user_agent    text,

  called_at     timestamptz not null default now()
);

-- 索引
create index if not exists idx_logs_api_key   on marketplace_logs(api_key_id);
create index if not exists idx_logs_api_name  on marketplace_logs(api_name);
create index if not exists idx_logs_called_at on marketplace_logs(called_at desc);
create index if not exists idx_logs_status    on marketplace_logs(status_code);


-- ------------------------------------------------------------
-- 3. api_products — 开放 API 产品目录
--    定义每个 API 的定价/描述/参数说明
-- ------------------------------------------------------------
create table if not exists api_products (
  id            uuid        primary key default gen_random_uuid(),

  name          text        unique not null,                -- 'analyze_video' | 'competitor_monitor' | 'generate_strategy'
  display_name  text        not null,                       -- 显示名
  description   text,                                       -- 详细描述
  category      text        not null default 'analysis',    -- 'analysis' | 'monitor' | 'strategy'

  -- 定价 (每次调用消耗的额度)
  cost_per_call integer     not null default 1,             -- 每次调用消耗额度
  free_quota    integer     not null default 10,            -- 免费额度 (每月)

  -- 文档
  input_schema  jsonb,                                      -- 输入参数 JSON Schema
  output_schema jsonb,                                      -- 输出格式说明
  example_request  jsonb,                                  -- 请求示例
  example_response jsonb,                                  -- 响应示例

  -- 状态
  is_active     boolean     not null default true,
  is_featured   boolean     not null default false,         -- 是否首页推荐

  created_at    timestamptz not null default now()
);

-- 插入默认产品
insert into api_products (name, display_name, description, category, cost_per_call, free_quota, is_featured, example_request, example_response)
values
  (
    'analyze_video',
    '视频爆款分析',
    '输入视频数据数组, AI 提炼爆款规律, 返回爆款原因、标题结构、内容套路和选题建议。支持 1-50 条视频批量分析。',
    'analysis',
    2,
    10,
    true,
    '{"videos":[{"title":"3分钟学会抖音运营","like_count":99999,"comment_count":1200,"share_count":800,"view_count":500000}],"model":"auto"}'::jsonb,
    '{"overview":"...","viral_reasons":[...],"title_patterns":[...],"content_tactics":[...],"topic_suggestions":[...]}'::jsonb
  ),
  (
    'competitor_monitor',
    '竞品账号监控',
    '输入竞品账号 URL, 自动采集最新视频并入库, 可选自动 AI 分析。支持抖音、小红书、YouTube、TikTok 多平台。',
    'monitor',
    5,
    5,
    true,
    '{"platform":"douyin","url":"https://www.douyin.com/user/xxx","max_videos":20,"auto_analyze":true}'::jsonb,
    '{"account_id":"...","crawled":15,"new_videos":3,"analysis_id":"...","analysis_summary":"..."}'::jsonb
  ),
  (
    'generate_strategy',
    '运营策略生成',
    '输入竞品视频数据, AI 生成改写标题、新脚本、相似选题和综合运营策略。一次调用生成全套内容方案。',
    'strategy',
    3,
    5,
    true,
    '{"video":{"title":"3分钟学会抖音运营","like_count":99999},"model":"auto","count":20}'::jsonb,
    '{"titles":[...],"scripts":[...],"topics":[...],"strategy_summary":{...}}'::jsonb
  )
on conflict (name) do nothing;


-- ------------------------------------------------------------
-- 4. RLS (演示开放, 生产环境需收紧)
-- ------------------------------------------------------------
alter table api_keys         enable row level security;
alter table marketplace_logs enable row level security;
alter table api_products     enable row level security;

drop policy if exists "public access" on api_keys;
drop policy if exists "public access" on marketplace_logs;
drop policy if exists "public access" on api_products;
create policy "public access" on api_keys         for all using (true) with check (true);
create policy "public access" on marketplace_logs for all using (true) with check (true);
create policy "public access" on api_products    for all using (true) with check (true);


-- ------------------------------------------------------------
-- 5. 视图: API Key 使用统计
-- ------------------------------------------------------------
create or replace view v_api_key_usage as
select
  k.id as api_key_id,
  k.name as api_key_name,
  k.plan,
  k.rate_limit_per_day,
  count(l.id) as today_calls,
  sum(case when l.status_code >= 400 then 1 else 0 end) as today_errors,
  sum(l.prompt_tokens) as today_prompt_tokens,
  sum(l.completion_tokens) as today_completion_tokens
from api_keys k
left join marketplace_logs l
  on l.api_key_id = k.id
  and l.called_at >= date_trunc('day', now())
group by k.id, k.name, k.plan, k.rate_limit_per_day;


-- ============================================================
-- 完. 执行后:
--   1. api_products 已有 3 个默认产品
--   2. 可通过 INSERT INTO api_keys 创建开发者 Key
--   3. 每次调用 API 自动记录到 marketplace_logs
-- ============================================================
