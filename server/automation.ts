import { chromium, Browser, Page, BrowserContext } from "playwright";
import { findRenewalHandler } from "./scripts/registry";

/**
 * 浏览器指纹伪装配置
 * 包括随机 User-Agent、视口大小、语言等
 */
interface BrowserFingerprintConfig {
  userAgent: string;
  viewport: { width: number; height: number };
  locale: string;
  timezone: string;
  deviceScaleFactor: number;
  isMobile: boolean;
  hasTouch: boolean;
  acceptLanguage: string;
}

/**
 * 生成随机浏览器指纹配置
 */
function generateRandomFingerprint(): BrowserFingerprintConfig {
  const userAgents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
  ];

  const timezones = ["UTC", "America/New_York", "Europe/London", "Asia/Shanghai", "Asia/Tokyo"];
  const locales = ["en-US", "en-GB", "zh-CN", "ja-JP", "de-DE"];

  const viewports = [
    { width: 1920, height: 1080 },
    { width: 1366, height: 768 },
    { width: 1440, height: 900 },
    { width: 1600, height: 900 },
  ];

  return {
    userAgent: userAgents[Math.floor(Math.random() * userAgents.length)],
    viewport: viewports[Math.floor(Math.random() * viewports.length)],
    locale: locales[Math.floor(Math.random() * locales.length)],
    timezone: timezones[Math.floor(Math.random() * timezones.length)],
    deviceScaleFactor: 1,
    isMobile: false,
    hasTouch: false,
    acceptLanguage: "en-US,en;q=0.9",
  };
}

/**
 * 生成随机延迟（毫秒）
 * 模拟真实用户行为
 */
function getRandomDelay(min: number = 500, max: number = 3000): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

/**
 * 创建带有反爬虫对策的浏览器上下文
 */
async function createStealthContext(browser: Browser): Promise<BrowserContext> {
  const fingerprint = generateRandomFingerprint();

  const context = await (browser as any).newContext({
    userAgent: fingerprint.userAgent,
    viewport: fingerprint.viewport,
    locale: fingerprint.locale,
    timezoneId: fingerprint.timezone,
    deviceScaleFactor: fingerprint.deviceScaleFactor,
    isMobile: fingerprint.isMobile,
    hasTouch: fingerprint.hasTouch,
    acceptLanguage: fingerprint.acceptLanguage,
    // 添加额外的反爬虫头部
    extraHTTPHeaders: {
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
      "Accept-Encoding": "gzip, deflate, br",
      "Accept-Language": fingerprint.acceptLanguage,
      "Cache-Control": "max-age=0",
      "Sec-Fetch-Dest": "document",
      "Sec-Fetch-Mode": "navigate",
      "Sec-Fetch-Site": "none",
      "Sec-Fetch-User": "?1",
      "Upgrade-Insecure-Requests": "1",
    },
  });

  // 注入 JavaScript 来隐藏 Playwright 和 WebDriver 标记
  await context.addInitScript(() => {
        // 隐藏 webdriver 属性
        Object.defineProperty(navigator, "webdriver", {
          get: () => false,
        });

        // 隐藏 chrome 属性
        Object.defineProperty(navigator, "chrome", {
          get: () => ({
            runtime: {},
          }),
        });

        // 隐藏 plugins
        Object.defineProperty(navigator, "plugins", {
          get: () => [
            {
              name: "Chrome PDF Plugin",
              description: "Portable Document Format",
              filename: "internal-pdf-viewer",
            },
          ],
        });

        // 隐藏 languages
        Object.defineProperty(navigator, "languages", {
          get: () => ["en-US", "en"],
        });

        // 隐藏 Playwright 标记
        (window as any).__playwright = undefined;
  });

  return context;
}

/**
 * 自动化执行配置
 */
export interface AutomationExecutionConfig {
  url: string;
  username: string;
  password: string;
  script?: string; // 自定义 JavaScript 脚本
  timeout?: number; // 执行超时时间（毫秒）
}

/**
 * 自动化执行结果
 */
export interface AutomationExecutionResult {
  success: boolean;
  message: string;
  duration: number; // 执行耗时（毫秒）
  errorDetails?: string;
  screenshot?: Buffer; // 可选的错误截图
}

/**
 * 执行自动化签到/续期任务
 */
