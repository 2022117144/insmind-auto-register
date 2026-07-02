/**
 * insMind API 核心模块 - 桥接到适配层
 *
 * 所有 insMind 特定实现已迁移到 src/adapters/insmind/
 * 此文件保留为向后兼容的桥接层。
 */
export {
  // Token 解析
  type TokenInfo,
  tokenSplit,
  parseToken,
  acquireToken,
  getCookieValue,
  extractCookies,

  // 地区解析
  type RegionInfo,
  type TokenWithProxy,
  parseRegionFromToken,
  parseProxyFromToken,

  // 统一请求
  request,

  // 积分
  type CreditInfo,
  type VipInfo,
  getCredit,
  getVipStatus,
  receiveCredit,

  // Token 存活检测
  getTokenLiveStatus,

  // 内容审核 & 助手ID
  checkImageContent,
  getAssistantId,

  // 文件系统
  type FileAccessToken,
  getFileAccessToken,
} from "@/adapters/insmind/index.ts";
