/**
 * insMind API 核心请求客户端
 *
 * 底层使用 axios 发送 HTTP 请求到 insMind 各端点。
 * 处理认证（Cookie/Bearer）、代理、错误响应统一格式化。
 */
import axios, { AxiosRequestConfig, AxiosResponse } from "axios";
import { HttpsProxyAgent } from "https-proxy-agent";
import { SocksProxyAgent } from "socks-proxy-agent";

import { InsMindErrorResponse } from "./types.ts";
import { BASE_URL_INSMIND, FAKE_HEADERS } from "./constants.ts";
import { acquireToken, parseProxyFromToken } from "./auth.ts";
import { handleApiError, handleNetworkError } from "./errors.ts";
import logger from "@/lib/logger.ts";

export interface RequestOptions {
  data?: any;
  params?: Record<string, any>;
  headers?: Record<string, string>;
  responseType?: AxiosRequestConfig["responseType"];
  timeout?: number;
  baseUrl?: string;
}

/**
 * 获取 axios 代理配置
 */
function getProxyConfig(proxyUrl: string | null): AxiosRequestConfig {
  if (!proxyUrl) return {};
  if (proxyUrl.startsWith("socks")) {
    return { httpsAgent: new SocksProxyAgent(proxyUrl) };
  }
  return { httpsAgent: new HttpsProxyAgent(proxyUrl) };
}

/**
 * 核心请求函数
 *
 * @param method  HTTP 方法
 * @param path    API 路径（如 /api/v3/xxx）
 * @param token   认证 token
 * @param options 请求选项
 */
export async function request(
  method: "get" | "post" | "put" | "delete" | "patch",
  path: string,
  token: string,
  options: RequestOptions = {}
): Promise<any> {
  const {
    data,
    params,
    headers: extraHeaders,
    responseType,
    timeout = 60000,
    baseUrl = BASE_URL_INSMIND,
  } = options;

  const { token: cleanToken, proxyUrl } = parseProxyFromToken(token);
  let accessToken = await acquireToken(cleanToken);

  // insMind 认证支持多种格式：
  // 1. Bearer token (JWT) → 直接使用
  // 2. token.prod Cookie 值（base64 JSON 包含 access_token 字段）→ 提取 access_token
  // 3. Cookie 字符串 → 提取 token.prod 后解析
  if (accessToken && !accessToken.startsWith("eyJ")) {
    if (accessToken.includes("token.prod=")) {
      const match = accessToken.match(/token\.prod=([^;]+)/);
      if (match) accessToken = match[1];
    }

    try {
      const decoded = JSON.parse(Buffer.from(accessToken, "base64").toString());
      if (decoded.access_token) {
        accessToken = decoded.access_token;
      }
    } catch {
      // 不是 base64 JSON，原样使用
    }
  }

  const url = `${baseUrl}${path}`;
  const reqHeaders: Record<string, string> = {
    ...FAKE_HEADERS,
    ...extraHeaders,
  };

  if (accessToken) {
    reqHeaders["Authorization"] = `Bearer ${accessToken}`;
  }

  const config: AxiosRequestConfig = {
    method,
    url,
    headers: reqHeaders,
    params,
    data,
    responseType,
    timeout,
    ...getProxyConfig(proxyUrl),
  };

  logger.debug(`insMind API 请求: ${method.toUpperCase()} ${path}`);

  try {
    const response: AxiosResponse = await axios(config);
    logger.debug(`insMind API 响应: ${method.toUpperCase()} ${path} -> status=${response.status}`);
    return response.data;
  } catch (error: any) {
    if (error.response) {
      return handleApiError(error.response, { method, path });
    }
    return handleNetworkError(error, { method, path });
  }
}

/**
 * 检查图片内容是否符合安全规范（占位实现）
 */
export async function checkImageContent(
  _imageUrl: string,
  _token: string
): Promise<{ passed: boolean; reason?: string }> {
  logger.debug("checkImageContent: 跳过内容审核（未实现）");
  return { passed: true };
}

/**
 * 获取助手 ID（占位实现）
 */
export async function getAssistantId(
  _token: string,
  _regionInfo?: any
): Promise<number> {
  logger.debug("getAssistantId: 返回默认值 0");
  return 0;
}