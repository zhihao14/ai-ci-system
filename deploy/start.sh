#!/bin/bash
set -e

echo "========================================"
echo "  AI-CI System Backend Starting..."
echo "========================================"

# 启动所有 FastAPI 服务 (后台运行)
cd /app/backend

uvicorn main:app              --host 0.0.0.0 --port 8000 &
uvicorn main_accounts:app     --host 0.0.0.0 --port 8001 &
uvicorn main_viral:app        --host 0.0.0.0 --port 8002 &
uvicorn main_multi:app        --host 0.0.0.0 --port 8003 &
uvicorn main_router:app       --host 0.0.0.0 --port 8004 &
uvicorn main_anomaly:app      --host 0.0.0.0 --port 8005 &
uvicorn main_content:app      --host 0.0.0.0 --port 8006 &
uvicorn main_agents:app       --host 0.0.0.0 --port 8007 &
uvicorn main_auth:app         --host 0.0.0.0 --port 8008 &
uvicorn main_monitor:app     --host 0.0.0.0 --port 8009 &
uvicorn main_ws:app           --host 0.0.0.0 --port 8010 &
uvicorn main_marketplace:app  --host 0.0.0.0 --port 8011 &

echo "All 12 FastAPI services started."

# 启动 nginx 反向代理
echo "Starting nginx..."
nginx -g "daemon off;"
