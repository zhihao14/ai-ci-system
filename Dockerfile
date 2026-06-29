# ============================================================
# AI-CI System Backend Dockerfile
# Python (FastAPI) + Node.js (Playwright crawler) + nginx
# ============================================================

FROM python:3.10-slim

# 安装系统依赖 + nginx
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Node.js 20 (爬虫需要)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装 Python 依赖
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# 安装爬虫依赖 + Playwright 浏览器
COPY crawler /app/crawler
RUN cd /app/crawler && npm install --production \
    && cd /app/crawler/shared && npm install --production \
    && cd /app/crawler/douyin && npm install --production \
    && cd /app/crawler/tiktok && npm install --production \
    && cd /app/crawler/youtube && npm install --production \
    && cd /app/crawler/xiaohongshu && npm install --production \
    && npx playwright install chromium --with-deps

# 复制后端代码
COPY backend /app/backend

# 复制 nginx 配置 + 启动脚本
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/start.sh /app/start.sh
RUN chmod +x /app/start.sh

# 复制数据库 schema (供初始化参考)
COPY db /app/db

EXPOSE 80

CMD ["/app/start.sh"]
