/**
 * insMind API 通用常量
 *
 * insMind = 稿定设计海外版 (gaoding.com)
 * 真实抓包确认（2026-06-09）：
 * - AI 生成端点: POST sse.insmind.com/api/ai-agent/v1/thread/completion
 * - 任务查询: GET /api/dam/ai/records?task_id=xxx
 * - 模型查询: GET /api/mns/models/codes-in-activity?codes=xxx
 * - 素材上传: POST /api/tb-dam/asset/upload/tokens
 * - 编辑器: PUT /api/tb-dam/v2/editors/template/{id}
 * - 用户权限: GET /api/structure/user/permissions?app_codes=gdproductimg
 * - 内容推荐: POST /api/v3/cp/recommend-contents/general
 */

// ========== API 基础 URL ==========

export const BASE_URL_INSMIND = "https://www.insmind.com";
export const BASE_URL_SSE = "https://sse.insmind.com";
export const BASE_URL_UMS = "https://ums.insmind.com";

// ========== AI Agent ==========

export const AI_AGENT_PATH = "/api/ai-agent/v1/thread/completion";
export const DEFAULT_INPUT_SKILL_ID = "4";

// ========== 平台标识 ==========

export const PLATFORM_CODE = "insmind";
export const VERSION_CODE = "1.0.0";

// ========== 模型集合键 ==========

// ModelSetKey 定义已移至 types.ts 以避免与 index.ts 中 export * 冲突

// ========== 模型常量 ==========

export const DEFAULT_IMAGE_MODEL = "agent-gpt-image-2";
export const DEFAULT_VIDEO_MODEL = "Pixversev60";

/** 图像模型映射（对外名 → 内部 scene_code） */
export const IMAGE_MODEL_MAP: Record<string, string> = {
  "agent-gpt-image-2": "agent-gpt-image-2",
  "insmind-v1": "agent-gpt-image-2",
};

/** 视频模型映射（对外名 → 内部 scene_code） */
export const VIDEO_MODEL_MAP: Record<string, string> = {
  "Pixversev60": "Pixversev60",
  "Wan27": "Wan27",
};

// ========== 分辨率选项 ==========

export const RESOLUTION_OPTIONS: Record<string, Record<string, { width: number; height: number; ratio: number }>> = {
  "2k": {
    "1:1": { width: 1024, height: 1024, ratio: 1 },
    "16:9": { width: 1920, height: 1080, ratio: 16 / 9 },
    "9:16": { width: 1080, height: 1920, ratio: 9 / 16 },
    "4:3": { width: 1440, height: 1080, ratio: 4 / 3 },
    "3:4": { width: 1080, height: 1440, ratio: 3 / 4 },
  },
  "1k": {
    "1:1": { width: 512, height: 512, ratio: 1 },
    "16:9": { width: 960, height: 540, ratio: 16 / 9 },
    "9:16": { width: 540, height: 960, ratio: 9 / 16 },
  },
};

export const RESOLUTION_OPTIONS_NANOBANANAPRO_4K: Record<string, { width: number; height: number; ratio: number }> = {};

// ========== 伪装请求头 ==========

export const FAKE_HEADERS: Record<string, string> = {
  Accept: "application/json, text/plain, */*",
  "Accept-Encoding": "gzip, deflate, br",
  "Accept-language": "zh-CN,zh;q=0.9",
  "Cache-control": "no-cache",
  Pragma: "no-cache",
  "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not_A Brand";v="99"',
  "Sec-Ch-Ua-Mobile": "?0",
  "Sec-Ch-Ua-Platform": '"Windows"',
  "Sec-Fetch-Dest": "empty",
  "Sec-Fetch-Mode": "cors",
  "Sec-Fetch-Site": "same-origin",
  "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
};

// ========== 轮询配置 ==========

export const POLLING_CONFIG = {
  MAX_POLL_COUNT: 60,
  POLL_INTERVAL: 3000,
  STABLE_ROUNDS: 3,
  TIMEOUT_SECONDS: 180,
};

export const STATUS_CODE_MAP: Record<number, string> = {
  0: "INIT",
  10: "SUCCESS",
  20: "PROCESSING",
  30: "FAILED",
  50: "COMPLETED",
};

export const RETRY_CONFIG = {
  MAX_RETRIES: 3,
  BASE_DELAY: 1000,
  MAX_DELAY: 5000,
};

// ========== 上传相关 ==========

export const EDITOR_URL = "/editor/canvas?type=board";
export const RECOMMEND_CONTENT_PATH = "/api/v3/cp/recommend-contents/general";
export const USER_PERMISSIONS_PATH = "/api/structure/user/permissions?app_codes=gdproductimg";
