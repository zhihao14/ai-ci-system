// crawl.js - 短视频数据爬虫
// 策略: Playwright 页面内 fetch 捕获抖音 API 真实响应
//
// 用法: node crawl.js <url>
// 输出: JSON to stdout

const url = process.argv[2];
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

// ============================================================
// 抖音视频列表爬虫
// ============================================================

/**
 * 从分享链接获取 sec_uid
 */
async function getSecUid(shareUrl) {
  const resp = await fetch(shareUrl, {
    redirect: "follow",
    headers: { "User-Agent": UA },
    signal: AbortSignal.timeout(15000),
  });
  const finalUrl = resp.url;
  const match = finalUrl.match(/sec_uid=([^&]+)/);
  if (!match) {
    throw new Error("无法从重定向 URL 提取 sec_uid");
  }
  return decodeURIComponent(match[1]);
}

/**
 * 获取账号基础信息 (公共 API, 无需登录)
 */
async function getAccountInfo(secUid) {
  const apiResp = await fetch(
    `https://www.iesdouyin.com/web/api/v2/user/info/?sec_uid=${secUid}`,
    { headers: { "User-Agent": UA }, signal: AbortSignal.timeout(15000) }
  );
  const data = await apiResp.json();
  if (data.status_code !== 0 || !data.user_info) {
    throw new Error(`账号信息 API 返回异常: status=${data.status_code}`);
  }
  const u = data.user_info;
  return {
    nickname: u.nickname || null,
    unique_id: u.unique_id || u.short_id || null,
    signature: u.signature || null,
    verify_reason: u.enterprise_verify_reason || u.custom_verify || null,
    follower_count: u.mplatform_followers_count ?? null,
    total_favorited: u.total_favorited ? Number(u.total_favorited) : null,
    aweme_count: u.aweme_count ?? null,
    following_count: u.following_count ?? null,
    sec_uid: secUid,
  };
}

/**
 * 从 API 响应中提取标准化的视频数据
 */
function extractVideosFromResponse(jsonData) {
  const videos = [];
  if (!jsonData || !jsonData.aweme_list) return videos;

  for (const item of jsonData.aweme_list) {
    const stats = item.statistics || {};
    const video = item.video || {};
    const playAddr = video.play_addr || {};
    const author = item.author || {};

    videos.push({
      aweme_id: item.aweme_id || null,
      title: item.desc || "",
      desc: item.desc || "",
      digg_count: stats.digg_count ?? null,
      comment_count: stats.comment_count ?? null,
      share_count: stats.share_count ?? null,
      play_count: stats.play_count ?? null,
      collect_count: stats.collect_count ?? null,
      create_time: item.create_time || null,
      create_time_str: item.create_time
        ? new Date(item.create_time * 1000).toISOString()
        : null,
      video_url: playAddr.url_list && playAddr.url_list.length > 0
        ? playAddr.url_list[0]
        : null,
      cover_url: video.cover && video.cover.url_list && video.cover.url_list.length > 0
        ? video.cover.url_list[0]
        : null,
      duration: video.duration ?? null,
      author_nickname: author.nickname || null,
    });
  }
  return videos;
}

/**
 * 使用 Playwright 在页面 context 内 fetch API
 * 策略:
 * 1. 访问抖音首页获取 cookie (ttwid, msToken)
 * 2. 导航到用户主页触发 JS 加载
 * 3. 在页面 context 内 fetch 视频列表 API (带 cookie + 签名)
 * 4. 如果有更多, 继续翻页
 */
