// ============================================================
// crawl_tiktok.js - TikTok 用户视频爬虫
//
// 调用: node crawl_tiktok.js <账号URL> [--max=30] [--headed]
// 示例: node crawl_tiktok.js "https://www.tiktok.com/@username"
//
// 原理:
//   1. 拦截 /api/post/item_list/ 响应, 提取 itemList 中的视频
//   2. TikTok 有 SIGI_STATE / __UNIVERSAL_DATA_FOR_REHYDRATION__ 内嵌数据
//   3. DOM 兜底: 解析 [data-e2e="user-post-item"] 等元素
//   4. TikTok 公开账号通常无需登录, 但反爬较严, 需反检测
// ============================================================
import {
  createBrowser,
  scrollAndCollect,
  parseArgs,
  emitSuccess,
  emitError,
  ts2str,
} from "../shared/base.mjs";

const { url, max, headed } = parseArgs();
if (!url) {
  emitError("tiktok", null, "缺少参数: node crawl_tiktok.js <URL> [--max=N] [--headed]");
  process.exit(0);
}

(async () => {
  const { context, page } = await createBrowser({
    headed,
    dataDir: "tiktok",
    locale: "en-US",
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  });

  // 收集器
  const collected = new Map();
  let accountName = "";
  let accountId = "";
  let followerCount = 0;

  // ---- 拦截 TikTok 视频列表 API ----
  page.on("response", async (resp) => {
    const u = resp.url();
    // TikTok 视频列表 API (有多种路径变体)
    if (
      u.includes("/api/post/item_list/") ||
      u.includes("/api/post/item_list")
    ) {
      try {
        const json = await resp.json();
        const list = json.itemList || json.item_list || [];
        for (const item of list) {
          const v = normalizeTikTokItem(item);
          if (v) collected.set(v.video_id, v);
        }
        // 用户名
        if (list[0]?.author?.nickname) accountName = list[0].author.nickname;
      } catch {}
    }
  });

  // ---- 导航 ----
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
  } catch (err) {
    await context.close();
    emitError("tiktok", url, `页面加载失败: ${err.message}`);
    return;
  }

  // ---- 等待内容渲染 ----
  await page
    .waitForSelector(
      '[data-e2e="user-post-item"], [data-e2e="user-post-list"], div[class*="DivItemContainer"]',
      { timeout: 15000 }
    )
    .catch(() => {});

  // ---- 从内嵌数据提取 (SIGI_STATE / __UNIVERSAL_DATA) ----
  const embedded = await page.evaluate(() => {
    // TikTok 将数据嵌入 script tag
    // 方式 1: SIGI_STATE 全局变量
    if (typeof window.SIGI_STATE !== "undefined") return window.SIGI_STATE;
    // 方式 2: __UNIVERSAL_DATA_FOR_REHYDRATION__
    const script = document.getElementById("__UNIVERSAL_DATA_FOR_REHYDRATION__");
    if (script) {
      try {
        return JSON.parse(script.textContent);
      } catch {}
    }
    return null;
  });

  if (embedded) {
    try {
      // 用户信息
      const userInfo =
        embedded?.__DEFAULT_SCOPE__?.["webapp.user-detail"]?.userInfo?.user ||
        embedded?.UserModule?.users?.[0] ||
        embedded?.ItemModule?.[Object.keys(embedded.ItemModule || {})[0]]?.author ||
        {};
      if (userInfo.nickname) accountName = userInfo.nickname;
      if (userInfo.uniqueId) accountId = userInfo.uniqueId;

      const stats =
        embedded?.__DEFAULT_SCOPE__?.["webapp.user-detail"]?.userInfo?.stats ||
        embedded?.UserModule?.stats?.[Object.keys(embedded.UserModule?.stats || {})[0]] ||
        {};
      followerCount = Number(stats.followerCount) || 0;

      // 视频列表
      const items =
        embedded?.__DEFAULT_SCOPE__?.["webapp.video-list"]?.itemList ||
        embedded?.Items ||
        [];
      if (Array.isArray(items)) {
        for (const item of items) {
          const v = normalizeTikTokItem(item);
          if (v) collected.set(v.video_id, v);
        }
      }
    } catch {}
  }

  // 从 URL 提取 username (兜底)
  if (!accountId) {
    const m = url.match(/@([\w.-]+)/);
    if (m) accountId = m[1];
  }

  // ---- 自动滚动加载 ----
  await scrollAndCollect(page, {
    getCount: async () => collected.size,
    maxItems: max,
    maxRounds: 30,
    waitMs: 2000,
  });

  // ---- DOM 兜底 ----
  if (collected.size === 0) {
    const domVideos = await extractFromDom(page);
    for (const v of domVideos) collected.set(v.video_id, v);
  }

  await context.close();

  emitSuccess("tiktok", {
    account_url: url,
    account_name: accountName.trim(),
    account_id: accountId,
    follower_count: followerCount,
    videos: Array.from(collected.values()).slice(0, max),
  });
})().catch((err) => {
  emitError("tiktok", url, err);
});

