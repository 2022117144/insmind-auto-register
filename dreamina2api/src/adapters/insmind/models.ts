/**
 * insMind 模型管理
 *
 * 真实抓包确认的模型代码（2026-06-09）:
 * - 生图: agent-gpt-image-2
 * - 生视频: Pixversev60, Wan27
 *
 * 模型端点: GET /api/mns/models/codes-in-activity
 */
import _ from "lodash";
import { RegionInfo, ModelResult, ModelSetKey, ResolutionResult } from "./types.ts";
import { IMAGE_MODEL_MAP, VIDEO_MODEL_MAP, DEFAULT_IMAGE_MODEL, DEFAULT_VIDEO_MODEL, RESOLUTION_OPTIONS } from "./constants.ts";

// ========== 模型映射 ==========

/** 按区域获取图像模型映射 */
export function getImageModelMapBySet(_set: ModelSetKey): Record<string, string> {
  return IMAGE_MODEL_MAP;
}

/** 按区域获取视频模型映射 */
export function getVideoModelMapBySet(_set: ModelSetKey): Record<string, string> {
  return VIDEO_MODEL_MAP;
}

/** 获取支持的图像模型列表 */
export function getSupportedImageModels(_set: ModelSetKey): string[] {
  return Object.keys(IMAGE_MODEL_MAP);
}

/** 获取支持的视频模型列表 */
export function getSupportedVideoModels(_set: ModelSetKey): string[] {
  return Object.keys(VIDEO_MODEL_MAP);
}

/**
 * 获取图像模型映射（对外名 → 内部 scene_code）
 * insMind 目前直接使用模型代码，不进行转换
 */
export function getImageModel(model: string, _regionInfo: RegionInfo): ModelResult {
  const userModel = model || DEFAULT_IMAGE_MODEL;
  return { model: userModel, userModel };
}

/**
 * 获取视频模型映射（对外名 → 内部 scene_code）
 */
export function getVideoModel(model: string, _regionInfo: RegionInfo): string {
  return model || DEFAULT_VIDEO_MODEL;
}

// ========== 分辨率解析 ==========

/**
 * 解析分辨率参数
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