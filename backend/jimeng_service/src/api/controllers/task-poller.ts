import APIException from "@/lib/exceptions/APIException.ts";
import EX from "@/api/consts/exceptions.ts";
import logger from "@/lib/logger.ts";
import util from "@/lib/util.ts";
import { request } from "@/api/controllers/core.ts";
import { extractImageUrls, extractVideoUrl, fetchHighQualityVideoUrl } from "@/lib/image-utils.ts";
import { getAsyncTask, saveAsyncTask, AsyncTaskRecord } from "@/lib/async-task-store.ts";

async function enrichImageTask(task: AsyncTaskRecord, historyData: any): Promise<AsyncTaskRecord> {
  const itemList = historyData.item_list || [];
  const imageUrls = extractImageUrls(itemList);

  return {
    ...task,
    status: "succeeded",
    remoteStatus: historyData.status,
    finishTime: historyData.task?.finish_time || 0,
    result: {
      created: util.unixTimestamp(),
      data: imageUrls.map((url) => ({ url })),
      itemCount: imageUrls.length,
      outputType: "image",
    },
    error: undefined,
  };
}

async function enrichVideoTask(task: AsyncTaskRecord, historyData: any): Promise<AsyncTaskRecord> {
  const itemList = historyData.item_list || [];
  const itemId = itemList?.[0]?.item_id
    || itemList?.[0]?.id
    || itemList?.[0]?.local_item_id
    || itemList?.[0]?.common_attr?.id;

  let videoUrl = null;
  if (itemId) {
    try {
      videoUrl = await fetchHighQualityVideoUrl(String(itemId), task.refreshToken);
    } catch (error: any) {
      logger.warn(`异步任务获取高质量视频URL失败，回退预览URL: ${error.message}`);
    }
  }
  if (!videoUrl && itemList[0]) {
    videoUrl = extractVideoUrl(itemList[0]);
  }

  if (!videoUrl) {
    throw new APIException(EX.API_VIDEO_GENERATION_FAILED, "异步任务未能提取视频URL");
  }

  return {
    ...task,
    status: "succeeded",
    remoteStatus: historyData.status,
    finishTime: historyData.task?.finish_time || 0,
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

  const response = await request("post", "/mweb/v1/get_history_by_ids", task.refreshToken, {
    data: {
      history_ids: [task.historyId],
    },
  });

  const historyData = response[task.historyId] || response[Object.keys(response)[0]];
  if (!historyData) {
    return task;
  }

  const baseTask: AsyncTaskRecord = {
    ...task,
    status: historyData.status === 30 ? "failed" : (historyData.status === 10 || historyData.status === 50 ? "succeeded" : "processing"),
    remoteStatus: historyData.status,
    finishTime: historyData.task?.finish_time || 0,
    failCode: historyData.fail_code,
  };

  let nextTask = baseTask;
  if (baseTask.status === "succeeded") {
    nextTask = task.kind === "video_generation"
      ? await enrichVideoTask(baseTask, historyData)
      : await enrichImageTask(baseTask, historyData);
  } else if (baseTask.status === "failed") {
    nextTask = {
      ...baseTask,
      error: {
        message: `${task.kind === "video_generation" ? "视频" : "图片"}生成失败`,
        failCode: historyData.fail_code,
        details: {
          status: historyData.status,
          fail_code: historyData.fail_code,
          task: historyData.task,
        },
      },
    };
  }

  await saveAsyncTask(nextTask);
  return nextTask;
}
