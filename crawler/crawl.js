// ============================================================
// crawl.js - Playwright 通用网页爬虫
// 调用方式: node crawl.js <url>
// 输出: 标准输出一行 JSON  { url, title, content }
//
// 支持:
//   - 普通网页 (Playwright 渲染)
//   - 抖音分享链接 (v.douyin.com 短链 -> iesdouyin API 直取)
//   - 小红书分享链接 (xhslink.com)
// ============================================================
const url = process.argv[2];
if (!url) {
  console.log(JSON.stringify({ url: null, title: "", content: "", error: "缺少 URL 参数" }));
  process.exit(0);
}

const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36";

// ============================================================
// 抖音分享链接: 不走 Playwright, 直接用 API 获取用户信息
// ============================================================
async function crawlDouyinShare(shareUrl) {
  // 1. fetch 跟随重定向拿到最终 URL (含 sec_uid)
  const resp = await fetch(shareUrl, {
    redirect: "follow",
    headers: { "User-Agent": UA },
    signal: AbortSignal.timeout(15000),
  });
  const finalUrl = resp.url;

  // 2. 从 URL 提取 sec_uid
  const match = finalUrl.match(/sec_uid=([^&]+)/);
  if (!match) {
    return { url: shareUrl, title: "", content: "", error: "无法从重定向 URL 提取 sec_uid" };
  }
  const secUid = decodeURIComponent(match[1]);

  // 3. 调用抖音公开 API 获取用户信息
  const apiResp = await fetch(
    `https://www.iesdouyin.com/web/api/v2/user/info/?sec_uid=${secUid}`,
    { headers: { "User-Agent": UA }, signal: AbortSignal.timeout(15000) }
  );
  const data = await apiResp.json();

  if (data.status_code !== 0 || !data.user_info) {
    return { url: shareUrl, title: "", content: "", error: `API 返回异常: status=${data.status_code}` };
  }

  const u = data.user_info;

  // 4. 结构化字段 (供 AI 引用为 evidence_fields)
  const account_fields = {
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

  // 5. 格式化为结构化文本供 AI 分析
  const content = [
    `账号名称: ${u.nickname}`,
    `抖音号: ${u.unique_id || u.short_id || "未知"}`,
    `简介: ${u.signature || "无"}`,
    `认证信息: ${u.enterprise_verify_reason || u.custom_verify || "未认证"}`,
    `粉丝数: ${u.mplatform_followers_count || "未知"}`,
    `获赞总数: ${u.total_favorited || "未知"}`,
    `作品数: ${u.aweme_count || "未知"}`,
    `关注数: ${u.following_count || "未知"}`,
    `sec_uid: ${secUid}`,
  ].join("\n");

  const title = `${u.nickname} - 抖音`;
  return { url: shareUrl, title, content, account_fields, error: null };
}

// ============================================================
// 通用网页爬取 (Playwright)
// ============================================================
async function crawlGeneric(targetUrl) {
  const isShareLink = /v\.douyin\.com|xhslink\.com|v\.kuaishou\.com|b23\.tv/i.test(targetUrl);

  const { chromium } = await import("playwright");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: UA,
    viewport: { width: 1366, height: 800 },
    locale: "zh-CN",
    timezone: "Asia/Shanghai",
  });

  // 反检测
  await context.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => undefined });
  });

  const page = await context.newPage();

  try {
    await page.goto(targetUrl, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });

    if (isShareLink) {
      await page.waitForTimeout(3000);
      await page
        .waitForFunction(() => document.body && document.body.innerText.trim().length > 50, {
          timeout: 10000,
        })
        .catch(() => {});
    } else {
      await page.waitForTimeout(2000);
    }

    const title = await page.title();

    const content = await page.evaluate(() => {
      const main =
        document.querySelector("main") ||
        document.querySelector("article") ||
        document.querySelector('[class*="content"]') ||
        document.querySelector('[class*="detail"]') ||
        document.body;
      const el = main || document.body;
      const clone = el.cloneNode(true);
      clone
        .querySelectorAll("script, style, noscript, svg, iframe, [class*='comment']")
        .forEach((n) => n.remove());
      const text = clone.innerText || clone.textContent || "";
      return text.replace(/\s+\n/g, "\n").replace(/[ \t]{2,}/g, " ").trim().slice(0, 8000);
    });

    return { url: targetUrl, title, content, error: null };
  } catch (err) {
    return { url: targetUrl, title: "", content: "", error: String(err) };
  } finally {
    await browser.close();
  }
}

// ============================================================
// 主入口: 根据链接类型分发
// ============================================================
(async () => {
  try {
    // 抖音分享链接 -> API 直取
    if (/v\.douyin\.com/i.test(url)) {
      const result = await crawlDouyinShare(url);
      console.log(JSON.stringify(result));
      return;
    }

    // 其他链接 -> Playwright 通用爬取
    const result = await crawlGeneric(url);
    console.log(JSON.stringify(result));
  } catch (err) {
    console.log(JSON.stringify({ url, title: "", content: "", error: String(err) }));
  }
})();
