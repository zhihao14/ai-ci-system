#!/bin/bash
set -e

# ============================================================
# AI-CI System 一键部署脚本
# 使用前: gh auth login
# ============================================================

REPO_NAME="ai-ci-system"
REPO_DESC="AI Competitive Intelligence System - SaaS Platform"

echo "========================================"
echo "  AI-CI System Deployment Setup"
echo "========================================"

# ---- 1. 检查 GitHub 认证 ----
if ! gh auth status &>/dev/null; then
    echo "❌ 未登录 GitHub CLI"
    echo "请先运行: gh auth login"
    echo "完成认证后重新执行此脚本"
    exit 1
fi
echo "✅ GitHub 已认证"

# ---- 2. 创建 GitHub 仓库 ----
echo ""
echo "→ 创建 GitHub 仓库..."
if gh repo view "$REPO_NAME" &>/dev/null; then
    echo "  仓库已存在, 跳过创建"
else
    gh repo create "$REPO_NAME" --public --description "$REPO_DESC" --source=. --remote=origin
    echo "✅ GitHub 仓库已创建"
fi

# ---- 3. 推送代码 ----
echo ""
echo "→ 推送代码到 GitHub..."
git push -u origin main || git push -u origin master
echo "✅ 代码已推送到 GitHub"

# ---- 4. 配置 GitHub Actions Secrets ----
echo ""
echo "→ 配置 GitHub Actions Secrets..."
echo ""
echo "请在 GitHub repo Settings → Secrets and variables → Actions 中添加以下 Secrets:"
echo ""
echo "  必需 Secrets:"
echo "  ┌─────────────────────┬──────────────────────────────────┐"
echo "  │ RAILWAY_TOKEN       │ Railway Account Token             │"
echo "  │ RAILWAY_SERVICE_ID  │ Railway Service ID                │"
echo "  │ VERCEL_TOKEN        │ Vercel Access Token               │"
echo "  │ VERCEL_ORG_ID       │ Vercel Team/User ID               │"
echo "  │ VERCEL_PROJECT_ID   │ Vercel Project ID                 │"
echo "  └─────────────────────┴──────────────────────────────────┘"
echo ""
echo "  获取方式:"
echo "  • Railway Token:   https://railway.com/account/tokens"
echo "  • Vercel Token:    https://vercel.com/account/tokens"
echo "  • Vercel Org/Project ID: vercel link 后查看 .vercel/project.json"
echo ""

# ---- 5. 提示 Vercel + Railway 配置 ----
echo "→ Vercel 配置:"
echo "  1. 访问 https://vercel.com/new"
echo "  2. 导入 GitHub 仓库 ai-ci-system"
echo "  3. Framework Preset: Next.js (自动检测)"
echo "  4. Root Directory: frontend"
echo "  5. 配置环境变量:"
echo "     • NEXT_PUBLIC_SUPABASE_URL"
echo "     • NEXT_PUBLIC_SUPABASE_ANON_KEY"
echo "     • BACKEND_URL (Railway 部署后的域名)"
echo "     • NEXT_PUBLIC_WS_URL (wss://Railway域名/ws)"
echo ""
echo "→ Railway 配置:"
echo "  1. 访问 https://railway.com/new"
echo "  2. Deploy from GitHub repo → 选择 ai-ci-system"
echo "  3. Railway 自动检测 railway.json + Dockerfile"
echo "  4. 配置环境变量 (从 .env.example 复制)"
echo "  5. 部署后获取域名, 填入 Vercel 的 BACKEND_URL"
echo ""

echo "========================================"
echo "  ✅ 所有配置文件已就绪!"
echo "  完成以上步骤后, 每次 push to main 即自动 CI/CD"
echo "========================================"
