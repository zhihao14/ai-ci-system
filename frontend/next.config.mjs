/** @type {import('next').NextConfig} */

// 生产环境: 所有后端 API 通过 Railway 统一域名 + nginx 反代
// 开发环境: 各服务直连 localhost:PORT
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost";

// 路由表: 前端路径前缀 → 后端服务端口
const ROUTES = [
  { prefix: "/api",          port: 8000, path: "/api" },
  { prefix: "/be/accounts",  port: 8001, path: "" },
  { prefix: "/be/viral",     port: 8002, path: "" },
  { prefix: "/be/multi",     port: 8003, path: "" },
  { prefix: "/be/router",   port: 8004, path: "" },
  { prefix: "/be/anomaly",  port: 8005, path: "" },
  { prefix: "/be/content",   port: 8006, path: "" },
  { prefix: "/be/agents",    port: 8007, path: "" },
  { prefix: "/be/auth",      port: 8008, path: "" },
  { prefix: "/be/monitor",   port: 8009, path: "" },
  { prefix: "/be/market",    port: 8011, path: "" },
];

const nextConfig = {
  output: "standalone",
  async rewrites() {
    const isProd = process.env.NODE_ENV === "production";
    return ROUTES.map(({ prefix, port, path }) => ({
      source: `${prefix}/:path*`,
      destination: isProd
        ? `${BACKEND_URL}${path}/:path*`
        : `http://localhost:${port}${path}/:path*`,
    }));
  },
};
export default nextConfig;