export async function executeAutomationTask(
  config: AutomationExecutionConfig
): Promise<AutomationExecutionResult> {
  const startTime = Date.now();
  let browser: Browser | null = null;
  let context: BrowserContext | null = null;
  let page: Page | null = null;

  try {
    // 检查是否有注册的专用续期脚本
    const handler = findRenewalHandler(config.url);

    if (handler) {
      console.log(`[Automation] 使用专用续期脚本: ${handler.name}`);

      // 启动浏览器
      browser = await chromium.launch({
        headless: true,
        args: [
          "--disable-blink-features=AutomationControlled",
          "--disable-web-resources",
          "--no-first-run",
          "--no-default-browser-check",
          "--disable-popup-blocking",
        ],
      });

      const result = await handler.execute(browser);
      const duration = Date.now() - startTime;

      if (result.success) {
        return {
          success: true,
          message: result.message,
          duration,
        };
      }

      return {
        success: false,
        message: result.message,
        duration,
        errorDetails: result.details || result.message,
      };
    }

    // 没有专用脚本，走通用登录流程
    // 启动浏览器
    browser = await chromium.launch({
      headless: true,
      args: [
        "--disable-blink-features=AutomationControlled",
        "--disable-web-resources",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-popup-blocking",
        "--disable-prompt-on-repost",
        "--disable-background-networking",
        "--disable-client-side-phishing-detection",
        "--disable-component-extensions-with-background-pages",
        "--disable-default-apps",
        "--disable-extensions",
        "--disable-features=TranslateUI",
        "--disable-sync",
      ],
    });

    // 创建隐身上下文（带反爬虫对策）
    context = await createStealthContext(browser as any);

    // 创建页面
    page = await (context as any).newPage();

    // 设置导航超时
    (page as any).setDefaultNavigationTimeout(30000);
    (page as any).setDefaultTimeout(30000);

    // 添加随机延迟以避免被检测
    await new Promise(resolve => setTimeout(resolve, getRandomDelay(1000, 2000)));

    // 导航到目标 URL
    console.log(`[Automation] 导航到 ${config.url}`);
    await (page as any).goto(config.url, { waitUntil: "networkidle" });

    // 添加随机延迟
    await new Promise(resolve => setTimeout(resolve, getRandomDelay(500, 1500)));

    // 如果提供了自定义脚本，执行自定义脚本
    if (config.script) {
      console.log("[Automation] 执行自定义脚本");
      if (!page) throw new Error("Page is not initialized");
      try {
        // 创建一个函数来执行脚本
        const result = await page.evaluate(
          ({ script, username, password }: any) => {
            // 将脚本作为函数执行
            const func = new Function("username", "password", script);
            return func(username, password);
          },
          { script: config.script, username: config.username, password: config.password }
        );

        console.log("[Automation] 自定义脚本执行结果:", result);
      } catch (error) {
        throw new Error(`自定义脚本执行失败: ${error instanceof Error ? error.message : String(error)}`);
      }
    } else {
      // 执行默认的登录和签到流程
      console.log("[Automation] 执行默认登录流程");

      if (!page) throw new Error("Page is not initialized");

      // 尝试查找并填充用户名字段
      const usernameSelectors = [
        'input[type="text"]',
        'input[name="username"]',
        'input[name="user"]',
        'input[name="email"]',
        'input[id*="user"]',
        'input[id*="name"]',
      ];

      let usernameField = null;
      for (const selector of usernameSelectors) {
        usernameField = await page.$(selector);
        if (usernameField) {
          console.log(`[Automation] 找到用户名字段: ${selector}`);
          break;
        }
      }

      if (usernameField) {
        await usernameField.fill(config.username);
        await new Promise(resolve => setTimeout(resolve, getRandomDelay(300, 800)));
      }

      // 尝试查找并填充密码字段
      const passwordField = await page.$('input[type="password"]');
      if (passwordField) {
        await passwordField.fill(config.password);
        await new Promise(resolve => setTimeout(resolve, getRandomDelay(300, 800)));
      }

      // 尝试查找并点击登录按钮
      if (!page) throw new Error("Page is not initialized");
      const submitButtons = [
        'button[type="submit"]',
        'button:has-text("登录")',
        'button:has-text("Sign In")',
        'button:has-text("Login")',
        'input[type="submit"]',
      ];

      let submitted = false;
      for (const selector of submitButtons) {
        const button = await page.$(selector);
        if (button) {
          console.log(`[Automation] 点击提交按钮: ${selector}`);
          await button.click();
          submitted = true;
          break;
        }
      }

      if (!submitted) {
        throw new Error("无法找到登录提交按钮");
      }

      // 等待页面加载
      await new Promise(resolve => setTimeout(resolve, getRandomDelay(1500, 3000)));

      // 尝试查找签到按钮并点击
      if (!page) throw new Error("Page is not initialized");
      const checkinButtons = [
        'button:has-text("签到")',
        'button:has-text("Check In")',
        'button:has-text("Checkin")',
        'a:has-text("签到")',
        'a:has-text("Check In")',
      ];

      let checkinClicked = false;
      for (const selector of checkinButtons) {
        const button = await page.$(selector);
        if (button) {
          console.log(`[Automation] 点击签到按钮: ${selector}`);
          await button.click();
          checkinClicked = true;
          break;
        }
      }

      if (!checkinClicked) {
        console.log("[Automation] 未找到签到按钮，但流程继续");
      }

      // 等待最终结果
      await new Promise(resolve => setTimeout(resolve, getRandomDelay(1500, 2500)));
    }

    const duration = Date.now() - startTime;

    return {
      success: true,
      message: "自动化任务执行成功",
      duration,
    };
  } catch (error) {
    const duration = Date.now() - startTime;
    const errorMessage = error instanceof Error ? error.message : String(error);

    console.error("[Automation] 执行失败:", errorMessage);

    // 尝试获取错误截图
    let screenshot: Buffer | undefined;
    try {
      if (page) {
        screenshot = await page.screenshot({ fullPage: true });
      }
    } catch (screenshotError) {
      console.error("[Automation] 无法获取截图:", screenshotError);
    }

    return {
      success: false,
      message: "自动化任务执行失败",
      duration,
      errorDetails: errorMessage,
      screenshot,
    };
  } finally {
    // 清理资源
    try {
      if (page) await page.close();
      if (context) await context.close();
      if (browser) await browser.close();
    } catch (cleanupError) {
      console.error("[Automation] 清理资源失败:", cleanupError);
    }
  }
}

/**
 * 批量执行多个自动化任务
 */
export async function executeBatchAutomationTasks(
  configs: AutomationExecutionConfig[]
): Promise<AutomationExecutionResult[]> {
  const results: AutomationExecutionResult[] = [];

  for (let i = 0; i < configs.length; i++) {
    const config = configs[i];
    const result = await executeAutomationTask(config);
    results.push(result);

    // 任务之间添加随机延迟
    if (i < configs.length - 1) {
      await new Promise(resolve => setTimeout(resolve, getRandomDelay(2000, 5000)));
    }
  }

  return results;
}
