/**
 * insMind 风格 API 路由
 *
 * 提供 insMind 前端调用的接口风格：
 *   POST /api/ai/drawing        → AI 绘图（文生图/图生图）
 *   POST /api/ai/video/generate → AI 视频生成
 *   GET  /api/models            → 获取可用模型列表
 *   POST /api/tasks/:id/refresh → 刷新异步任务状态
 *   GET  /api/health            → 健康检查
 *
 * 底层复用现有的即梦 API 控制器（images.ts / videos.ts），
 * 但输入/输出格式适配为 insMind 风格。
 */
import _ from "lodash";
import util from "@/lib/util.ts";
import logger from "@/lib/logger.ts";

import Request from "@/lib/request/Request.ts";
import { tokenSplit, parseRegionFromToken } from "@/api/controllers/core.ts";
import { generateImages, generateImageComposition, getModel as getImageModel } from "@/api/controllers/images.ts";
import { generateVideo, DEFAULT_MODEL as DEFAULT_VIDEO } from "@/api/controllers/videos.ts";
import { DEFAULT_IMAGE_MODEL, DEFAULT_VIDEO_MODEL } from "@/api/consts/common.ts";
import { createAsyncTask, getAsyncTask, saveAsyncTask } from "@/lib/async-task-store.ts";
import { refreshAsyncTask } from "@/api/controllers/task-poller.ts";

import { success, badRequest, notFound, unauthorized } from "./insmind-response.ts";
import { getInsMindModelList } from "./insmind-models.ts";

