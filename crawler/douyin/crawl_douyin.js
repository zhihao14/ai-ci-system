// ============================================================
// crawl_douyin.js - 抖音账号视频爬虫 (Playwright)
//
// 调用方式:
//   node crawl_douyin.js <抖音账号URL> [--max=30] [--headed]
//
// 示例:
//   node crawl_douyin.js "https://www.douyin.com/user/MS4wLjABAAAA..." --max=20
//   node crawl_douyin.js "<url>" --headed          # 有头模式(首次登录扫码)
//
// 输出: stdout 一行 JSON
//   { ok: true, account_url, account_name, videos: [{ title, likes, comments,
//     shares, publish_time, video_url, video_id, cover_url }] }
//   { ok: false, error: "..." }
//
// 原理:
//   1. 用持久化 userDataDir 保存登录 Cookie, 首次 --headed 扫码登录后免再次登录
//   2. 拦截抖音 XHR 响应 /aweme/v1/web/aweme/post/ (用户视频列表 API)
//      该接口返回结构化 JSON, 比 DOM 抓取更稳定
//   3. 自动滚动页面触发懒加载, 持续收集直到达到 --max 或无更多
//   4. 若 API 未捕获到, 回退到 DOM 解析
// ============================================================
import { chromium } from "playwright";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

// ---- 参数解析 ----
const argv = process.argv.slice(2);
const accountUrl = argv.find((a) => !a.startsWith("--"));
const maxVideos = parseInt(
  argv.find((a) => a.startsWith("--max="))?.split("=")[1] || "30",
  10
);
const headed = argv.includes("--headed");

if (!accountUrl) {
  console.log(
    JSON.stringify({ ok: false, error: "缺少参数: node crawl_douyin.js <抖音账号URL> [--max=N] [--headed]" })
  );
  process.exit(0);
}

// 持久化目录: 保存登录状态, 首次扫码后后续免登录
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const userDataDir = path.join(__dirname, ".browser-data");

// ============================================================
// 主流程
// ============================================================
(async () => {
  // 用 persistent context 启动 (自动保存 cookie / localStorage)
  const browser = await chromium.launchPersistentContext(userDataDir, {
    headless: !headed,
    viewport: { width: 1440, height: 900 },
    locale: "zh-CN",
    timezone: "Asia/Shanghai",
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    // 反检测: 隐藏 webdriver 标记
    args: ["--disable-blink-features=AutomationControlled"],
  });

  // 注入脚本: 覆盖 navigator.webdriver, 降低被识别概率
  await browser.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => undefined });
    // 覆盖插件/语言检测
    Object.defineProperty(navigator, "plugins", {
      get: () => [1, 2, 3, 4, 5],
    });
    Object.defineProperty(navigator, "languages", {
      get: () => ["zh-CN", "zh", "en"],
    });
  });

  const page = await browser.newPage();

  // ---- 视频数据收集器 ----
  // 方式 A (主): 拦截 API 响应, 提取 aweme_list
  const collected = new Map(); // aweme_id -> 标准化视频对象, 用 Map 去重
  let accountName = "";

  // 监听所有响应, 命中视频列表 API 时解析
  page.on("response", async (response) => {
    const u = response.url();
    // 抖音用户视频列表接口 (web 端)
    if (u.includes("/aweme/v1/web/aweme/post/") || u.includes("/aweme/v1/web/aweme/post")) {
      try {
        const json = await response.json();
        const list = json.aweme_list || json.awemes || [];
        for (const aw of list) {
          const item = normalizeApiItem(aw);
          if (item) collected.set(item.video_id, item);
        }
        // 顺便取账号名
        if (list[0]?.author?.nickname) accountName = list[0].author.nickname;
      } catch {
        /* 响应可能非 JSON (如重定向), 忽略 */
      }
    }
  });

  // ============================================================
  // 1. 导航到账号主页, 等待页面就绪
  // ============================================================
  try {
    await page.goto(accountUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
  } catch (err) {
    await browser.close();
    console.log(JSON.stringify({ ok: false, error: `页面加载失败: ${err.message}` }));
    return;
  }

  // 等待页面关键容器出现 (用户主页 tab 区)
  // 用多选择器兜底, 抖音 DOM 结构会变
  try {
    await page.waitForSelector(
      '[data-e2e="user-tab-list"], [data-e2e="user-post-list"], ' +
        'div[data-e2e="user-info"] , ul[data-e2e="scroll-list"]',
      { timeout: 15000 }
    );
  } catch {
    /* 容器选择器失效不阻塞, 继续尝试滚动 */
  }

  // ============================================================
  // 2. 检测登录状态; 若需要登录且为有头模式, 等待扫码
  // ============================================================
  const needsLogin = await page
    .locator('text=扫码登录, text=登录, [data-e2e="login-container"]')
    .count()
    .catch(() => 0);

  if (needsLogin > 0) {
    if (!headed) {
      await browser.close();
      console.log(
        JSON.stringify({
          ok: false,
          error: "需要登录: 请用 --headed 参数重新运行, 扫码登录后会被持久化保存",
        })
      );
      return;
    }
    console.error("[提示] 请在浏览器中扫码登录抖音, 登录成功后将继续爬取...");
    // 等待登录完成 (URL 不再含 login, 或出现用户内容)
    await page
      .waitForSelector('[data-e2e="user-tab-list"], [data-e2e="user-post-list"]', {
        timeout: 120000, // 给 2 分钟扫码
      })
      .catch(() => {});
  }

  // ============================================================
  // 3. 自动滚动触发懒加载, 持续收集视频
  // ============================================================
  let noChangeRounds = 0;
  let prevSize = 0;
  const maxRounds = 40; // 安全上限, 防止无限滚动

  for (let i = 0; i < maxRounds; i++) {
    // 向下滚动
    await page.evaluate(() => window.scrollBy(0, window.innerHeight * 2));
    // 等待新内容/接口返回
    await page.waitForTimeout(1200);

    // 检查是否已收集够
    if (collected.size >= maxVideos) break;

    // 检查是否已无新增 (连续 3 轮无变化则结束)
    if (collected.size === prevSize) {
      noChangeRounds++;
      if (noChangeRounds >= 3) break;
    } else {
      noChangeRounds = 0;
      prevSize = collected.size;
    }
  }

  // ============================================================
  // 4. 若 API 拦截未拿到数据, 回退到 DOM 解析
  // ============================================================
  if (collected.size === 0) {
    console.error("[提示] API 未捕获到视频, 尝试 DOM 解析...");
    const domVideos = await extractFromDom(page);
    for (const v of domVideos) collected.set(v.video_id, v);
  }

  // ============================================================
  // 5. 取账号名 (DOM 兜底)
  // ============================================================
  if (!accountName) {
    accountName =
      (await page
        .locator('[data-e2e="user-info"] h1, [data-e2e="nickname"]')
        .first()
        .textContent()
        .catch(() => "")) || "";
  }

  await browser.close();

  // ---- 输出结果 ----
  const videos = Array.from(collected.values()).slice(0, maxVideos);
  console.log(
    JSON.stringify({
      ok: true,
      account_url: accountUrl,
      account_name: accountName.trim(),
      count: videos.length,
      videos,
    })
  );
})().catch((err) => {
  console.log(JSON.stringify({ ok: false, error: `爬虫异常: ${String(err)}` }));
});

