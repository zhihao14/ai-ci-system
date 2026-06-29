# AI Competitive Intelligence System

AI 驱动的竞争情报 SaaS 平台 — 多平台数据采集、AI 分析、异常检测、内容生成、实时监控一体化。

## 架构

```
┌─────────────────────────────────────────────────────┐
│                   Frontend (Vercel)                   │
│              Next.js 14 + TailwindCSS                │
│         Glassmorphism UI + Framer Motion            │
├─────────────────────────────────────────────────────┤
│                    Backend (Railway)                   │
│                   nginx 反向代理 :80                   │
├──────┬──────┬──────┬──────┬──────┬──────┬──────────┤
│ 8000 │ 8001 │ 8002 │ 8003 │ 8004 │ 8005 │   ...    │
│情报  │账号  │爆款  │多平台│AI路由│异常  │  8006-   │
│分析  │视频  │分析  │采集  │     │检测  │  8011    │
├──────┴──────┴──────┴──────┴──────┴──────┴──────────┤
│              Crawler (Playwright Node.js)            │
│         Douyin / Xiaohongshu / YouTube / TikTok      │
├─────────────────────────────────────────────────────┤
│               Supabase PostgreSQL                    │
│        RLS 多租户隔离 + Auth + Realtime              │
├─────────────────────────────────────────────────────┤
│            AI Layer (DeepSeek / Claude / GLM)        │
└─────────────────────────────────────────────────────┘
```

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 14, TailwindCSS, Framer Motion, Recharts, shadcn/ui |
| 后端 | FastAPI, Pydantic, uvicorn (12 个微服务) |
| 数据库 | Supabase PostgreSQL, RLS |
| 爬虫 | Node.js, Playwright (4 平台) |
| AI | DeepSeek (主), Claude (备), GLM (选), AI Router 统一路由 |
| 部署 | Vercel (前端), Railway (后端), GitHub Actions (CI/CD) |

## 后端服务端口

| 端口 | 模块 | 入口 |
|---|---|---|
| 8000 | 竞争对手情报分析 | `main.py` |
| 8001 | 账号/视频管理 | `main_accounts.py` |
| 8002 | 爆款分析 | `main_viral.py` |
| 8003 | 多平台采集 | `main_multi.py` |
| 8004 | AI Router | `main_router.py` |
| 8005 | 异常检测 | `main_anomaly.py` |
| 8006 | AI 内容生成 | `main_content.py` |
| 8007 | Multi-Agent | `main_agents.py` |
| 8008 | 用户系统 | `main_auth.py` |
| 8009 | 自动监控 | `main_monitor.py` |
| 8010 | WebSocket 通知 | `main_ws.py` |
| 8011 | API Marketplace | `main_marketplace.py` |

## 目录结构

```
ai-ci-system/
├── backend/                 # Python 后端 (FastAPI)
│   ├── main.py              # 情报分析 (8000)
│   ├── main_accounts.py     # 账号管理 (8001)
│   ├── main_viral.py        # 爆款分析 (8002)
│   ├── main_multi.py        # 多平台采集 (8003)
│   ├── main_router.py       # AI Router (8004)
│   ├── main_anomaly.py      # 异常检测 (8005)
│   ├── main_content.py      # 内容生成 (8006)
│   ├── main_agents.py       # Multi-Agent (8007)
│   ├── main_auth.py         # 用户系统 (8008)
│   ├── main_monitor.py      # 自动监控 (8009)
│   ├── main_ws.py           # WebSocket (8010)
│   ├── main_marketplace.py  # API Marketplace (8011)
│   ├── ai_router/           # AI 统一路由层
│   ├── agents/              # Agent 框架 (4 个 Agent)
│   ├── requirements.txt
│   └── ...
├── crawler/                 # Node.js 爬虫 (Playwright)
│   ├── shared/base.mjs      # 共享模块
│   ├── douyin/              # 抖音爬虫
│   ├── xiaohongshu/         # 小红书爬虫
│   ├── youtube/             # YouTube 爬虫
│   ├── tiktok/              # TikTok 爬虫
│   └── crawl.js             # 网站爬虫
├── db/                      # SQL Schema
│   ├── schema.sql
│   ├── schema_accounts.sql
│   ├── schema_anomaly.sql
│   ├── schema_auth.sql
│   ├── schema_marketplace.sql
│   └── schema_monitor.sql
├── frontend/                # Next.js 前端
│   ├── app/                 # App Router 页面
│   ├── components/          # UI 组件
│   ├── lib/                 # 工具库
│   └── package.json
├── deploy/                  # 部署配置
│   ├── nginx.conf           # nginx 反向代理
│   └── start.sh             # 启动脚本
├── .github/workflows/       # GitHub Actions
│   ├── ci.yml               # CI: 语法检查 + 构建
│   └── deploy.yml           # CD: Railway + Vercel
├── Dockerfile               # 后端镜像
├── Dockerfile.frontend      # 前端镜像
├── docker-compose.yml       # 本地编排
├── vercel.json              # Vercel 部署
├── railway.json             # Railway 部署
└── .env.example             # 环境变量模板
```

