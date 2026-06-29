// ============================================================
// base.mjs - 多平台爬虫共享基座
//
// 提供:
//   1. createBrowser()  — 反检测浏览器启动 + 登录态持久化
//   2. scrollAndCollect() — 自动滚动触发懒加载
//   3. emit() / emitError() — 统一 JSON 输出格式
//   4. parseArgs() — 命令行参数解析
//   5. ts2str() — 时间戳转字符串
//   6. normalizeItem() — 标准化为统一 VideoItem schema
//
// 统一输出 JSON Schema:
//   {
//     ok: boolean,
//     platform: "douyin" | "xiaohongshu" | "youtube" | "tiktok",
//     account_url: string,
//     account_name: string,
//     account_id: string,          // 平台内用户 ID
//     follower_count: number,
//     count: number,
//     videos: VideoItem[]
//   }
//
// VideoItem 统一字段:
//   {
//     video_id: string,            // 平台内内容唯一 ID
//     title: string,
//     description: string | null,
//     likes: number,
//     comments: number,
//     shares: number,
//     views: number,               // 部分平台无此字段, 填 0
//     publish_time: string | null,  // "YYYY-MM-DD HH:mm:ss"
//     video_url: string | null,
//     cover_url: string | null,
//     type: "video" | "image"       // 小红书有图文帖
//   }
// ============================================================
import { chromium } from "playwright";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// ============================================================
// 默认 UA 与浏览器参数 (各平台可在 createBrowser 中覆盖)
// ============================================================
const DEFAULT_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

const DEFAULT_INIT_SCRIPT = () => {
  // 覆盖 navigator.webdriver, 降低反爬识别
  Object.defineProperty(navigator, "webdriver", { get: () => undefined });
  Object.defineProperty(navigator, "plugins", {
    get: () => [1, 2, 3, 4, 5],
  });
  Object.defineProperty(navigator, "languages", {
    get: () => ["zh-CN", "zh", "en"],
  });
};

// ============================================================
// createBrowser — 启动持久化浏览器上下文
// ============================================================
/**
 * @param {Object} opts
 * @param {boolean} opts.headed — 是否有头模式 (首次登录扫码用)
 * @param {string} opts.dataDir — 持久化目录名 (如 "xiaohongshu")
 * @param {string} [opts.userAgent] — 自定义 UA
 * @param {string} [opts.locale] — 语言
 * @returns {Promise<{context: import('playwright').BrowserContext, page: import('playwright').Page}>}
 */
export async function createBrowser(opts) {
  const userDataDir = path.join(__dirname, "..", opts.dataDir, ".browser-data");
  const context = await chromium.launchPersistentContext(userDataDir, {
    headless: !opts.headed,
    viewport: { width: 1440, height: 900 },
    locale: opts.locale || "zh-CN",
    timezone: "Asia/Shanghai",
    userAgent: opts.userAgent || DEFAULT_UA,
    args: ["--disable-blink-features=AutomationControlled"],
  });
  await context.addInitScript(DEFAULT_INIT_SCRIPT);
  const page = await context.newPage();
  return { context, page };
}

// ============================================================
// scrollAndCollect — 自动滚动 + 收集, 返回收集到的数量
// ============================================================
/**
 * @param {import('playwright').Page} page
 * @param {Object} opts
 * @param {() => Promise<number>} opts.getCount — 返回当前已收集数量
 * @param {number} opts.maxItems — 最大收集数
 * @param {number} [opts.maxRounds] — 最大滚动轮次
 * @param {number} [opts.waitMs] — 每轮等待毫秒
 */
export async function scrollAndCollect(page, opts) {
  const { getCount, maxItems, maxRounds = 40, waitMs = 1500 } = opts;
  let noChange = 0;
  let prevCount = 0;

  for (let i = 0; i < maxRounds; i++) {
    await page.evaluate(() => window.scrollBy(0, window.innerHeight * 2));
    await page.waitForTimeout(waitMs);

    const current = await getCount();
    if (current >= maxItems) break;

    if (current === prevCount) {
      noChange++;
      if (noChange >= 3) break;
    } else {
      noChange = 0;
      prevCount = current;
    }
  }
}

// ============================================================
// parseArgs — 解析命令行参数
// ============================================================
export function parseArgs() {
  const argv = process.argv.slice(2);
  const url = argv.find((a) => !a.startsWith("--"));
  const max = parseInt(
    argv.find((a) => a.startsWith("--max="))?.split("=")[1] || "30",
    10
  );
  const headed = argv.includes("--headed");
  return { url, max, headed };
}

// ============================================================
// emit / emitError — 统一 JSON 输出到 stdout
// ============================================================
export function emit(data) {
  console.log(JSON.stringify(data));
}

export function emitError(platform, url, error) {
  emit({
    ok: false,
    platform,
    account_url: url,
    account_name: "",
    account_id: "",
    follower_count: 0,
    count: 0,
    videos: [],
    error: String(error),
  });
}

// ============================================================
// ts2str — 秒级/毫秒级时间戳 → "YYYY-MM-DD HH:mm:ss"
// ============================================================
export function ts2str(ts, unit = "s") {
  if (!ts) return null;
  const ms = unit === "s" ? ts * 1000 : ts;
  const d = new Date(ms);
  if (isNaN(d.getTime())) return null;
  return d.toISOString().replace("T", " ").slice(0, 19);
}

// ============================================================
// normalizeItem — 标准化为统一 VideoItem
// 兜底缺字段, 保证 schema 一致
// ============================================================
export function normalizeItem(item) {
  return {
    video_id: String(item.video_id || ""),
    title: (item.title || "").trim() || "(无标题)",
    description: item.description || null,
    likes: Number(item.likes) || 0,
    comments: Number(item.comments) || 0,
    shares: Number(item.shares) || 0,
    views: Number(item.views) || 0,
    publish_time: item.publish_time || null,
    video_url: item.video_url || null,
    cover_url: item.cover_url || null,
    type: item.type || "video",
  };
}

// ============================================================
// emitSuccess — 标准化成功输出
// ============================================================
export function emitSuccess(platform, data) {
  emit({
    ok: true,
    platform,
    account_url: data.account_url,
    account_name: data.account_name || "",
    account_id: data.account_id || "",
    follower_count: Number(data.follower_count) || 0,
    count: data.videos.length,
    videos: data.videos.map(normalizeItem),
  });
}