// ============================================================
// 工具函数: 把抖音 API 的 aweme 对象标准化为目标输出格式
// ============================================================
function normalizeApiItem(aw) {
  if (!aw || !aw.aweme_id) return null;
  const stat = aw.statistics || {};
  const video = aw.video || {};
  // play_addr.url_list 可能有多条, 取第一条
  const playUrls = video.play_addr?.url_list || [];
  // 尝试得到无水印链接: 将 playwm 替换为 play
  const videoUrl = playUrls[0]
    ? playUrls[0].replace("playwm", "play")
    : null;
  const coverUrls = video.cover?.url_list || video.origin_cover?.url_list || [];

  return {
    video_id: aw.aweme_id,
    title: (aw.desc || "").trim() || "(无标题)",
    likes: stat.digg_count ?? 0,
    comments: stat.comment_count ?? 0,
    shares: stat.share_count ?? 0,
    // create_time 是秒级时间戳, 转为 ISO 字符串
    publish_time: aw.create_time
      ? new Date(aw.create_time * 1000).toISOString().replace("T", " ").slice(0, 19)
      : null,
    video_url: videoUrl,
    cover_url: coverUrls[0] || null,
  };
}

// ============================================================
// 工具函数: DOM 兜底解析 (当 API 未命中时使用)
// 抖音 DOM class 名经混淆会变, 这里用 data-e2e + 结构特征定位
// ============================================================
async function extractFromDom(page) {
  return await page.evaluate(() => {
    const videos = [];
    // 视频卡: 带有 /video/ 链接的 <a>, 包在 li/div 内
    const cards = document.querySelectorAll(
      '[data-e2e="user-tab-list"] a[href*="/video/"], ' +
        'li a[href*="/video/"], [data-e2e="user-post-list"] a[href*="/video/"]'
    );
    const seen = new Set();
    cards.forEach((a) => {
      const href = a.getAttribute("href") || "";
      const m = href.match(/\/video\/(\d+)/);
      if (!m || seen.has(m[1])) return;
      seen.add(m[1]);
      const id = m[1];

      // 向上找卡片容器, 在其中提取标题与统计
      let card = a;
      for (let i = 0; i < 5 && card.parentElement; i++) card = card.parentElement;

      const title =
        a.getAttribute("title") ||
        card.querySelector("p, [class*=title], [class*=desc]")?.textContent?.trim() ||
        "(无标题)";

      // 统计: 抖音 DOM 中数字文本, 尝试匹配 点赞/评论/分享
      const nums = Array.from(card.querySelectorAll("span"))
        .map((s) => s.textContent?.trim())
        .filter((t) => /^[\d.]+[万wW亿]?$/.test(t || ""));

      const toNum = (s) => {
        if (!s) return 0;
        s = s.replace(/[wW万]/, "0000").replace(/亿/, "00000000");
        return parseInt(s, 10) || 0;
      };

      videos.push({
        video_id: id,
        title,
        likes: toNum(nums[0]),
        comments: toNum(nums[1]),
        shares: toNum(nums[2]),
        publish_time: null, // DOM 通常无精确发布时间
        video_url: href.startsWith("http") ? href : `https://www.douyin.com${href}`,
        cover_url: card.querySelector("img")?.src || null,
      });
    });
    return videos;
  });
}