## 本地开发

### 1. 环境准备

```bash
# 克隆仓库
git clone <repo-url>
cd ai-ci-system

# 复制环境变量模板
cp .env.example .env
# 填入 Supabase / DeepSeek / Claude 等凭据
```

### 2. 初始化数据库

在 Supabase SQL Editor 中按顺序执行:
```bash
db/schema.sql
db/schema_accounts.sql
db/schema_anomaly.sql
db/schema_auth.sql
db/schema_monitor.sql
db/schema_marketplace.sql
```

### 3. 启动爬虫依赖

```bash
cd crawler/shared && npm install && npx playwright install chromium
cd ../douyin && npm install
cd ../tiktok && npm install
cd ../youtube && npm install
cd ../xiaohongshu && npm install
cd ..
```

### 4. 启动后端

```bash
cd backend
pip install -r requirements.txt
# 启动所有服务 (或按需启动)
uvicorn main:app --port 8000 &
uvicorn main_accounts:app --port 8001 &
uvicorn main_viral:app --port 8002 &
# ... 其余服务同理
```

### 5. 启动前端

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:3000
```

## Docker 部署

```bash
# 一键启动 (后端 + 前端)
docker-compose up -d

# 或单独构建后端
docker build -t ai-ci-backend .
docker run -p 8000:80 --env-file .env ai-ci-backend
```

## 生产部署

### Railway (后端)

1. 在 Railway 创建项目, 连接 GitHub 仓库
2. Railway 自动检测 `railway.json` + `Dockerfile`
3. 配置环境变量 (Supabase / DeepSeek / Claude 等)
4. 部署后获取 Railway 域名 (如 `xxx.up.railway.app`)

### Vercel (前端)

1. 在 Vercel 创建项目, 导入 GitHub 仓库
2. Vercel 自动检测 `vercel.json` + Next.js
3. 配置环境变量:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `BACKEND_URL` (Railway 域名, 如 `https://xxx.up.railway.app`)
   - `NEXT_PUBLIC_WS_URL` (如 `wss://xxx.up.railway.app/ws`)
4. 部署完成

### GitHub Actions CI/CD

需要在 GitHub repo Settings → Secrets 中配置:

| Secret | 用途 |
|---|---|
| `RAILWAY_TOKEN` | Railway API Token |
| `RAILWAY_SERVICE_ID` | Railway 服务 ID |
| `VERCEL_TOKEN` | Vercel API Token |
| `VERCEL_ORG_ID` | Vercel 组织 ID |
| `VERCEL_PROJECT_ID` | Vercel 项目 ID |

CI 流程 (PR / push):
1. Python 语法检查 + 依赖验证
2. Node.js 爬虫依赖验证
3. Next.js 类型检查 + 构建

CD 流程 (push to main):
1. CI 通过 → 部署后端到 Railway
2. CI 通过 → 部署前端到 Vercel

## License

MIT