// ============================================================
// 标准化: TikTok item → 统一 VideoItem
// ============================================================
function normalizeTikTokItem(item) {
  if (!item || !item.id) return null;

  const stats = item.stats || {};
  const video = item.video || {};

  // 视频地址
  const playUrls = video.playAddr || video.play_addr || [];
  const videoUrl = Array.isArray(playUrls) ? playUrls[0] : playUrls;

  // 封面
  const coverUrls = video.cover || video.originCover || {};
  const coverUrl = Array.isArray(coverUrls)
    ? coverUrls[0]
    : coverUrls?.urlList?.[0] || coverUrls?.UrlList?.[0] || null;

  // createTime: 秒级时间戳
  const publishTime = item.createTime ? ts2str(item.createTime, "s") : null;

  return {
    video_id: String(item.id),
    title: (item.desc || "").trim() || "(无标题)",
    description: null,
    likes: Number(stats.diggCount) || 0,
    comments: Number(stats.commentCount) || 0,
    shares: Number(stats.shareCount) || 0,
    views: Number(stats.playCount) || 0,
    publish_time: publishTime,
    video_url: videoUrl || null,
    cover_url: coverUrl,
    type: "video",
  };
}

// ============================================================
// DOM 兜底解析
// ============================================================
async function extractFromDom(page) {
  return await page.evaluate(() => {
    const items = [];
    // TikTok 视频卡
    const cards = document.querySelectorAll(
      '[data-e2e="user-post-item"], div[class*="DivItemContainer"], a[href*="/video/"]'
    );
    const seen = new Set();

    cards.forEach((card) => {
      let href = card.getAttribute("href") || "";
      if (!href) {
        const link = card.querySelector('a[href*="/video/"]');
        href = link?.getAttribute("href") || "";
      }
      const m = href.match(/\/video\/(\d+)/);
      if (!m || seen.has(m[1])) return;
      seen.add(m[1]);

      let container = card;
      // 如果 card 本身是 <a>, 向上找容器
      if (card.tagName === "A") {
        for (let i = 0; i < 4 && container.parentElement; i++) {
          container = container.parentElement;
        }
      }

      const title =
        card.getAttribute("title") ||
        container.querySelector("a[class*='title'], [class*='Caption'], [data-e2e='video-desc']")?.textContent?.trim() ||
        "(无标题)";

      // 统计数字
      const nums = Array.from(container.querySelectorAll("span"))
        .map((s) => s.textContent?.trim())
        .filter((t) => /^[\d.]+[KkMm]?$/.test(t || ""));

      const toNum = (s) => {
        if (!s) return 0;
        const n = parseFloat(s);
        if (/[Mm]/.test(s)) return Math.floor(n * 1e6);
        if (/[Kk]/.test(s)) return Math.floor(n * 1000);
        return Math.floor(n) || 0;
      };

      const cover = container.querySelector("img")?.src || null;

      items.push({
        video_id: m[1],
        title,
        description: null,
        likes: toNum(nums[0]),
        comments: toNum(nums[1]),
        shares: toNum(nums[2]),
        views: 0,
        publish_time: null,
        video_url: href.startsWith("http") ? href : `https://www.tiktok.com${href}`,
        cover_url: cover,
        type: "video",
      });
    });
    return items;
  });
}
