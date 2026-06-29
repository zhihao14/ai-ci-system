// ============================================================
// crawl.js - Playwright 竞争对手网站爬虫
// 调用方式: node crawl.js <url>
// 输出: 标准输出一行 JSON  { url, title, content }
// 设计为被 FastAPI 以子进程方式调用, 通过 stdout 传回结果
// ============================================================
import { chromium } from "playwright";

// 从命令行参数读取目标 URL
const url = process.argv[2];
if (!url) {
  // 错误也走 stdout(JSON), 便于后端解析
  console.log(JSON.stringify({ url: null, title: "", content: "", error: "缺少 URL 参数" }));
  process.exit(0);
}

(async () => {
  // 启动浏览器 (无头模式)
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    // 模拟真实桌面浏览器, 降低被反爬拦截概率
    userAgent:
      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    viewport: { width: 1366, height: 800 },
    locale: "zh-CN",
  });
  const page = await context.newPage();

  try {
    // 导航到目标页, 等待网络空闲, 最多等 30s
    await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });

    // 抓取页面标题
    const title = await page.title();

    // 抓取正文: 优先提取 main/article, 否则取 body 文本
    const content = await page.evaluate(() => {
      const main = document.querySelector("main") || document.querySelector("article");
      const el = main || document.body;
      // 清理脚本/样式/隐藏元素后再取文本
      const clone = el.cloneNode(true);
      clone.querySelectorAll("script, style, noscript, svg, iframe").forEach((n) => n.remove());
      const text = clone.innerText || clone.textContent || "";
      // 折叠多余空白并截断(避免超长文本喂给 LLM)
      return text.replace(/\s+\n/g, "\n").replace(/[ \t]{2,}/g, " ").trim().slice(0, 8000);
    });

    console.log(JSON.stringify({ url, title, content, error: null }));
  } catch (err) {
    // 任何异常都返回结构化错误, 不抛出进程错误
    console.log(JSON.stringify({ url, title: "", content: "", error: String(err) }));
  } finally {
    await browser.close();
  }
})();
