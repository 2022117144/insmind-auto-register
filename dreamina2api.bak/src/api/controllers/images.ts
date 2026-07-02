import _ from "lodash";

import APIException from "@/lib/exceptions/APIException.ts";
import EX from "@/api/consts/exceptions.ts";
import util from "@/lib/util.ts";
import { request, parseRegionFromToken, RegionInfo } from "./core.ts";
import logger from "@/lib/logger.ts";
import { DEFAULT_IMAGE_MODEL, BASE_URL_SSE, AI_AGENT_PATH } from "@/api/consts/common.ts";
import { uploadImageFromUrl, uploadFile } from "@/lib/image-uploader.ts";
import { buildImageGenerationPayload, resolveResolution, ResolutionResult } from "@/api/builders/payload-builder.ts";
import { extractImageUrls } from "@/lib/image-utils.ts";

export const DEFAULT_MODEL = DEFAULT_IMAGE_MODEL;

export interface ModelResult {
  model: string;
  userModel: string;
}

/**
 * 获取模型映射
 */
export function getModel(model: string, _regionInfo: RegionInfo): ModelResult {
  const userModel = model || DEFAULT_MODEL;
  return { model: userModel, userModel };
}

/**
 * 文生图
 * 使用 AI Agent SSE 接口
 */
export async function generateImages(
  model: string,
  prompt: string,
  {
    negativePrompt,
    ratio = "1:1",
    resolution = "2k",
    sampleStrength,
    intelligentRatio,
    seed,
    imageCount = 1,
  }: {
    negativePrompt?: string;
    ratio?: string;
    resolution?: string;
    sampleStrength?: number;
    intelligentRatio?: boolean;
    seed?: number;
    imageCount?: number;
  },
  token: string,
  regionInfo: RegionInfo
): Promise<{ data: { url: string; revised_prompt?: string }[]; created: number }> {
  const modelCode = getModel(model, regionInfo).model;
  logger.info(`文生图: prompt="${prompt.substring(0, 50)}..." model=${modelCode}`);

  const resolutionResult = resolveResolution(model, regionInfo, resolution, ratio);

  // 使用 AI Agent 格式构建 payload
  const payload = buildImageGenerationPayload({
    prompt,
    model: modelCode,
    negativePrompt,
    width: resolutionResult.width,
    height: resolutionResult.height,
    seed: seed || Math.floor(Math.random() * 100000000),
    imageCount,
  });

  // 发送到 SSE 端点
  const result = await request("post", AI_AGENT_PATH, token, {
    data: payload,
    baseUrl: BASE_URL_SSE,
    timeout: 120000,
  });

  // 尝试从 SSE 响应或 JSON 响应中提取图片 URL
  const taskId = result?.task_id || result?.taskId;
  const items = result?.data?.images || result?.data?.items || result?.images || [];
  const imageUrls = extractImageUrls(items);

  if (imageUrls.length > 0) {
    return {
      data: imageUrls.map((url: string) => ({ url, revised_prompt: prompt })),
      created: util.unixTimestamp(),
    };
  }

  // 可能直接返回了 URL
  const singleUrl = result?.data?.url || result?.url;
  if (singleUrl) {
    return {
      data: [{ url: singleUrl, revised_prompt: prompt }],
      created: util.unixTimestamp(),
    };
  }

  // 如果是异步任务，抛出异常让上层处理
  if (taskId) {
    throw new APIException(EX.API_REQUEST_FAILED,
      `图片生成已提交为异步任务 (id=${taskId})，请使用异步模式查询`);
  }

  throw new APIException(EX.API_IMAGE_GENERATION_FAILED, "未能从响应中提取图片URL");
}

/**
 * 图生图
 */
export async function generateImageComposition(
  model: string,
  prompt: string,
  images: (string | Buffer)[],
  {
    ratio = "1:1",
    resolution = "2k",
    sampleStrength = 0.5,
    negativePrompt = "",
    intelligentRatio = false,
  }: {
    ratio?: string;
    resolution?: string;
    sampleStrength?: number;
    negativePrompt?: string;
    intelligentRatio?: boolean;
  },
  token: string,
  regionInfo: RegionInfo
): Promise<{ data: { url: string }[]; created: number }> {
  const modelCode = getModel(model, regionInfo).model;
  logger.info(`图生图: prompt="${prompt.substring(0, 50)}..."`);

  // 上传参考图片
  const uploadedUrls: string[] = [];
  for (const img of images) {
    if (typeof img === "string") {
      const result = await uploadImageFromUrl(img, token, regionInfo);
      uploadedUrls.push(result.uri);
    } else {
      const result = await uploadFile(Buffer.from(img), token, "ref-image.png");
      uploadedUrls.push(result.uri);
    }
  }

  const resolutionResult = resolveResolution(model, regionInfo, resolution, ratio);

  const payload = buildImageGenerationPayload({
    prompt,
    model: modelCode,
    negativePrompt,
    width: resolutionResult.width,
    height: resolutionResult.height,
    imageCount: 1,
    imageUrls: uploadedUrls,
  });

  const result = await request("post", AI_AGENT_PATH, token, {
    data: payload,
    baseUrl: BASE_URL_SSE,
    timeout: 120000,
  });

  const taskId = result?.task_id || result?.taskId;
  const items = result?.data?.images || result?.data?.items || result?.images || [];
  const imageUrls = extractImageUrls(items);

  if (imageUrls.length > 0) {
    return {
      data: imageUrls.map((url: string) => ({ url })),
      created: util.unixTimestamp(),
    };
  }

  const singleUrl = result?.data?.url || result?.url;
  if (singleUrl) {
    return {
      data: [{ url: singleUrl }],
      created: util.unixTimestamp(),
    };
  }

  if (taskId) {
    throw new APIException(EX.API_REQUEST_FAILED,
      `图片生成已提交为异步任务 (id=${taskId})，请使用异步模式查询`);
  }

  throw new APIException(EX.API_IMAGE_GENERATION_FAILED, "未能从响应中提取图片URL");
}

/**
 * 查询 AI 记录（用于异步任务轮询）
 * 抓包确认: GET /api/dam/ai/records?task_id=xxx
 */
export async function queryAiRecord(taskId: string, token: string): Promise<any> {
  try {
    const result = await request("get", `/api/dam/ai/records?task_id=${taskId}`, token);
    return result?.data || result;
  } catch {
    return null;
  }
}