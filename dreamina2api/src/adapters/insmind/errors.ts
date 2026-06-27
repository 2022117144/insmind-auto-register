/**
 * insMind 统一错误处理
 *
 * 格式化 insMind API 的错误响应为 APIException
 */
import APIException from "@/lib/exceptions/APIException.ts";
import EX from "@/api/consts/exceptions.ts";
import logger from "@/lib/logger.ts";
import { InsMindErrorResponse } from "./types.ts";

// 重新导出类型，供桥接层使用
export type { InsMindErrorResponse };

interface ErrorContext {
  method?: string;
  path?: string;
  context?: string;
}

/**
 * 构建详细的 API 错误消息
 */
export function buildDetailedApiError(response: InsMindErrorResponse): string {
  const ret = response.ret || String(response.code || "unknown");
  const errmsg = response.errmsg || response.message || "未知错误";
  return `[请求失败]: ${errmsg} (错误码: ${ret})`;
}

/**
 * 处理 API 错误响应（非 2xx 状态码但服务器返回了有效 JSON）
 */
export function handleApiError(
  response: { status: number; data: any },
  ctx: ErrorContext = {}
): never {
  const { status, data: errData } = response;
  const ret = errData?.ret || errData?.code || String(status);
  const errmsg = errData?.errmsg || errData?.message || `HTTP ${status}`;

  logger.error(`insMind API 错误: ${ctx.method?.toUpperCase()} ${ctx.path} -> ${status}: ${errmsg}`);

  if (status === 401) {
    throw new APIException(EX.API_TOKEN_EXPIRES, `[登录失效]: token 已过期，请重新获取`);
  }

  throw new APIException(
    EX.API_REQUEST_FAILED,
    `[请求失败] ${status}: ${errmsg}`
  );
}

/**
 * 处理网络/传输层错误
 */
export function handleNetworkError(
  error: any,
  ctx: ErrorContext = {}
): never {
  const { context = "网络请求" } = ctx;

  if (error.code === "ECONNABORTED") {
    throw new APIException(EX.API_REQUEST_FAILED, `[请求超时]: ${ctx.path || context}`);
  }

  if (error.response?.status >= 500) {
    throw new APIException(EX.API_REQUEST_FAILED, `[服务器错误]: (${error.response.status})`);
  }

  if (error.response?.status === 429) {
    throw new APIException(EX.API_REQUEST_FAILED, `[频率限制]: 请求过于频繁`);
  }

  throw new APIException(EX.API_REQUEST_FAILED, `[${context}失败]: ${error.message}`);
}

/**
 * 处理轮询超时
 */
export function handlePollingTimeout(
  pollCount: number,
  maxPollCount: number,
  elapsedTime: number,
  status: number,
  itemCount: number,
  historyId?: string
): void {
  const message = `轮询超时: ${pollCount} 次, ${elapsedTime}秒, 状态: ${status}, 结果: ${itemCount}`;
  logger.warn(message + (historyId ? `, historyId=${historyId}` : ""));
  if (itemCount === 0) {
    throw new APIException(EX.API_IMAGE_GENERATION_FAILED, `生成超时`);
  }
}

/**
 * 处理生成失败
 */
export function handleGenerationFailure(
  status: number,
  failCode: string | undefined,
  historyId?: string,
  type: "image" | "video" = "image",
  itemCount: number = 0
): boolean {
  const typeText = type === "image" ? "图像" : "视频";
  const message = `${typeText}生成失败: status=${status}, failCode=${failCode}`;
  if (itemCount > 0) {
    logger.warn(message);
    return false;
  }
  throw new APIException(
    type === "image" ? EX.API_IMAGE_GENERATION_FAILED : EX.API_VIDEO_GENERATION_FAILED,
    `${typeText}生成失败，状态码: ${status}`
  );
}

/**
 * 类风格的错误处理器（向后兼容）
 */
export class JimengErrorHandler {
  static handleApiResponse(
    response: InsMindErrorResponse,
    options: { context?: string } = {}
  ): never {
    return handleApiError({ status: Number(response.code || 400), data: response }, options);
  }

  static handleNetworkError(error: any, options: { context?: string } = {}): never {
    return handleNetworkError(error, options);
  }

  static handlePollingTimeout(...args: Parameters<typeof handlePollingTimeout>): void {
    return handlePollingTimeout(...args);
  }

  static handleGenerationFailure(...args: Parameters<typeof handleGenerationFailure>): boolean {
    return handleGenerationFailure(...args);
  }
}