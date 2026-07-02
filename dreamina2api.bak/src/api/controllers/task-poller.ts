import APIException from "@/lib/exceptions/APIException.ts";
import EX from "@/api/consts/exceptions.ts";
import logger from "@/lib/logger.ts";
import util from "@/lib/util.ts";
import { request } from "@/api/controllers/core.ts";
import { extractImageUrls, extractVideoUrl } from "@/lib/image-utils.ts";
import { getAsyncTask, saveAsyncTask, AsyncTaskRecord } from "@/lib/async-task-store.ts";

/**
 * 解析 AI 记录数据中的图片 URL
 * insMind 的 /api/dam/ai/records 返回格式：
 * {
 *   "id": "...",
 *   "status": "completed" | "processing" | "failed",
 *   "result": { "images": [...], "video_url": "..." },
 *   "task_id": "..."
 * }
 */
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
      data: imageUrls.map((url) => ({ url })),
      itemCount: imageUrls.length,
      outputType: "image",
    },
    error: undefined,
  };
}

async function enrichVideoTask(task: AsyncTaskRecord, record: any): Promise<AsyncTaskRecord> {
  let videoUrl = extractVideoFromRecord(record);

  // 如果 record 中没有，从 items 中提取
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

export async function refreshAsyncTask(taskId: string): Promise<AsyncTaskRecord | null> {
  const task = await getAsyncTask(taskId);
  if (!task) return null;
  if (task.status === "succeeded" || task.status === "failed") return task;

  let response: any;
  try {
    // insMind 使用 /api/dam/ai/records 查询任务状态
    response = await request("get", `/api/dam/ai/records?task_id=${task.historyId}`, task.refreshToken);
  } catch (error: any) {
    logger.warn(`轮询异步任务失败: ${error.message}`);
    return { ...task, status: "processing" };
  }

  const record = response?.data || response;

  // 判断状态
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
