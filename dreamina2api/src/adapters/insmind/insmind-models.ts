/**
 * insMind 模型映射表
 *
 * 将 insMind 对外模型名映射到内部 scene_code。
 * 同时提供 OpenAPI 兼容的模型列表端点格式。
 */
import {
  IMAGE_MODEL_MAP,
  VIDEO_MODEL_MAP,
  DEFAULT_IMAGE_MODEL,
  DEFAULT_VIDEO_MODEL,
} from "./constants.ts";

export interface InsMindModelEntry {
  id: string;
  object: "model";
  owned_by: string;
  category: "image" | "video";
  description?: string;
  capabilities?: string[];
}

// ========== 模型元数据 ==========

const IMAGE_MODEL_META: Record<string, Partial<InsMindModelEntry>> = {
  "agent-gpt-image-2": {
    description: "insMind GPT Image 2.0 — 文生图/图生图",
    capabilities: ["text-to-image", "image-to-image", "negative-prompt"],
  },
  "insmind-v1": {
    description: "insMind V1 — 基础文生图模型（映射到 agent-gpt-image-2）",
    capabilities: ["text-to-image"],
  },
};

const VIDEO_MODEL_META: Record<string, Partial<InsMindModelEntry>> = {
  "Pixversev60": {
    description: "PixVerse V6.0 — 高质量文生视频/图生视频",
    capabilities: ["text-to-video", "image-to-video"],
  },
  "Wan27": {
    description: "Wan 2.7 — 高效文生视频模型",
    capabilities: ["text-to-video"],
  },
};

// ========== 获取模型列表（OpenAPI 格式） ==========

export function getInsMindModelList(): InsMindModelEntry[] {
  const imageModels: InsMindModelEntry[] = Object.keys(IMAGE_MODEL_MAP).map((id) => ({
    id,
    object: "model" as const,
    owned_by: "insmind-api",
    category: "image" as const,
    ...IMAGE_MODEL_META[id],
  }));

  const videoModels: InsMindModelEntry[] = Object.keys(VIDEO_MODEL_MAP).map((id) => ({
    id,
    object: "model" as const,
    owned_by: "insmind-api",
    category: "video" as const,
    ...VIDEO_MODEL_META[id],
  }));

  return [...imageModels, ...videoModels];
}

// ========== 获取默认模型 ==========

export function getDefaultImageModel(): string {
  return DEFAULT_IMAGE_MODEL;
}

export function getDefaultVideoModel(): string {
  return DEFAULT_VIDEO_MODEL;
}

// ========== 模型别名解析 ==========

/**
 * 解析 insMind 对外模型名为内部 scene_code
 */
export function resolveImageModel(alias: string): string {
  return IMAGE_MODEL_MAP[alias] || alias;
}

export function resolveVideoModel(alias: string): string {
  return VIDEO_MODEL_MAP[alias] || alias;
}
