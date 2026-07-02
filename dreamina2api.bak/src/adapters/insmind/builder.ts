/**
 * insMind Builder - AI Agent 请求体构建
 *
 * 真实抓包确认的 AI Agent SSE 请求格式（2026-06-09）:
 * POST https://sse.insmind.com/api/ai-agent/v1/thread/completion
 *
 * 请求体:
 * {
 *   "content": {
 *     "type": "plain",
 *     "scene_code": "<model_code>",
 *     "prompt": [
 *       {"type": "text", "content": "..."},
 *       {"type": "media", "url": "...", "name": "...", "mime": "image/png"}
 *     ],
 *     "parameters": { ... },
 *     "text": ""
 *   },
 *   "name": "user",
 *   "role": "user",
 *   "thread_id": "...",
 *   "input_skill_id": "4",
 *   "extra": { "enable_websearch": false }
 * }
 */
import { AiAgentPayloadParams, ImageGenerationParams, VideoGenerationParams } from "./types.ts";

/**
 * 构建通用 AI Agent 请求体
 */
export function buildAiAgentPayload(params: AiAgentPayloadParams): Record<string, any> {
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

  return {
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
}

/**
 * 构建图片生成请求体
 */
export function buildImageGenerationPayload(params: ImageGenerationParams): Record<string, any> {
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

/**
 * 构建视频生成请求体
 */
export function buildVideoGenerationPayload(params: VideoGenerationParams): Record<string, any> {
  const resolution = params.resolution || "720P";
  const duration = params.duration || 5;

  const promptSuffix = `Using video tool: ${params.model}, Resolution: ${resolution}, Duration: ${duration} seconds`;

  const parameters: Record<string, any> = {
    mode: params.videoUrls && params.videoUrls.length > 0 ? "ImageToVideo" : "Frames",
    ratio: params.ratio || "",
    resolution,
    duration: String(duration),
    styleCode: params.model,
  };

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