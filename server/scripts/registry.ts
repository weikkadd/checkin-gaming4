/**
 * 自定义续期脚本注册表
 *
 * 每个网站的续期逻辑不同，这里注册专用的处理函数。
 * 新增网站续期脚本时，在这里添加即可。
 */

import type { Browser } from "playwright";
import { executeAclCloudsKakaRenewal } from "../scripts/aclclouds-kaka";

export interface CustomRenewalHandler {
  /** 处理函数的显示名称 */
  name: string;
  /** 匹配条件：服务 URL 包含此字符串 */
  urlMatch: string;
  /** 执行函数 */
  execute: (browser: Browser) => Promise<{
    success: boolean;
    message: string;
    details?: string;
  }>;
}

/**
 * 所有注册的自定义续期脚本
 */
export const renewalHandlers: CustomRenewalHandler[] = [
  {
    name: "AclClouds 卡卡项目",
    urlMatch: "dash.aclclouds.com",
    execute: executeAclCloudsKakaRenewal,
  },
  // 在这里添加更多网站的续期脚本...
];

/**
 * 根据服务 URL 查找匹配的续期处理器
 */
export function findRenewalHandler(
  serviceUrl: string
): CustomRenewalHandler | undefined {
  return renewalHandlers.find((handler) =>
    serviceUrl.includes(handler.urlMatch)
  );
}
