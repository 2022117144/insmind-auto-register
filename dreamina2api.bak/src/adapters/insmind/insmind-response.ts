/**
 * insMind 响应格式封装
 *
 * 将内部响应格式化为 insMind 风格的 JSON 响应。
 * 同时保留 OpenAI 兼容格式的选项。
 */
import { VERSION_CODE, PLATFORM_CODE } from "./constants.ts";

export interface InsMindApiResponse<T = any> {
  code: number;
  message: string;
  data: T;
  request_id?: string;
  version?: string;
}

export interface InsMindErrorResponse {
  code: number;
  message: string;
  request_id?: string;
  version?: string;
  details?: any;
}

// ========== 构建成功响应 ==========

export function success<T>(data: T, message: string = "success"): InsMindApiResponse<T> {
  return {
    code: 0,
    message,
    data,
    version: VERSION_CODE,
  };
}

// ========== 构建错误响应 ==========

export function error(
  code: number,
  message: string,
  details?: any
): InsMindErrorResponse {
  return {
    code,
    message,
    version: VERSION_CODE,
    details,
  };
}

// ========== 常见错误快捷方法 ==========

export function badRequest(message: string = "请求参数错误"): InsMindErrorResponse {
  return error(400, message);
}

export function unauthorized(message: string = "未授权，请提供有效的 Token"): InsMindErrorResponse {
  return error(401, message);
}

export function forbidden(message: string = "无权限访问"): InsMindErrorResponse {
  return error(403, message);
}

export function notFound(message: string = "资源不存在"): InsMindErrorResponse {
  return error(404, message);
}

export function tooManyRequests(message: string = "请求过于频繁"): InsMindErrorResponse {
  return error(429, message);
}

export function internalError(message: string = "服务器内部错误"): InsMindErrorResponse {
  return error(500, message);
}

// ========== OpenAI 兼容格式转换 ==========

export interface OpenAiImageResult {
  created: number;
  data: Array<{ url: string; revised_prompt?: string }>;
}

export interface OpenAiVideoResult {
  created: number;
  data: Array<{ url: string; revised_prompt?: string }>;
}

export interface OpenAiModelEntry {
  id: string;
  object: "model";
  owned_by: string;
  category: "image" | "video";
}

/**
 * 将 insMind 内部生成结果包装为 OpenAI 兼容格式
 */
export function toOpenAiFormat(
  result: OpenAiImageResult | OpenAiVideoResult,
  kind: "image" | "video"
): InsMindApiResponse {
  return success({
    object: "list",
    kind,
    created: result.created,
    data: result.data,
  });
}
