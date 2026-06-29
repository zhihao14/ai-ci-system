// ============================================================
// crawl_youtube.js - YouTube 频道视频爬虫
//
// 调用: node crawl_youtube.js <频道URL> [--max=30] [--headed]
// 示例: node crawl_youtube.js "https://www.youtube.com/@Google/videos"
//
// 原理:
//   1. YouTube 页面内嵌 ytInitialData (JSON), 包含初始视频列表
//   2. 滚动时拦截 /youtubei/v1/browse 续传 API 获取更多视频
//   3. DOM 兜底: 解析 #contents 下的视频项
//   4. YouTube 公开频道无需登录
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
  emitError("youtube", null, "缺少参数: node crawl_youtube.js <URL> [--max=N]");
  process.exit(0);
}

// 确保 URL 指向 /videos 页面
let targetUrl = url;
if (!url.includes("/videos")) {
  targetUrl = url.replace(/\/?$/, "/videos");
}

(async () => {
  const { context, page } = await createBrowser({
    headed,
    dataDir: "youtube",
    locale: "en-US", // YouTube 用英文界面, 解析更稳定
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  });

  // 收集器
  const collected = new Map();
  let accountName = "";
  let accountId = "";
  let followerCount = 0;

  // ---- 拦截 YouTube 续传 API ----
  page.on("response", async (resp) => {
    const u = resp.url();
    if (u.includes("/youtubei/v1/browse")) {
      try {
        const json = await resp.json();
        // 续传响应中的视频在 onResponseReceivedActions -> appendContinuationItemsAction -> continuationItems
        const actions = json?.onResponseReceivedActions || [];
        for (const action of actions) {
          const items =
            action?.appendContinuationItemsAction?.continuationItems ||
            action?.reloadContinuationItemsCommand?.continuationItems ||
            [];
          for (const item of items) {
            const video = item?.richItemRenderer?.content?.videoRenderer;
            if (video) {
              const v = normalizeYtVideo(video);
              if (v) collected.set(v.video_id, v);
            }
          }
        }
      } catch {}
    }
  });

  // ---- 导航 ----
  try {
    await page.goto(targetUrl, { waitUntil: "networkidle", timeout: 45000 });
  } catch (err) {
    await context.close();
    emitError("youtube", targetUrl, `页面加载失败: ${err.message}`);
    return;
  }

  // ---- 从 ytInitialData 提取初始视频列表 ----
  const initData = await page.evaluate(() => {
    if (typeof window.ytInitialData === "undefined") return null;
    return window.ytInitialData;
  });

  if (initData) {
    // 频道名
    try {
      const header =
        initData?.header?.c4TabbedHeaderRenderer ||
        initData?.header?.pageHeaderRenderer;
      if (header?.title) accountName = header.title;
      if (header?.channelId) accountId = header.channelId;
      // subscriberCountText: "1.2M subscribers"
      const subText =
        header?.subscriberCountText?.simpleText ||
        initData?.header?.pageHeaderRenderer?.content?.pageHeaderViewModel?.metadata?.contentMetadataViewModel?.metadataRows?.[1]?.metadataParts?.[0]?.text;
      if (subText) {
        followerCount = parseSubCount(subText);
      }
    } catch {}

    // 提取视频列表
    try {
      const tabs =
        initData?.contents?.twoColumnBrowseResultsRenderer?.tabs || [];
      for (const tab of tabs) {
        const tabRenderer = tab?.tabRenderer;
        if (tabRenderer?.selected) {
          const contents =
            tabRenderer?.content?.richGridRenderer?.contents || [];
          for (const item of contents) {
            const video = item?.richItemRenderer?.content?.videoRenderer;
            if (video) {
              const v = normalizeYtVideo(video);
              if (v) collected.set(v.video_id, v);
            }
          }
        }
      }
    } catch {}
  }

  // 从 URL 提取 channel ID (兜底)
  if (!accountId) {
    const m = targetUrl.match(/@([\w-]+)/);
    if (m) accountId = m[1];
  }

  // ---- 自动滚动加载更多 ----
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

  emitSuccess("youtube", {
    account_url: url,
    account_name: accountName.trim(),
    account_id: accountId,
    follower_count: followerCount,
    videos: Array.from(collected.values()).slice(0, max),
  });
})().catch((err) => {
  emitError("youtube", url, err);
});