async function crawlDouyinVideos(shareUrl) {
  const { chromium } = await import("playwright");

  // 1. 获取 sec_uid 和账号信息
  const secUid = await getSecUid(shareUrl);
  const accountFields = await getAccountInfo(secUid);
  console.error(`[crawler] 账号: ${accountFields.nickname}, sec_uid: ${secUid.substring(0, 20)}...`);

  // 2. 启动浏览器 (带反检测配置)
  const browser = await chromium.launch({
    headless: true,
    args: [
      "--disable-blink-features=AutomationControlled",
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
    ],
  });

  const context = await browser.newContext({
    userAgent: UA,
    viewport: { width: 1920, height: 1080 },
    locale: "zh-CN",
    timezoneId: "Asia/Shanghai",
    extraHTTPHeaders: {
      "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    },
  });

  // 注入反检测脚本
  await context.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => false });
    Object.defineProperty(navigator, "plugins", { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, "languages", { get: () => ["zh-CN", "zh", "en"] });
    window.chrome = { runtime: {} };
  });

  const page = await context.newPage();

  // 3. 直接导航到用户主页 (获取 cookie + 触发 JS)
  const profileUrl = `https://www.douyin.com/user/${secUid}`;
  console.error(`[crawler] 导航到用户主页...`);
  try {
    await page.goto(profileUrl, {
      waitUntil: "domcontentloaded",
      timeout: 20000,
    });
    await page.waitForTimeout(3000);
  } catch (e) {
    console.error(`[crawler] 用户主页导航超时, 继续尝试: ${e.message}`);
  }

  // 5. 在页面 context 内 fetch 视频列表 API
  const allVideos = [];
  const TARGET_VIDEO_COUNT = 50;
  let maxCursor = 0;
  let hasMore = true;
  let pageCount = 0;

  console.error(`[crawler] 开始页面内 fetch API, 目标: ${TARGET_VIDEO_COUNT} 条`);

  while (allVideos.length < TARGET_VIDEO_COUNT && hasMore && pageCount < 3) {
    pageCount++;
    try {
      const apiResult = await page.evaluate(async (params) => {
        const searchParams = new URLSearchParams({
          device_platform: "webapp",
          aid: "6383",
          channel: "channel_pc_web",
          sec_user_id: params.secUid,
          max_cursor: String(params.cursor),
          count: "20",
          version_code: "170400",
          version_name: "17.4.0",
        });
        const apiUrl = `https://www.douyin.com/aweme/v1/web/aweme/post/?${searchParams.toString()}`;
        const resp = await fetch(apiUrl, {
          method: "GET",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
        });
        const text = await resp.text();
        return { status: resp.status, text, length: text.length };
      }, { secUid, cursor: maxCursor });

      console.error(`[crawler] fetch #${pageCount}: status=${apiResult.status}, length=${apiResult.length}`);

      if (apiResult.text && apiResult.text.length > 10) {
        const body = JSON.parse(apiResult.text);
        const extracted = extractVideosFromResponse(body);
        // 去重
        for (const v of extracted) {
          if (!allVideos.find((x) => x.aweme_id === v.aweme_id)) {
            allVideos.push(v);
          }
        }
        hasMore = body.has_more === true || body.has_more === 1;
        maxCursor = body.max_cursor || 0;
        console.error(`[crawler] 获取 ${extracted.length} 条, 累计 ${allVideos.length}/${TARGET_VIDEO_COUNT}, has_more=${hasMore}`);
      } else {
        console.error(`[crawler] API 响应为空, 停止`);
        break;
      }
    } catch (e) {
      console.error(`[crawler] fetch 失败: ${e.message}`);
      break;
    }
  }

  await browser.close();

  // 6. 截取目标数量
  const videos = allVideos.slice(0, TARGET_VIDEO_COUNT);
  console.error(`[crawler] 最终获取 ${videos.length} 条视频`);

  // 7. 构造账号信息文本
  const content = [
    `账号名称: ${accountFields.nickname}`,
    `抖音号: ${accountFields.unique_id || "未知"}`,
    `简介: ${accountFields.signature || "无"}`,
    `认证信息: ${accountFields.verify_reason || "未认证"}`,
    `粉丝数: ${accountFields.follower_count || "未知"}`,
    `获赞总数: ${accountFields.total_favorited || "未知"}`,
    `作品数: ${accountFields.aweme_count || "未知"}`,
    `关注数: ${accountFields.following_count || "未知"}`,
    `sec_uid: ${secUid}`,
    `获取视频数: ${videos.length}`,
  ].join("\n");

  const title = `${accountFields.nickname} - 抖音`;

  return {
    url: shareUrl,
    title,
    content,
    account_fields: accountFields,
    videos,
    video_count: videos.length,
    error: null,
  };
}

/**
 * 通用网页爬虫 (Playwright)
 */
async function crawlGeneric(targetUrl) {
  const isShareLink = /v\.douyin\.com|xhslink\.com|v\.kuaishou\.com|b23\.tv/i.test(targetUrl);
  const { chromium } = await import("playwright");
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  const context = await browser.newContext({ userAgent: UA });
  const page = await context.newPage();

  try {
    await page.goto(targetUrl, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });

    if (isShareLink) {
      await page.waitForTimeout(5000);
    } else {
      await page.waitForTimeout(3000);
    }

    const result = await page.evaluate(() => {
      const title = document.title || "";
      const bodyText = document.body ? document.body.innerText : "";
      return {
        title,
        content: bodyText.substring(0, 10000),
      };
    });

    return { url: targetUrl, ...result, error: null };
  } catch (err) {
    return { url: targetUrl, title: "", content: "", error: String(err) };
  } finally {
    await browser.close();
  }
}

// ============================================================
// 主入口
// ============================================================
(async () => {
  try {
    if (/v\.douyin\.com|douyin\.com\/user\//i.test(url)) {
      const result = await crawlDouyinVideos(url);
      console.log(JSON.stringify(result));
      return;
    }
    const result = await crawlGeneric(url);
    console.log(JSON.stringify(result));
  } catch (err) {
    console.log(JSON.stringify({ url, title: "", content: "", error: String(err) }));
  }
})();
