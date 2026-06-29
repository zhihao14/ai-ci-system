// ============================================================
// crawl_xiaohongshu.js - 小红书用户笔记爬虫
//
// 调用: node crawl_xiaohongshu.js <用户主页URL> [--max=30] [--headed]
// 示例: node crawl_xiaohongshu.js "https://www.xiaohongshu.com/user/profile/xxx" --headed
//
// 原理:
//   1. Playwright 渲染页面, 浏览器自身 JS 处理小红书的 X-s/X-t 签名
//   2. 拦截 /api/sns/web/v1/user_posted 响应, 提取 notes 列表
//   3. DOM 兜底: 解析 .note-item 等元素
//   4. 统一输出 JSON (schema 与抖音/TikTok/YouTube 一致)
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
  emitError("xiaohongshu", null, "缺少参数: node crawl_xiaohongshu.js <URL> [--max=N] [--headed]");
  process.exit(0);
}

(async () => {
  const { context, page } = await createBrowser({
    headed,
    dataDir: "xiaohongshu",
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
  });

  // 收集器: note_id -> 标准化 item
  const collected = new Map();
  let accountName = "";
  let accountId = "";
  let followerCount = 0;

  // ---- 拦截小红书笔记列表 API ----
  page.on("response", async (resp) => {
    const u = resp.url();
    if (u.includes("/api/sns/web/v1/user_posted") || u.includes("/api/sns/web/v1/feed")) {
      try {
        const json = await resp.json();
        const notes = json?.data?.notes || [];
        for (const note of notes) {
          const item = normalizeXhsNote(note);
          if (item) collected.set(item.video_id, item);
        }
        // 从 API 响应中取用户信息
        if (notes[0]?.user?.nickname) accountName = notes[0].user.nickname;
      } catch {
        /* 非 JSON 响应, 忽略 */
      }
    }
    // 拦截用户信息 API
    if (u.includes("/api/sns/web/v1/user/otherinfo") || u.includes("/api/sns/web/v1/user/me")) {
      try {
        const json = await resp.json();
        const userInfo = json?.data?.basic_info || json?.data?.infos || json?.data || {};
        if (userInfo.nickname) accountName = userInfo.nickname;
        if (userInfo.red_id) accountId = userInfo.red_id;
        followerCount = Number(userInfo.fans) || Number(userInfo.follower_count) || 0;
      } catch {}
    }
  });

  // ---- 导航到用户主页 ----
  try {
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
  } catch (err) {
    await context.close();
    emitError("xiaohongshu", url, `页面加载失败: ${err.message}`);
    return;
  }

  // ---- 检测登录 ----
  const needsLogin = await page
    .locator('text=扫码登录, .login-container, [class*="qrcode"]')
    .count()
    .catch(() => 0);

  if (needsLogin > 0) {
    if (!headed) {
      await context.close();
      emitError("xiaohongshu", url, "需要登录: 请用 --headed 扫码登录, 登录态会被持久化");
      return;
    }
    console.error("[提示] 请扫码登录小红书...");
    await page
      .waitForSelector('.user-note-item, .note-item, [class*="note-item"]', { timeout: 120000 })
      .catch(() => {});
  }

  // ---- 等待笔记列表渲染 ----
  await page
    .waitForSelector('.user-note-item, .note-item, [class*="note-item"], section.note-item', { timeout: 15000 })
    .catch(() => {});

  // ---- 从 DOM 取账号名 (兜底) ----
  if (!accountName) {
    accountName =
      (await page.locator('.user-name, .user-nickname, [class*="user-name"]').first().textContent().catch(() => "")) || "";
  }
  // 从 URL 提取 account_id
  const idMatch = url.match(/\/profile\/([^/?#]+)/);
  if (idMatch) accountId = accountId || idMatch[1];

  // ---- 自动滚动收集 ----
  await scrollAndCollect(page, {
    getCount: async () => collected.size,
    maxItems: max,
    maxRounds: 30,
    waitMs: 1800,
  });

  // ---- DOM 兜底: 若 API 未命中 ----
  if (collected.size === 0) {
    const domNotes = await extractFromDom(page);
    for (const n of domNotes) collected.set(n.video_id, n);
  }

  await context.close();

  emitSuccess("xiaohongshu", {
    account_url: url,
    account_name: accountName.trim(),
    account_id: accountId,
    follower_count: followerCount,
    videos: Array.from(collected.values()).slice(0, max),
  });
})().catch((err) => {
  emitError("xiaohongshu", url, err);
});

// ============================================================
// 标准化: 小红书 API note 对象 → 统一 VideoItem
// ============================================================
function normalizeXhsNote(note) {
  if (!note || !note.note_id) return null;

  const interact = note.interact_info || {};
  // 小红书的互动数据可能是字符串 "1.2万", 需要转换
  const parseCount = (v) => {
    if (v == null) return 0;
    const s = String(v);
    if (s.includes("万")) return Math.floor(parseFloat(s) * 10000);
    if (s.includes("亿")) return Math.floor(parseFloat(s) * 100000000);
    return parseInt(s, 10) || 0;
  };

  // 视频地址 (仅 video 类型有)
  let videoUrl = null;
  if (note.type === "video" && note.video?.media?.stream?.h264?.[0]?.master_url) {
    videoUrl = note.video.media.stream.h264[0].master_url;
  }

  // 封面
  const coverUrl = note.cover?.url || note.cover?.url_default || null;

  // 时间: 小红书 time 字段为毫秒时间戳
  const publishTime = note.time ? ts2str(note.time, "ms") : null;

  return {
    video_id: note.note_id,
    title: (note.display_title || note.title || "").trim() || "(无标题)",
    description: note.desc || null,
    likes: parseCount(interact.liked_count),
    comments: parseCount(interact.comment_count),
    shares: parseCount(interact.share_count),
    views: 0, // 小红书无播放数
    publish_time: publishTime,
    video_url: videoUrl,
    cover_url: coverUrl,
    type: note.type === "video" ? "video" : "image",
  };
}

// ============================================================
// DOM 兜底解析
// ============================================================
async function extractFromDom(page) {
  return await page.evaluate(() => {
    const items = [];
    // 小红书笔记卡: .note-item 或 .user-note-item
    const cards = document.querySelectorAll(
      '.note-item, .user-note-item, section[class*="note-item"], a[href*="/explore/"]'
    );
    const seen = new Set();

    cards.forEach((card) => {
      // 提取 note_id: 从链接 href 或 data 属性
      const href = card.getAttribute("href") || card.querySelector("a")?.getAttribute("href") || "";
      const m = href.match(/\/(?:explore|discovery\/item)\/([a-f0-9]+)/);
      const noteId = m ? m[1] : card.getAttribute("data-note-id") || "";
      if (!noteId || seen.has(noteId)) return;
      seen.add(noteId);

      const title =
        card.querySelector("[class*=title], [class*=desc], .note-title")?.textContent?.trim() ||
        card.getAttribute("title") ||
        "(无标题)";

      // 封面
      const cover = card.querySelector("img")?.src || null;

      // 互动数据 (DOM 中可能没有, 填 0)
      const nums = Array.from(card.querySelectorAll("span, [class*=count]"))
        .map((s) => s.textContent?.trim())
        .filter((t) => /^[\d.]+[万wW亿]?$/.test(t || ""));

      const toNum = (s) => {
        if (!s) return 0;
        s = s.replace(/[wW万]/, "0000").replace(/亿/, "00000000");
        return parseInt(s, 10) || 0;
      };

      // 判断是否视频
      const isVideo = !!card.querySelector("[class*=video], [class*=play], .play-icon");

      items.push({
        video_id: noteId,
        title,
        description: null,
        likes: toNum(nums[0]),
        comments: toNum(nums[1]),
        shares: toNum(nums[2]),
        views: 0,
        publish_time: null,
        video_url: null,
        cover_url: cover,
        type: isVideo ? "video" : "image",
      });
    });
    return items;
  });
}
