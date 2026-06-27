import { RegionInfo } from "@/api/controllers/core.ts";
import { RESOLUTION_OPTIONS } from "@/api/consts/common.ts";

export interface ResolutionResult {
  width: number;
  height: number;
  imageRatio: number;
  resolutionType: string;
  isForced: boolean;
}

/**
 * 分辨率解析
 */
export function resolveResolution(
  _userModel: string,
  _regionInfo: RegionInfo,
  resolution: string = "2k",
  ratio: string = "1:1"
): ResolutionResult {
  const resolutionGroup = RESOLUTION_OPTIONS[resolution];
  if (!resolutionGroup) {
    const supportedResolutions = Object.keys(RESOLUTION_OPTIONS).join(", ");
    throw new Error(`不支持的分辨率 "${resolution}"。支持的分辨率: ${supportedResolutions}`);
  }

  const ratioConfig = resolutionGroup[ratio];
  if (!ratioConfig) {
    const supportedRatios = Object.keys(resolutionGroup).join(", ");
    throw new Error(`在 "${resolution}" 分辨率下，不支持的比例 "${ratio}"。支持的比例: ${supportedRatios}`);
  }

  return {
    width: ratioConfig.width,
    height: ratioConfig.height,
    imageRatio: ratioConfig.ratio,
    resolutionType: resolution,
    isForced: false,
  };
}

// ========== AI Agent 格式构建器 ==========
//
// 真实抓包确认（2026-06-09）：
// insMind 使用 AI Agent 架构（SSE 流式）
// 端点: POST https://sse.insmind.com/api/ai-agent/v1/thread/completion
//
// 请求体格式:
// {
//   "content": {
//     "type": "plain",
//     "scene_code": "Pixversev60",    // 模型代码
//     "prompt": [
//       {"type": "text", "content": "..."},
//       {"type": "media", "url": "...", "name": "...", "mime": "image/png"}
//     ],
//     "parameters": {
//       "mode": "Frames",
//       "ratio": "",
//       "resolution": "720P",
//       "duration": "5",
//       "styleCode": "Pixversev60"
//     },
//     "duration": "5",
//     "resolution": "720P",
//     "text": ""
//   },
//   "name": "user",
//   "role": "user",
//   "thread_id": "...",
//   "local_thread_id": "",
//   "local_message_id": "...",
//   "input_skill_id": "4",
//   "attachments": [],
//   "extra": {
//     "prompt_suffix": "...",
//     "enable_websearch": false
//   }
// }

/**
 * 构建 AI Agent 生成请求体（通用）
 */
export function buildAiAgentPayload(params: {
  sceneCode: string;           // 模型代码，如 Pixversev60
  prompt: string;              // 文本 prompt
  imageUrls?: string[];        // 参考图片 URL
  parameters?: Record<string, any>; // 额外参数
  threadId?: string;           // 已有 thread（续传）
  localMessageId?: string;     // 本地消息 ID
  inputSkillId?: string;       // 技能 ID
  extra?: Record<string, any>; // 额外信息
}): Record<string, any> {
  // 构建 prompt 数组
  const promptItems: any[] = [];

  if (params.prompt) {
    promptItems.push({ type: "text", content: params.prompt });
  }

  if (params.imageUrls && params.imageUrls.length > 0) {
    for (const url of params.imageUrls) {
      promptItems.push({
        type: "media",
        url,
        name: url.split("/").pop() || "image.png",
        mime: "image/png",
      });
    }
  }

  const payload: Record<string, any> = {
    content: {
      type: "plain",
      scene_code: params.sceneCode,
      prompt: promptItems,
      parameters: params.parameters || {},
      text: params.prompt || "",
    },
    name: "user",
    role: "user",
    local_thread_id: "",
    local_message_id: params.localMessageId || `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    thread_id: params.threadId || "",
    input_skill_id: params.inputSkillId || "4",
    attachments: [],
    extra: {
      ...(params.extra || {}),
      enable_websearch: false,
    },
  };

  return payload;
}

/**
 * 构建 insMind 视频生成请求体（AI Agent 格式）
 */
export function buildVideoGenerationPayload(params: {
  prompt: string;
  model: string;
  imageUrls?: string[];
  videoUrls?: string[];
  duration?: number;
  resolution?: string;
  ratio?: string;
}): Record<string, any> {
  const resolution = params.resolution || "720P";
  const duration = params.duration || 5;

  const promptSuffix = `Using video tool: ${params.model}, Resolution: ${resolution}, Duration: ${duration} seconds`;

  const parameters: Record<string, any> = {
    mode: params.videoUrls && params.videoUrls.length > 0 ? "ImageToVideo" : "Frames",
    ratio: params.ratio || "",
    resolution: resolution,
    duration: String(duration),
    styleCode: params.model,
  };

  // 构建 prompt 数组
  const promptItems: any[] = [{ type: "text", content: params.prompt }];

  if (params.imageUrls && params.imageUrls.length > 0) {
    for (const url of params.imageUrls) {
      promptItems.push({
        type: "media",
        url,
        name: url.split("/").pop() || "image.png",
        mime: "image/png",
      });
    }
  }

  if (params.videoUrls && params.videoUrls.length > 0) {
    for (const url of params.videoUrls) {
      promptItems.push({
        type: "media",
        url,
        name: url.split("/").pop() || "video.mp4",
        mime: "video/mp4",
      });
    }
  }

  return {
    content: {
      type: "plain",
      scene_code: params.model,
      prompt: promptItems,
      parameters,
      duration: String(duration),
      resolution,
      text: params.prompt,
    },
    name: "user",
    role: "user",
    local_thread_id: "",
    local_message_id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    thread_id: "",
    input_skill_id: "4",
    attachments: [],
    extra: {
      prompt_suffix: promptSuffix,
      enable_websearch: false,
    },
  };
}

/**
 * 构建 insMind 图片生成请求体（AI Agent 格式）
 */
export function buildImageGenerationPayload(params: {
  prompt: string;
  model: string;
  negativePrompt?: string;
  width: number;
  height: number;
  seed?: number;
  guidanceScale?: number;
  imageCount?: number;
  imageUrls?: string[];
}): Record<string, any> {
  const promptItems: any[] = [];

  if (params.negativePrompt) {
    promptItems.push({ type: "text", content: `${params.prompt} [negative: ${params.negativePrompt}]` });
  } else {
    promptItems.push({ type: "text", content: params.prompt });
  }

  if (params.imageUrls && params.imageUrls.length > 0) {
    for (const url of params.imageUrls) {
      promptItems.push({
        type: "media",
        url,
        name: url.split("/").pop() || "image.png",
        mime: "image/png",
      });
    }
  }

  const parameters: Record<string, any> = {
    mode: params.imageUrls && params.imageUrls.length > 0 ? "ImageToImage" : "TextToImage",
    width: params.width,
    height: params.height,
    num_images: params.imageCount || 1,
  };

  if (params.seed) parameters.seed = params.seed;
  if (params.guidanceScale !== undefined) parameters.guidance_scale = params.guidanceScale;

  return {
    content: {
      type: "plain",
      scene_code: params.model,
      prompt: promptItems,
      parameters,
      text: params.prompt,
    },
    name: "user",
    role: "user",
    local_thread_id: "",
    local_message_id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    thread_id: "",
    input_skill_id: "4",
    attachments: [],
    extra: {
      prompt_suffix: `Using image tool: ${params.model}`,
      enable_websearch: false,
    },
  };
}
