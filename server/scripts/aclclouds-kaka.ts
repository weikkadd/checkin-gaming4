/**
 * dash.aclclouds.com 卡卡项目自动续期脚本
 *
 * 网站: https://dash.aclclouds.com/projects
 * 项目: 卡卡（node.js 通用 / 机器人 / 免费）
 * 登录方式: Google OAuth
 * 续期规则: 续期按钮在到期前 2 天出现
 *
 * 使用方式:
 * 1. 在 Playwright 的 Page 上调用此脚本
 * 2. 需要先打开浏览器并导航到登录页
 */

import type { Page, Browser, BrowserContext } from "playwright";

// ============================================================
// 🔐 在这里填写你的 Google 凭据（部署前替换）
// ============================================================
const GOOGLE_EMAIL = process.env.KAKA_GOOGLE_EMAIL || "your-google-email@gmail.com";
const GOOGLE_PASSWORD = process.env.KAKA_GOOGLE_PASSWORD || "your-google-password";

// ============================================================
// 站点常量
// ============================================================
const BASE_URL = "https://dash.aclclouds.com";
const LOGIN_URL = `${BASE_URL}/login`;
const PROJECTS_URL = `${BASE_URL}/projects`;

/**
 * 在浏览器中执行 Google OAuth 登录
 * 假设网站使用 Google OAuth 按钮登录
 */
async function doGoogleLogin(page: Page): Promise<boolean> {
  console.log("[AclClouds] 导航到登录页...");
  await page.goto(LOGIN_URL, { waitUntil: "networkidle", timeout: 30000 });
  await randomDelay(1000, 2000);

  // 1. 查找并点击 "Google" / "使用 Google 登录" 按钮
  const googleButtons = [
    'button:has-text("Google")',
    'a:has-text("Google")',
    'button:has-text("谷歌")',
    '[data-provider="google"]',
    '.google-login',
    '.google-btn',
    'button[class*="google"]',
    'a[class*="google"]',
    // 通用：查找包含 google 图标的区域
    'img[alt*="Google"]',
    'svg[class*="google"]',
  ];

  let googleClicked = false;
  for (const selector of googleButtons) {
    const el = await page.$(selector);
    if (el) {
      console.log(`[AclClouds] 找到 Google 登录入口: ${selector}`);
      await el.click();
      googleClicked = true;
      await randomDelay(2000, 4000);
      break;
    }
  }

  // 如果没有找到 Google 按钮，尝试通用点击
  if (!googleClicked) {
    console.log("[AclClouds] 未找到明显的 Google 按钮，尝试查找 'Sign in with Google'...");
    // 可能页面直接嵌入了 Google Sign-In iframe
    const frames = page.frames();
    for (const frame of frames) {
      const googleBtn = await frame.$('div[role="button"]:has-text("Google"), span:has-text("Google")');
      if (googleBtn) {
        await googleBtn.click();
        googleClicked = true;
        await randomDelay(2000, 4000);
        break;
      }
    }
  }

  if (!googleClicked) {
    // 截图帮助调试
    await page.screenshot({ path: "/tmp/aclclouds-login-page.png" });
    throw new Error("无法找到 Google 登录入口，截图已保存到 /tmp/aclclouds-login-page.png");
  }

  // 2. 等待 Google 登录页面加载
  console.log("[AclClouds] 等待 Google 登录页...");
  await randomDelay(2000, 4000);
  console.log(`[AclClouds] 当前 URL: ${page.url()}`);

  // 3. 填写 Google 邮箱
  const emailField = await page.waitForSelector('input[type="email"]', { timeout: 15000 });
  if (emailField) {
    console.log("[AclClouds] 填写 Google 邮箱...");
    await emailField.fill(GOOGLE_EMAIL);
    await randomDelay(500, 1500);
    await page.click('button:has-text("Next"), button:has-text("下一步"), #identifierNext');
  }

  await randomDelay(3000, 5000);

  // 4. 填写 Google 密码
  try {
    const passwordField = await page.waitForSelector(
      'input[type="password"]',
      { timeout: 15000 }
    );
    if (passwordField) {
      console.log("[AclClouds] 填写 Google 密码...");
      await passwordField.fill(GOOGLE_PASSWORD);
      await randomDelay(500, 1500);
      await page.click('button:has-text("Next"), button:has-text("下一步"), #passwordNext');
    }
  } catch {
    // 可能 Google 信任此设备，直接跳过了密码步骤
    console.log("[AclClouds] 未出现密码输入框（可能已信任设备）");
  }

  // 5. 等待 OAuth 回调完成，回到 aclclouds
  console.log("[AclClouds] 等待 OAuth 回调...");
  await randomDelay(5000, 10000);

  // 检查是否回到了 dashboard
  const currentUrl = page.url();
  if (currentUrl.includes("dash.aclclouds.com") && !currentUrl.includes("/login")) {
    console.log("[AclClouds] ✅ Google 登录成功！");
    return true;
  }

  // 可能还有额外的授权页面
  try {
    const allowBtn = await page.$('button:has-text("Allow"), button:has-text("允许"), button:has-text("Continue")');
    if (allowBtn) {
      await allowBtn.click();
      await randomDelay(3000, 5000);
    }
  } catch {
    // 忽略
  }

  return page.url().includes("dash.aclclouds.com") && !page.url().includes("/login");
}

