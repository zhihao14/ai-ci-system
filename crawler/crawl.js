// crawl.js - 短视频数据爬虫
// 策略: Playwright Network Intercept 捕获抖音 API 真实响应
//
// 用法: node crawl.js <url>
// 输出: JSON to stdout

const url = process.argv[2];
const UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

// ============================================================
// 抖音视频列表爬虫 (Playwright Network Intercept)
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
 * 使用 Playwright 拦截抖音视频列表 API
 * 策略:
 * 1. 打开抖音用户主页
 * 2. 设置 network intercept 捕获 /aweme/v1/web/aweme/post/ 响应
 * 3. 自动滚动触发分页加载
 * 4. 收集足够视频后返回
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
    // 隐藏 webdriver 标志
    Object.defineProperty(navigator, "webdriver", { get: () => false });
    // 模拟真实插件
    Object.defineProperty(navigator, "plugins", {
      get: () => [1, 2, 3, 4, 5],
    });
    // 模拟真实语言
    Object.defineProperty(navigator, "languages", {
      get: () => ["zh-CN", "zh", "en"],
    });
    // 伪装 chrome 对象
    window.chrome = { runtime: {} };
  });

  const page = await context.newPage();

  // 3a. 先访问抖音首页获取 cookie (ttwid, msToken 等)
  console.error(`[crawler] 预访问抖音首页获取 cookie...`);
  try {
    await page.goto("https://www.douyin.com/", {
      waitUntil: "networkidle",
      timeout: 20000,
    });
    await page.waitForTimeout(5000);
    console.error(`[crawler] 首页加载完成, cookie 已获取`);
  } catch (e) {
    console.error(`[crawler] 预访问首页失败, 继续: ${e.message}`);
  }

  // 3b. 监听所有网络请求 (调试用, 找到真实的 API)
  const apiUrls = new Set();
  page.on("request", (request) => {
    const u = request.url();
    if (u.includes("aweme") && u.includes("post")) {
      apiUrls.add(u.substring(0, 120));
      console.error(`[crawler] [REQ] ${u.substring(0, 150)}`);
    }
  });

  // 3c. 设置 Network Intercept 捕获视频列表 API
  const allVideos = [];
  const videoApiResponse = { has_more: true, max_cursor: 0 };
  let apiCallCount = 0;

  page.on("response", async (response) => {
    const reqUrl = response.url();
    // 匹配视频列表 API
    if (reqUrl.includes("/aweme/v1/web/aweme/post/") || reqUrl.includes("/aweme/v1/aweme/post/")) {
      try {
        // 尝试多种方式获取响应体
        let text = "";
        try {
          text = await response.text();
        } catch {
          // response.text() 失败, 尝试 body()
          try {
            const buf = await response.body();
            text = buf.toString("utf-8");
          } catch {
            console.error(`[crawler] API 响应体无法读取 (status=${response.status()})`);
            return;
          }
        }

        if (!text || text.length < 10) {
          console.error(`[crawler] API 响应为空 (status=${response.status()}, length=${text.length})`);
          // 尝试从页面 JS context 直接 fetch
          return;
        }
        const body = JSON.parse(text);
        apiCallCount++;
        console.error(`[crawler] 捕获 API 响应 #${apiCallCount}, aweme_list: ${body.aweme_list?.length || 0} 条`);

        const extracted = extractVideosFromResponse(body);
        // 去重 (按 aweme_id)
        for (const v of extracted) {
          if (!allVideos.find((x) => x.aweme_id === v.aweme_id)) {
            allVideos.push(v);
          }
        }

        // 更新分页状态
        videoApiResponse.has_more = body.has_more === true || body.has_more === 1;
        videoApiResponse.max_cursor = body.max_cursor || 0;
      } catch (e) {
        console.error(`[crawler] 解析 API 响应失败: ${e.message} (status=${response.status()})`);
      }
    }
  });

  // 4. 导航到用户主页
  const profileUrl = `https://www.douyin.com/user/${secUid}`;
  console.error(`[crawler] 导航到: ${profileUrl.substring(0, 60)}...`);

  try {
    await page.goto(profileUrl, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });
  } catch (e) {
    console.error(`[crawler] 导航超时, 继续尝试拦截: ${e.message}`);
  }

  // 等待页面初始加载 (抖音 SPA 需要时间渲染)
  await page.waitForTimeout(5000);

  // 检测是否出现验证码
  const pageText = await page.evaluate(() => document.body?.innerText?.substring(0, 500) || "");
  if (pageText.includes("验证") || pageText.includes("安全验证") || pageText.includes("captcha")) {
    console.error(`[crawler] 检测到验证码页面, 尝试等待通过...`);
    await page.waitForTimeout(10000);
  }

  // 检测登录弹窗并关闭
  try {
    const closeBtn = await page.$('[class*="close"][class*="icon"], [class*="dy-account-close"], button:has-text("关闭")');
    if (closeBtn) {
      await closeBtn.click({ timeout: 2000 });
      console.error(`[crawler] 关闭登录弹窗`);
      await page.waitForTimeout(1000);
    }
  } catch {}

  // 5. 尝试点击"作品" tab (确保在作品页面)
  try {
    const tabSelectors = [
      'div[data-key="user_post_list"]',
      'span:has-text("作品")',
      'div.tab:has-text("作品")',
      '[class*="tab"][class*="active"]',
      'a:has-text("作品")',
    ];
    for (const sel of tabSelectors) {
      try {
        const el = await page.$(sel);
        if (el) {
          await el.click({ timeout: 3000 });
          console.error(`[crawler] 点击作品 tab: ${sel}`);
          await page.waitForTimeout(3000);
          break;
        }
      } catch {}
    }
  } catch {}

  // 6. 自动滚动加载更多视频
  const TARGET_VIDEO_COUNT = 20;
  const MAX_SCROLL_ATTEMPTS = 20;
  let scrollAttempts = 0;
  let lastVideoCount = 0;
  let noChangeCount = 0;

  console.error(`[crawler] 开始滚动加载, 目标: ${TARGET_VIDEO_COUNT} 条视频`);

  while (allVideos.length < TARGET_VIDEO_COUNT && scrollAttempts < MAX_SCROLL_ATTEMPTS) {
    scrollAttempts++;
    lastVideoCount = allVideos.length;

    // 模拟人类滚动: 先慢滚再快滚
    await page.evaluate(async () => {
      await new Promise((resolve) => {
        let total = 0;
        const step = 300 + Math.random() * 200;
        const timer = setInterval(() => {
          window.scrollBy(0, step);
          total += step;
          if (total >= 800 + Math.random() * 400) {
            clearInterval(timer);
            resolve();
          }
        }, 100);
      });
    });

    // 等待 API 响应
    await page.waitForTimeout(2500 + Math.random() * 1500);

    console.error(
      `[crawler] 滚动 #${scrollAttempts}: 已获取 ${allVideos.length}/${TARGET_VIDEO_COUNT} 条视频`
    );

    // 检测是否还有新数据
    if (allVideos.length === lastVideoCount) {
      noChangeCount++;
      if (noChangeCount >= 5) {
        console.error(`[crawler] 连续 ${noChangeCount} 次无新数据, 停止滚动`);
        break;
      }
    } else {
      noChangeCount = 0;
    }

    // 检测是否还有更多
    if (!videoApiResponse.has_more) {
      console.error(`[crawler] API 返回 has_more=false, 停止滚动`);
      break;
    }
  }

  await browser.close();

  // 7. 截取目标数量
  let videos = allVideos.slice(0, TARGET_VIDEO_COUNT);

  // 7a. 如果 Network Intercept 未获取到视频, 尝试在页面 context 内 fetch
  if (videos.length === 0) {
    console.error(`[crawler] Network Intercept 未获取到视频, 尝试页面内直接 fetch API...`);
    // 重新打开页面 (browser 已关闭)
    const browser2 = await chromium.launch({
      headless: true,
      args: [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
      ],
    });
    const context2 = await browser2.newContext({
      userAgent: UA,
      viewport: { width: 1920, height: 1080 },
      locale: "zh-CN",
      timezoneId: "Asia/Shanghai",
    });
    await context2.addInitScript(() => {
      Object.defineProperty(navigator, "webdriver", { get: () => false });
      window.chrome = { runtime: {} };
    });
    const page2 = await context2.newPage();

    // 访问首页获取 cookie
    try {
      await page2.goto("https://www.douyin.com/", { waitUntil: "domcontentloaded", timeout: 20000 });
      await page2.waitForTimeout(8000);
    } catch (e) {
      console.error(`[crawler] 预访问首页失败: ${e.message}`);
    }

    // 导航到用户主页触发 JS 加载
    const profileUrl2 = `https://www.douyin.com/user/${secUid}`;
    try {
      await page2.goto(profileUrl2, { waitUntil: "domcontentloaded", timeout: 30000 });
      await page2.waitForTimeout(8000);
    } catch (e) {
      console.error(`[crawler] 用户主页导航超时: ${e.message}`);
    }

    // 在页面 context 内 fetch (带 cookie + 签名)
    try {
      console.error(`[crawler] 在页面 context 内直接调用 API...`);
      const apiResult = await page2.evaluate(async (secUidVal) => {
        const params = new URLSearchParams({
          device_platform: "webapp",
          aid: "6383",
          channel: "channel_pc_web",
          sec_user_id: secUidVal,
          max_cursor: "0",
          count: "20",
          version_code: "170400",
          version_name: "17.4.0",
        });
        const apiUrl = `https://www.douyin.com/aweme/v1/web/aweme/post/?${params.toString()}`;
        const resp = await fetch(apiUrl, {
          method: "GET",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
        });
        const text = await resp.text();
        return { status: resp.status, text, length: text.length };
      }, secUid);

      console.error(`[crawler] 页面内 fetch 结果: status=${apiResult.status}, length=${apiResult.length}`);

      if (apiResult.text && apiResult.text.length > 10) {
        try {
          const body = JSON.parse(apiResult.text);
          const extracted = extractVideosFromResponse(body);
          for (const v of extracted) {
            if (!videos.find((x) => x.aweme_id === v.aweme_id)) {
              videos.push(v);
            }
          }
          console.error(`[crawler] 页面内 fetch 获取 ${extracted.length} 条视频`);
        } catch (e) {
          console.error(`[crawler] 页面内 fetch 结果解析失败: ${e.message}`);
        }
      }
    } catch (e) {
      console.error(`[crawler] 页面内 fetch 失败: ${e.message}`);
    }

    await browser2.close();
  }

  console.error(`[crawler] 最终获取 ${videos.length} 条视频 (共 ${apiCallCount} 次 API 调用)`);

  // 8. 构造账号信息文本
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
