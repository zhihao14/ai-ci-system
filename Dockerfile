# ============================================================
# AI-CI System Backend Dockerfile (Railway 优化版)
# 单容器: Python (FastAPI 主服务) + Node.js (爬虫)
# ============================================================

FROM python:3.10-slim

# 安装最小系统依赖 + Node.js 20
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 安装爬虫依赖 + Playwright Chromium
COPY crawler /app/crawler
RUN cd /app/crawler/shared && npm install --production \
    && cd /app/crawler/douyin && npm install --production \
    && cd /app/crawler/tiktok && npm install --production \
    && cd /app/crawler/youtube && npm install --production \
    && cd /app/crawler/xiaohongshu && npm install --production \
    && npx playwright install --with-deps chromium

# 复制后端代码
COPY backend /app/backend

# 复制数据库 schema
COPY db /app/db

# 工作目录设为 backend (uvicorn main:app 需在此目录下)
WORKDIR /app/backend

# 暴露主服务端口 (Railway 会注入 PORT 环境变量)
ENV PORT=8000
EXPOSE 8000

# 启动主服务 (情报分析模块)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
