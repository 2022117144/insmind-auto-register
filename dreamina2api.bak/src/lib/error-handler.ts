/**
 * 错误处理 - 桥接到 insMind 适配层
 *
 * 所有 insMind 特定实现已迁移到 src/adapters/insmind/errors.ts
 */
export {
  type InsMindErrorResponse,
  buildDetailedApiError,
  handleApiError,
  handleNetworkError,
  handlePollingTimeout,
  handleGenerationFailure,
  JimengErrorHandler,
} from "@/adapters/insmind/errors.ts";
