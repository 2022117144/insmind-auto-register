/**
 * 通用常量 - 桥接到 insMind 适配层
 *
 * 所有 insMind 特定常量已迁移到 src/adapters/insmind/constants.ts
 * 此文件保留为向后兼容的桥接层。
 */

// 常量从 constants.ts 导出
export {
  BASE_URL_INSMIND,
  BASE_URL_SSE,
  BASE_URL_UMS,
  AI_AGENT_PATH,
  DEFAULT_INPUT_SKILL_ID,
  PLATFORM_CODE,
  VERSION_CODE,
  DEFAULT_IMAGE_MODEL,
  DEFAULT_VIDEO_MODEL,
  IMAGE_MODEL_MAP,
  VIDEO_MODEL_MAP,
  RESOLUTION_OPTIONS,
  RESOLUTION_OPTIONS_NANOBANANAPRO_4K,
  POLLING_CONFIG,
  STATUS_CODE_MAP,
  RETRY_CONFIG,
} from "@/adapters/insmind/constants.ts";

// 类型从 types.ts 导出（避免 constants.ts 与 types.ts 的 ModelSetKey 冲突）
export { type ModelSetKey } from "@/adapters/insmind/types.ts";

// 函数从 models.ts 导出（它们实际定义在 models.ts 中，不在 constants.ts 中）
export {
  getImageModelMapBySet,
  getVideoModelMapBySet,
  getSupportedImageModels,
  getSupportedVideoModels,
} from "@/adapters/insmind/models.ts";
