// ============================================================
// crawl.js - Playwright 通用网页爬虫
// 调用方式: node crawl.js <url>
// 输出: 标准输出一行 JSON  { url, title, content }
// 设计为被 FastAPI 以子进程方式调用, 通过 stdout 传回结果
//
// 支持: 普通网页 / 抖音分享链接 / 小红书分享链接 等短链重定向场景
// ============================================================
import { chromium } from "playwright";

// 从命令行参数读取目标 URL
const url = process.argv[2];
if (!url) {
  console.log(JSON.stringify({ url: null, title: "", content: "", error: "缺少 URL 参数" }));
  process.exit(0);
}

// 判断是否为短链 / 分享链接 (v.douyin.com, xhslink.com 等)
const isShareLink = /v\.douyin\.com|xhslink\.com|v\.kuaishou\.com|b23\.tv/i.test(url);

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    viewport: { width: 1366, height: 800 },
    locale: "zh-CN",
    timezone: "Asia/Shanghai",
  });

  // 反检测: 隐藏 webdriver 标记
  await context.addInitScript(() => {
    Object.defineProperty(navigator, "webdriver", { get: () => undefined });
  });

  const page = await context.newPage();

  try {
    // ---- 1. 导航 ----
    // 分享链接: 用 domcontentloaded (短链会 302 重定向, networkidle 永远等不到)
    // 普通网页: 优先 domcontentloaded, 再额外等 2s 让 SPA 渲染
    await page.goto(url, {
      waitUntil: "domcontentloaded",
      timeout: 30000,
    });

    // 额外等待: 让重定向落地 / SPA 渲染完成
    if (isShareLink) {
      // 分享链接重定向后等页面稳定
      await page.waitForTimeout(3000);
      // 再等待 body 有实质内容
      await page
        .waitForFunction(() => document.body && document.body.innerText.trim().length > 50, {
          timeout: 10000,
        })
        .catch(() => {});
    } else {
      await page.waitForTimeout(2000);
    }

    // ---- 2. 抓取标题 ----
    const title = await page.title();

    // ---- 3. 抓取正文 ----
    const content = await page.evaluate(() => {
      // 优先提取 main/article, 否则取 body
      const main =
        document.querySelector("main") ||
        document.querySelector("article") ||
        document.querySelector('[class*="content"]') ||
        document.querySelector('[class*="detail"]') ||
        document.body;
      const el = main || document.body;

      // 清理脚本/样式/隐藏元素
      const clone = el.cloneNode(true);
      clone
        .querySelectorAll("script, style, noscript, svg, iframe, [class*='comment']")
        .forEach((n) => n.remove());

      const text = clone.innerText || clone.textContent || "";
      // 折叠多余空白并截断
      return text.replace(/\s+\n/g, "\n").replace(/[ \t]{2,}/g, " ").trim().slice(0, 8000);
    });

    console.log(JSON.stringify({ url, title, content, error: null }));
  } catch (err) {
    console.log(JSON.stringify({ url, title: "", content: "", error: String(err) }));
  } finally {
    await browser.close();
  }
})();