/**
 * 在项目列表中找到"卡卡"项目并进入
 */
async function findKakaProject(page: Page): Promise<boolean> {
  console.log("[AclClouds] 导航到项目列表...");
  await page.goto(PROJECTS_URL, { waitUntil: "networkidle", timeout: 30000 });
  await randomDelay(2000, 4000);

  // 查找"卡卡"项目
  const projectSelectors = [
    'a:has-text("卡卡")',
    'div:has-text("卡卡")',
    'tr:has-text("卡卡")',
    '[class*="project"]:has-text("卡卡")',
    '[class*="card"]:has-text("卡卡")',
    'li:has-text("卡卡")',
  ];

  for (const selector of projectSelectors) {
    const el = await page.$(selector);
    if (el) {
      console.log(`[AclClouds] 找到卡卡项目: ${selector}`);
      await el.click();
      await randomDelay(2000, 4000);
      return true;
    }
  }

  // 更广泛的文本匹配
  const textMatch = await page.evaluate(() => {
    const elements = document.querySelectorAll("a, button, div[role='button'], .clickable");
    for (const el of elements) {
      if (el.textContent?.includes("卡卡")) {
        (el as HTMLElement).click();
        return true;
      }
    }
    return false;
  });

  if (textMatch) {
    await randomDelay(2000, 4000);
    return true;
  }

  await page.screenshot({ path: "/tmp/aclclouds-projects-page.png" });
  throw new Error("未找到'卡卡'项目，截图已保存到 /tmp/aclclouds-projects-page.png");
}

/**
 * 查找并点击续期按钮
 */
async function clickRenewButton(page: Page): Promise<{
  success: boolean;
  reason: string;
}> {
  console.log("[AclClouds] 进入项目详情，查找续期按钮...");
  await randomDelay(2000, 4000);

  const renewButtonSelectors = [
    'button:has-text("续期")',
    'a:has-text("续期")',
    'button:has-text("Renew")',
    'button:has-text("Renewal")',
    'a:has-text("Renew")',
    'button:has-text("延长")',
    'button:has-text("延期")',
    '[class*="renew"]',
    'button[class*="renew"]',
    'button.bg-primary:has-text("续")',
    // 通用续期相关
    'button:has-text("免费续期")',
    'button:has-text("免费")',
  ];

  for (const selector of renewButtonSelectors) {
    const btn = await page.$(selector);
    if (btn) {
      const isVisible = await btn.isVisible();
      const isDisabled = await btn.isDisabled();

      if (isVisible && !isDisabled) {
        console.log(`[AclClouds] 找到续期按钮: ${selector}`);
        const text = await btn.textContent();
        console.log(`[AclClouds] 按钮文本: ${text}`);

        await btn.click();
        await randomDelay(2000, 4000);

        // 检查续期结果
        const success = await checkRenewalResult(page);
        if (success) {
          return { success: true, reason: "续期成功" };
        }
      } else if (isVisible && isDisabled) {
        return { success: false, reason: "续期按钮存在但被禁用" };
      }
    }
  }

  return { success: false, reason: "续期按钮未出现（可能未到续期时间窗口）" };
}