export default [
  // ============================================================
  //  POST /api/ai/drawing — AI 绘图（文生图/图生图）
  // ============================================================
  {
    prefix: "/api/ai",
    post: {
      "/drawing": async (request: Request) => {
        // --- 参数校验 ---
        request
          .validate("body.prompt", (v: any) => _.isString(v) && v.length > 0)
          .validate("body.model", (v: any) => _.isUndefined(v) || _.isString(v))
          .validate("body.image_url", (v: any) => _.isUndefined(v) || _.isString(v))
          .validate("body.ratio", (v: any) => _.isUndefined(v) || _.isString(v))
          .validate("body.resolution", (v: any) => _.isUndefined(v) || _.isString(v))
          .validate("body.negative_prompt", (v: any) => _.isUndefined(v) || _.isString(v))
          .validate("body.n", (v: any) => _.isUndefined(v) || _.isFinite(v))
          .validate("body.seed", (v: any) => _.isUndefined(v) || _.isFinite(v))
          .validate("body.async", (v: any) => _.isUndefined(v) || _.isBoolean(v) || _.isString(v))
          .validate("headers.authorization", _.isString);

        const tokens = tokenSplit(request.headers.authorization);
        const token = _.sample(tokens);
        const regionInfo = parseRegionFromToken(token);

        const {
          model,
          prompt,
          image_url,
          ratio,
          resolution,
          negative_prompt: negativePrompt,
          n,
          seed,
        } = request.body;

        const finalModel = model || DEFAULT_IMAGE_MODEL;
        const { model: mappedModel } = getImageModel(finalModel, regionInfo);
        const asyncMode = _.toString(request.query.async || request.body.async || "").toLowerCase() === "true";

        // --- 判断是文生图还是图生图 ---
        const isComposition = !!image_url;

        if (!asyncMode) {
          // 同步模式
          let result;
          if (isComposition) {
            result = await generateImageComposition(mappedModel, prompt, [image_url], {
              ratio,
              resolution,
              negativePrompt,
            }, token, regionInfo);
          } else {
            result = await generateImages(mappedModel, prompt, {
              negativePrompt,
              ratio,
              resolution,
              seed,
              imageCount: n || 1,
            }, token, regionInfo);
          }

          return success({
            object: "list",
            kind: "image",
            created: result.created,
            data: result.data.map((item: any) => ({
              url: item.url,
              revised_prompt: item.revised_prompt || prompt,
            })),
          });
        }

        // 异步模式
        const taskId = util.uuid(false);

        let result;
        if (isComposition) {
          result = await generateImageComposition(mappedModel, prompt, [image_url], {
            ratio,
            resolution,
            negativePrompt,
          }, token, regionInfo);
        } else {
          result = await generateImages(mappedModel, prompt, {
            negativePrompt,
            ratio,
            resolution,
            seed,
            imageCount: n || 1,
          }, token, regionInfo);
        }

        const task = await createAsyncTask({
          id: taskId,
          kind: "image_generation",
          refreshToken: token,
          responseFormat: "url",
          historyId: taskId,
          endpoint: "/api/ai/drawing",
          model: finalModel,
          prompt,
          expectedItemCount: n || 1,
        });

        return success({
          id: task.id,
          object: "task",
          kind: task.kind,
          status: task.status,
          created_at: task.createdAt,
          result: result,
        });
      },
    },
  },

  // ============================================================
  //  POST /api/ai/video/generate — AI 视频生成
  // ============================================================
  {
    prefix: "/api/ai/video",
    post: {
      "/generate": async (request: Request) => {
        request
          .validate("body.prompt", (v: any) => _.isString(v) && v.length > 0)
          .validate("body.model", (v: any) => _.isUndefined(v) || _.isString(v))
          .validate("body.image_url", (v: any) => _.isUndefined(v) || _.isString(v))
          .validate("body.ratio", (v: any) => _.isUndefined(v) || _.isString(v))
          .validate("body.duration", (v: any) => _.isUndefined(v) || _.isFinite(v))
          .validate("body.async", (v: any) => _.isUndefined(v) || _.isBoolean(v) || _.isString(v))
          .validate("headers.authorization", _.isString);

        const tokens = tokenSplit(request.headers.authorization);
        const token = _.sample(tokens);
        const regionInfo = parseRegionFromToken(token);

        const {
          model,
          prompt,
          image_url,
          ratio,
          duration,
        } = request.body;

        const finalModel = model || DEFAULT_VIDEO_MODEL;
        const asyncMode = _.toString(request.query.async || request.body.async || "").toLowerCase() === "true";

        const imageUrls: string[] = [];
        if (image_url) {
          imageUrls.push(image_url);
        }

        if (!asyncMode) {
          const result = await generateVideo(finalModel, prompt, {
            ratio,
            duration,
            imageUrls,
          }, token, regionInfo);

          return success({
            object: "list",
            kind: "video",
            created: result.created,
            data: result.data,
          });
        }

        // 异步模式
        const taskId = util.uuid(false);

        const result = await generateVideo(finalModel, prompt, {
          ratio,
          duration,
          imageUrls,
        }, token, regionInfo);

        const task = await createAsyncTask({
          id: taskId,
          kind: "video_generation",
          refreshToken: token,
          responseFormat: "url",
          historyId: taskId,
          endpoint: "/api/ai/video/generate",
          model: finalModel,
          prompt,
          expectedItemCount: 1,
        });

        return success({
          id: task.id,
          object: "task",
          kind: task.kind,
          status: task.status,
          created_at: task.createdAt,
          result: result,
        });
      },
    },
  },

  // ============================================================
  //  GET /api/models — 获取可用模型列表
  // ============================================================
  {
    prefix: "/api",
    get: {
      "/models": async (_request: Request) => {
        const models = getInsMindModelList();
        return success({
          object: "list",
          data: models,
        });
      },
    },
  },

  // ============================================================
  //  POST /api/tasks/:id/refresh — 刷新异步任务状态
  // ============================================================
  {
    prefix: "/api/tasks",
    post: {
      "/:id/refresh": async (request: Request) => {
        const taskId = request.params.id;
        if (!taskId) {
          return badRequest("缺少任务 ID");
        }

        const refreshed = await refreshAsyncTask(taskId);
        const task = refreshed || (await getAsyncTask(taskId));
        if (!task) {
          return notFound(`异步任务不存在: ${taskId}`);
        }

        return success({
          id: task.id,
          object: "task",
          kind: task.kind,
          status: task.status,
          created_at: task.createdAt,
          updated_at: task.updatedAt,
          result: task.result || null,
          error: task.error || null,
        });
      },
    },
  },

  // ============================================================
  //  GET /api/tasks/:id — 查询异步任务状态
  // ============================================================
  {
    prefix: "/api/tasks",
    get: {
      "/:id": async (request: Request) => {
        const taskId = request.params.id;
        if (!taskId) {
          return badRequest("缺少任务 ID");
        }

        const refreshed = await refreshAsyncTask(taskId);
        const task = refreshed || (await getAsyncTask(taskId));
        if (!task) {
          return notFound(`异步任务不存在: ${taskId}`);
        }

        return success({
          id: task.id,
          object: "task",
          kind: task.kind,
          status: task.status,
          created_at: task.createdAt,
          updated_at: task.updatedAt,
          result: task.result || null,
          error: task.error || null,
        });
      },
    },
  },
];
