/**
 * insMind 认证模块
 *
 * 认证方式:
 * - OAuth2 via ums.insmind.com (Bearer token)
 * - Cookie: token.prod (base64 JSON with access_token)
 * - 直接 JWT (eyJ...)
 */
import _ from "lodash";
import { TokenInfo, TokenWithProxy, RegionInfo, CountryProfile } from "./types.ts";
import { getCountryProfile } from "./region.ts";

// ========== Token 拆分 & 解析 ==========

/**
 * 从 Authorization header 解析 token 列表
 * 支持格式: "Bearer <token>" 或 "<token>"
 * 多个 token 用逗号分隔 (轮询模式)
 */
export function tokenSplit(authHeader: string): string[] {
  const header = authHeader.trim();
  const raw = header.replace(/^Bearer\s+/i, "").trim();
  return raw.split(",").map(t => t.trim()).filter(Boolean);
}

/**
 * 解析单个 token 字符串为 TokenInfo
 */
export function parseToken(rawToken: string): TokenInfo {
  const trimmed = rawToken.trim();
  return {
    rawToken: trimmed,
    accessToken: trimmed,
  };
}

/**
 * 获取/刷新 access_token
 * insMind 使用 Cookie 认证 + Bearer token，当前直接返回原始 token
 */
export async function acquireToken(token: string): Promise<string> {
  return token;
}

/**
 * 从 Cookie 字符串中提取指定 key 的值
 */
export function getCookieValue(cookieStr: string, key: string): string | null {
  const match = cookieStr.match(new RegExp(`${key}=([^;]+)`));
  return match ? match[1] : null;
}

/**
 * 从 token 中提取 Cookie 头
 */
export function extractCookies(token: string): Record<string, string> {
  const cookies: Record<string, string> = {};
  const cleaned = token.replace(/^Bearer\s+/i, "").trim();

  if (cleaned.includes("=") && cleaned.includes(";")) {
    cleaned.split(";").forEach(pair => {
      const [k, ...v] = pair.trim().split("=");
      if (k) cookies[k.trim()] = v.join("=");
    });
  }

  return cookies;
}

/**
 * 从原始 token 中解析代理信息
 * 格式: "https://proxy:port@token" 或 "socks5://proxy:port@token"
 */
export function parseProxyFromToken(rawToken: string): TokenWithProxy {
  const tokenValue = rawToken.trim();
  const proxyPattern = /^(https?|socks(?:4|5)?):\/\//i;
  if (!proxyPattern.test(tokenValue)) return { token: tokenValue, proxyUrl: null };

  const lastAtIndex = tokenValue.lastIndexOf("@");
  if (lastAtIndex <= 0 || lastAtIndex === tokenValue.length - 1)
    return { token: tokenValue, proxyUrl: null };

  const proxyUrl = tokenValue.slice(0, lastAtIndex);
  const token = tokenValue.slice(lastAtIndex + 1);
  if (!proxyUrl || !token) return { token: tokenValue, proxyUrl: null };

  return { token, proxyUrl };
}

/**
 * 从 token 中解析地区信息 (insMind 为单一平台, 固定返回 insmind profile)
 */
export function parseRegionFromToken(_token: string): RegionInfo {
  const profile = getCountryProfile("insmind");
  return {
    countryCode: "insmind",
    profile,
    isInternational: false,
    isCN: true,
  };
}

/**
 * 解析并净化 token（移除 proxy 前缀 + 提取 access_token）
 */
export function resolveToken(rawToken: string): { token: string; proxyUrl: string | null } {
  const { token, proxyUrl } = parseProxyFromToken(rawToken);
  return { token, proxyUrl };
}