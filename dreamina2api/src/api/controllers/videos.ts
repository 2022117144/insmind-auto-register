import _ from "lodash";
import fs from "fs-extra";
import axios from "axios";

import APIException from "@/lib/exceptions/APIException.ts";
import EX from "@/api/consts/exceptions.ts";
import util from "@/lib/util.ts";
import { request, parseRegionFromToken, RegionInfo } from "./core.ts";
import logger from "@/lib/logger.ts";
import { DEFAULT_VIDEO_MODEL, BASE_URL_SSE, AI_AGENT_PATH, BASE_URL_INSMIND } from "@/api/consts/common.ts";
import { uploadFile } from "@/lib/image-uploader.ts";
import { uploadVideoBuffer, uploadVideoFromUrl } from "@/lib/video-uploader.ts";
import { extractVideoUrl } from "@/lib/image-utils.ts";
import { buildVideoGenerationPayload, buildAiAgentPayload } from "@/api/builders/payload-builder.ts";

export const DEFAULT_MODEL = DEFAULT_VIDEO_MODEL;

/**
 * 视频模型映射 (insMind)
 * 真实抓包确认的模型代码:
 * - Pixversev60: PixVerse V6.0
 * - Wan27: Wan 2.7
 */
export function getModel(model: string, _regionInfo: RegionInfo): string {
  return model || DEFAULT_MODEL;
}

/**
 * 解析 AI Agent SSE 响应，提取 task_id
 * SSE 数据格式: data: {...}
 * 需要查找包含 task_id 的 event
 */
export function parseSseResponse(sseData: string): {
  taskId?: string;
  threadId?: string;
  content?: string;
} {
  const result: any = {};

  // 按行解析 SSE
  const lines = sseData.split("\n");
  for (const line of lines) {
    if (!line.startsWith("data: ")) continue;

    try {
      const data = JSON.parse(line.slice(6));
      if (data.task_id) result.taskId = data.task_id;
      if (data.thread_id) result.threadId = data.thread_id;
      if (data.content) result.content = data.content;
    } catch {
      // 非 JSON 行跳过
    }
  }

  return result;
}

/**
 * 主视频生成函数
 * 使用 AI Agent SSE 接口提交生成任务
 */
export async function generateVideo(
  model: string,
  prompt: string,
  {
    ratio,
    duration,
    imageUrls = [],
    videoUrls = [],
    functionMode,
    negativePrompt,
  }: {
    ratio?: string;
    duration?: number;
    imageUrls?: string[];
    videoUrls?: string[];
    functionMode?: string;
    negativePrompt?: string;
  },
  token: string,
  regionInfo: RegionInfo
): Promise<{
  data: { url: string; revised_prompt?: string }[];
  created: number;
}> {
  const modelCode = getModel(model, regionInfo);
  logger.info(`视频生成: prompt="${prompt.substring(0, 50)}..." model=${modelCode}`);

  // 构建 AI Agent 格式的 payload
  const payload = buildVideoGenerationPayload({
    prompt,
    model: modelCode,
    imageUrls,
    videoUrls,
    duration,
    resolution: ratio === "16:9" ? "720P" : "720P",
    ratio,
  });

  // 发送 SSE 请求（注意 baseUrl 是 sse.insmind.com）
  const result = await request("post", AI_AGENT_PATH, token, {
    data: payload,
    baseUrl: BASE_URL_SSE,
    timeout: 120000, // SSE 需要较长超时
  });

  // 解析 SSE 响应
  const parsed = typeof result === "string" ? parseSseResponse(result) : result;

  // 检查是否有 task_id（异步任务）
  const taskId = parsed?.task_id || parsed?.taskId || result?.task_id || result?.taskId;

  if (taskId) {
    logger.info(`视频生成已提交为异步任务: task_id=${taskId}`);

    // 尝试立即查询一次任务状态
    const taskResult = await queryVideoTask(taskId, token);
    if (taskResult?.status === "completed" || taskResult?.status === "succeeded") {
      // 任务已完成，直接返回
      const videoUrl = extractVideoUrl(taskResult);
      if (videoUrl) {
        return {
          data: [{ url: videoUrl, revised_prompt: prompt }],
          created: util.unixTimestamp(),
        };
      }
    }

    // 任务未完成，返回 task_id 让轮询器处理
    throw new APIException(EX.API_REQUEST_FAILED,
      `视频生成已提交为异步任务 (id=${taskId})，请使用异步模式查询`);
  }

  // 如果直接返回了 URL
  const videoUrl = extractVideoUrl(parsed) || extractVideoUrl(result);
  if (videoUrl) {
    return {
      data: [{ url: videoUrl, revised_prompt: prompt }],
      created: util.unixTimestamp(),
    };
  }

  throw new APIException(EX.API_VIDEO_GENERATION_FAILED, "视频生成失败: 未能获取结果URL或任务ID");
}

/**
 * 查询视频异步任务结果
 * 真实抓包确认: GET /api/dam/ai/records?task_id=xxx
 */
export async function queryVideoTask(taskId: string, token: string): Promise<any> {
  try {
    const result = await request("get", `/api/dam/ai/records?task_id=${taskId}`, token);
    return result?.data || result;
  } catch (error: any) {
    logger.warn(`查询视频任务失败: ${error.message}`);
    return null;
  }
}