/**
 * 检查续期是否成功
 */
async function checkRenewalResult(page: Page): Promise<boolean> {
  await randomDelay(1000, 3000);

  // 检查成功提示
  const successIndicators = [
    'text=续期成功',
    'text=Renewal successful',
    'text=已续期',
    'text=操作成功',
    '.toast-success',
    '.alert-success',
    '[class*="success"]',
  ];

  for (const selector of successIndicators) {
    const el = await page.$(selector);
    if (el && (await el.isVisible())) {
      console.log(`[AclClouds] 续期成功提示: ${selector}`);
      return true;
    }
  }

  // 检查页面是否有更新后的到期时间
  const remainingInfo = await page.evaluate(() => {
    const body = document.body.innerText;
    const match = body.match(/到期[时间]*[：:]\s*(\d+)\s*(天|d|h|小时)/i);
    return match ? match[0] : null;
  });

  if (remainingInfo) {
    console.log(`[AclClouds] 续期后剩余时间: ${remainingInfo}`);
    return true;
  }

  return false;
}

/**
 * 随机延迟（模拟人类行为）
 */
function randomDelay(min: number, max: number): Promise<void> {
  const ms = Math.floor(Math.random() * (max - min + 1)) + min;
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ============================================================
// 主入口
// ============================================================
export async function executeAclCloudsKakaRenewal(
  browser: Browser
): Promise<{
  success: boolean;
  message: string;
  details: string;
}> {
  let context: BrowserContext | null = null;
  let page: Page | null = null;

  try {
    console.log("[AclClouds:卡卡] 🚀 开始自动续期任务");
    console.log(`[AclClouds:卡卡] 📧 Google 账号: ${GOOGLE_EMAIL.replace(/(.{3}).*(@.*)/, "$1***$2")}`);

    // 创建浏览器上下文
    context = await browser.newContext({
      userAgent:
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      viewport: { width: 1920, height: 1080 },
      locale: "zh-CN",
    });

    page = await context.newPage();
    page.setDefaultTimeout(30000);
    page.setDefaultNavigationTimeout(30000);

    // Step 1: Google 登录
    console.log("[AclClouds:卡卡] Step 1/3: Google 登录");
    const loggedIn = await doGoogleLogin(page);

    if (!loggedIn) {
      await page.screenshot({ path: "/tmp/aclclouds-login-failed.png" });
      return {
        success: false,
        message: "Google 登录失败",
        details: `当前 URL: ${page.url()}，截图: /tmp/aclclouds-login-failed.png`,
      };
    }

    // Step 2: 找到卡卡项目
    console.log("[AclClouds:卡卡] Step 2/3: 定位卡卡项目");
    const projectFound = await findKakaProject(page);

    if (!projectFound) {
      return {
        success: false,
        message: "未找到卡卡项目",
        details: "项目列表中没有找到'卡卡'项目",
      };
    }

    // Step 3: 点击续期按钮
    console.log("[AclClouds:卡卡] Step 3/3: 点击续期");
    const renewResult = await clickRenewButton(page);

    if (renewResult.success) {
      return {
        success: true,
        message: "续期完成",
        details: renewResult.reason,
      };
    }

    await page.screenshot({ path: "/tmp/aclclouds-renew-page.png" });
    return {
      success: false,
      message: "续期未执行",
      details: `${renewResult.reason}，截图: /tmp/aclclouds-renew-page.png`,
    };
  } catch (error) {
    console.error("[AclClouds:卡卡] 脚本异常:", error);
    if (page) {
      try {
        await page.screenshot({ path: "/tmp/aclclouds-error.png" });
      } catch {}
    }
    return {
      success: false,
      message: "脚本执行异常",
      details: error instanceof Error ? error.message : String(error),
    };
  } finally {
    try {
      if (page) await page.close();
      if (context) await context.close();
    } catch {}
  }
}