// ============================================================
// 标准化: YouTube videoRenderer → 统一 VideoItem
// ============================================================
function normalizeYtVideo(vr) {
  if (!vr?.videoId) return null;

  // 标题: runs 数组拼接
  const title = vr.title?.runs?.map((r) => r.text).join("") || vr.title?.simpleText || "";

  // 封面
  const coverUrl = vr.thumbnail?.thumbnails?.slice(-1)[0]?.url || null;

  // 播放数: "1.2M views" → 1200000
  const parseViews = (text) => {
    if (!text) return 0;
    const s = text.replace(/[^\d.]/g, "");
    if (!s) return 0;
    const n = parseFloat(s);
    if (text.includes("B")) return Math.floor(n * 1e9);
    if (text.includes("M")) return Math.floor(n * 1e6);
    if (text.includes("K")) return Math.floor(n * 1000);
    return Math.floor(n) || 0;
  };

  const viewText = vr.viewCountText?.simpleText || "";
  const views = parseViews(viewText);

  // 发布时间: "2 days ago" — 无法精确转换, 保留原始文本
  const publishedText = vr.publishedTimeText?.simpleText || null;

  // YouTube 不直接提供点赞/评论数, 这些在视频详情页才有
  // 这里从标题栏旁的 aria-label 可尝试解析
  const ariaLabel = vr.title?.accessibility?.accessibilityData?.label || "";
  // aria-label 格式: "标题 作者 1.2M views 2 days ago"
  // 尝试从 videoInfo 提取
  const infoText = vr.videoInfo?.runs?.map((r) => r.text).join(" ") || "";

  return {
    video_id: vr.videoId,
    title: title.trim() || "(无标题)",
    description: null,
    likes: 0, // YouTube 列表页不显示点赞数
    comments: 0, // 列表页不显示评论数
    shares: 0,
    views,
    publish_time: publishedText, // 保留 "2 days ago" 原文
    video_url: `https://www.youtube.com/watch?v=${vr.videoId}`,
    cover_url: coverUrl,
    type: "video",
  };
}

// ============================================================
// 解析订阅数: "1.2M subscribers" → 1200000
// ============================================================
function parseSubCount(text) {
  if (!text) return 0;
  const s = text.replace(/[^\d.]/g, "");
  if (!s) return 0;
  const n = parseFloat(s);
  if (text.includes("M")) return Math.floor(n * 1e6);
  if (text.includes("K")) return Math.floor(n * 1000);
  if (text.includes("B")) return Math.floor(n * 1e9);
  return Math.floor(n) || 0;
}

// ============================================================
// DOM 兜底解析
// ============================================================
async function extractFromDom(page) {
  return await page.evaluate(() => {
    const items = [];
    // YouTube 视频卡: ytd-rich-item-renderer 或 ytd-video-renderer
    const cards = document.querySelectorAll(
      "ytd-rich-item-renderer, ytd-video-renderer, ytd-grid-video-renderer"
    );
    const seen = new Set();

    cards.forEach((card) => {
      const link = card.querySelector("a#thumbnail, a#video-title-link, a[href*='watch']");
      const href = link?.getAttribute("href") || "";
      const m = href.match(/watch\?v=([\w-]+)/);
      if (!m || seen.has(m[1])) return;
      seen.add(m[1]);

      const title =
        card.querySelector("#video-title, yt-formatted-string#video-title")?.textContent?.trim() ||
        "(无标题)";

      const cover = card.querySelector("img")?.src || null;
      const metaText = card.querySelector("#metadata-line")?.textContent || "";

      items.push({
        video_id: m[1],
        title,
        description: null,
        likes: 0,
        comments: 0,
        shares: 0,
        views: 0,
        publish_time: null,
        video_url: `https://www.youtube.com/watch?v=${m[1]}`,
        cover_url: cover,
        type: "video",
      });
    });
    return items;
  });
}
