/**
 * insMind SSE 响应解析 & 任务轮询
 *
 * insMind 使用 AI Agent SSE 端点提交生成任务:
 * - POST sse.insmind.com/api/ai-agent/v1/thread/completion → SSE stream
 * - 任务状态查询: GET /api/dam/ai/records?task_id=xxx
 * - 响应轮询: 使用 SmartPoller
 */
import APIException from "@/lib/exceptions/APIException.ts";
import EX from "@/api/consts/exceptions.ts";
import logger from "@/lib/logger.ts";
import util from "@/lib/util.ts";
import { request } from "./api.ts";
import { extractImageUrls, extractVideoUrl } from "./response.ts";
import { SseParseResult } from "./types.ts";
import { getAsyncTask, saveAsyncTask, AsyncTaskRecord } from "@/lib/async-task-store.ts";

// ========== SSE 解析 ==========

/**
 * 解析 AI Agent SSE 响应，提取 task_id
 */
export function parseSseResponse(sseData: string): SseParseResult {
  const result: SseParseResult = {};

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

// ========== 异步记录解析 ==========

function extractImagesFromRecord(record: any): string[] {
  const result = record?.result || record;
  const images = result?.images || result?.imgs || result?.data || [];
  return extractImageUrls(images);
}

function extractVideoFromRecord(record: any): string | null {
  const result = record?.result || record;
  return result?.video_url || result?.url || result?.video || null;
}

async function enrichImageTask(task: AsyncTaskRecord, record: any): Promise<AsyncTaskRecord> {
  const imageUrls = extractImagesFromRecord(record);

  return {
    ...task,
    status: "succeeded",
    remoteStatus: record.status,
    finishTime: record.finish_time || record.finished_at || 0,
    result: {
      created: util.unixTimestamp(),
      data: imageUrls.map((url: string) => ({ url })),
      itemCount: imageUrls.length,
      outputType: "image",
    },
    error: undefined,
  };
}

async function enrichVideoTask(task: AsyncTaskRecord, record: any): Promise<AsyncTaskRecord> {
  let videoUrl = extractVideoFromRecord(record);

  if (!videoUrl) {
    const items = record?.items || record?.item_list || [];
    for (const item of items) {
      videoUrl = extractVideoUrl(item);
      if (videoUrl) break;
    }
  }

  if (!videoUrl) {
    throw new APIException(EX.API_VIDEO_GENERATION_FAILED, "异步任务未能提取视频URL");
  }

  return {
    ...task,
    status: "succeeded",
    remoteStatus: record.status,
    finishTime: record.finish_time || record.finished_at || 0,
    result: {
      created: util.unixTimestamp(),
      data: [{ url: videoUrl, revised_prompt: task.prompt || "" }],
      itemCount: 1,
      outputType: "video",
    },
    error: undefined,
  };
}

/**
 * 刷新异步任务状态（从 insMind 查询最新结果）
 */
export async function refreshAsyncTask(taskId: string): Promise<AsyncTaskRecord | null> {
  const task = await getAsyncTask(taskId);
  if (!task) return null;
  if (task.status === "succeeded" || task.status === "failed") return task;

  let response: any;
  try {
    response = await request("get", `/api/dam/ai/records?task_id=${task.historyId}`, task.refreshToken);
  } catch (error: any) {
    logger.warn(`轮询异步任务失败: ${error.message}`);
    return { ...task, status: "processing" };
  }

  const record = response?.data || response;
  const status = record?.status || record?.state || "";
  const isCompleted = status === "completed" || status === "succeeded" || status === "done";
  const isFailed = status === "failed" || status === "error";

  const baseTask: AsyncTaskRecord = {
    ...task,
    status: isFailed ? "failed" : (isCompleted ? "succeeded" : "processing"),
    remoteStatus: status,
    finishTime: record?.finish_time || record?.finished_at || 0,
    failCode: record?.fail_code || record?.error_code || record?.error,
  };

  if (baseTask.status === "succeeded") {
    return task.kind === "video_generation"
      ? await enrichVideoTask(baseTask, record)
      : await enrichImageTask(baseTask, record);
  }

  if (baseTask.status === "failed") {
    baseTask.error = {
      message: `生成失败: ${baseTask.failCode || "未知错误"}`,
      failCode: baseTask.failCode,
    };
  }

  return baseTask;
}