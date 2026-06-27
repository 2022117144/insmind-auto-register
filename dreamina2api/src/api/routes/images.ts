import _ from "lodash";

import Request from "@/lib/request/Request.ts";
import { generateImages, generateImageComposition, getModel as getImageModel } from "@/api/controllers/images.ts";
import { DEFAULT_IMAGE_MODEL } from "@/api/consts/common.ts";
import { tokenSplit, parseRegionFromToken } from "@/api/controllers/core.ts";
import util from "@/lib/util.ts";
import { createAsyncTask } from "@/lib/async-task-store.ts";

export default {
  prefix: "/v1/images",

  post: {
    "/generations": async (request: Request) => {
      request
        .validate("body.model", v => _.isUndefined(v) || _.isString(v))
        .validate("body.prompt", _.isString)
        .validate("body.negative_prompt", v => _.isUndefined(v) || _.isString(v))
        .validate("body.ratio", v => _.isUndefined(v) || _.isString(v))
        .validate("body.resolution", v => _.isUndefined(v) || _.isString(v))
        .validate("body.n", v => _.isUndefined(v) || _.isFinite(v))
        .validate("body.async", v => _.isUndefined(v) || _.isBoolean(v) || _.isString(v))
        .validate("body.seed", v => _.isUndefined(v) || _.isFinite(v))
        .validate("body.response_format", v => _.isUndefined(v) || _.isString(v))
        .validate("headers.authorization", _.isString);

      const tokens = tokenSplit(request.headers.authorization);
      const token = _.sample(tokens);
      const {
        model,
        prompt,
        negative_prompt: negativePrompt,
        ratio,
        resolution,
        n,
        seed,
        response_format,
      } = request.body;
      const finalModel = _.defaultTo(model, DEFAULT_IMAGE_MODEL);
      const responseFormat = _.defaultTo(response_format, "url");
      const asyncMode = _.toString(request.query.async || request.body.async || "").toLowerCase() === "true";

      const regionInfo = parseRegionFromToken(token);
      const { model: mappedModel, userModel } = getImageModel(finalModel, regionInfo);

      // 同步模式
      if (!asyncMode) {
        const result = await generateImages(mappedModel, prompt, {
          negativePrompt,
          ratio,
          resolution,
          seed,
          imageCount: n || 1,
        }, token, regionInfo);

        return {
          created: result.created,
          data: result.data.map(item => ({
            url: item.url,
            revised_prompt: item.revised_prompt,
          })),
        };
      }

      // 异步模式
      const componentId = util.uuid();
      const submitId = util.uuid();
      const taskId = util.uuid(false);

      // 对于异步模式，先提交任务
      const result = await generateImages(mappedModel, prompt, {
        negativePrompt,
        ratio,
        resolution,
        seed,
        imageCount: n || 1,
      }, token, regionInfo);

      // 创建异步任务记录
      const historyId = componentId;
      const task = await createAsyncTask({
        id: taskId,
        kind: "image_generation",
        refreshToken: token,
        responseFormat,
        historyId,
        endpoint: "/v1/images/generations",
        model: finalModel,
        prompt,
        expectedItemCount: n || 1,
      });

      return {
        id: task.id,
        object: "task",
        kind: task.kind,
        status: task.status,
        created_at: task.createdAt,
        result: result,
      };
    },

    "/compositions": async (request: Request) => {
      request
        .validate("body.model", v => _.isUndefined(v) || _.isString(v))
        .validate("body.prompt", _.isString)
        .validate("body.image_url", v => _.isUndefined(v) || _.isString(v))
        .validate("body.ratio", v => _.isUndefined(v) || _.isString(v))
        .validate("body.resolution", v => _.isUndefined(v) || _.isString(v))
        .validate("body.sample_strength", v => _.isUndefined(v) || _.isFinite(v))
        .validate("body.response_format", v => _.isUndefined(v) || _.isString(v))
        .validate("headers.authorization", _.isString);

      const tokens = tokenSplit(request.headers.authorization);
      const token = _.sample(tokens);
      const {
        model,
        prompt,
        image_url,
        image_file,
        ratio,
        resolution,
        sample_strength,
        negative_prompt,
        response_format,
      } = request.body;
      const finalModel = _.defaultTo(model, DEFAULT_IMAGE_MODEL);
      const regionInfo = parseRegionFromToken(token);
      const { model: mappedModel, userModel } = getImageModel(finalModel, regionInfo);

      // 收集图片
      const images: (string | Buffer)[] = [];
      if (image_url) {
        images.push(image_url);
      }
      const files: any = request.files || {};
      if (files.image_file) {
        const file = files.image_file;
        if (file.filepath) {
          const fs = await import("fs-extra");
          const buffer = await fs.readFile(file.filepath);
          images.push(buffer);
        }
      }

      const result = await generateImageComposition(mappedModel, prompt, images, {
        ratio,
        resolution,
        sampleStrength: sample_strength,
        negativePrompt: negative_prompt,
      }, token, regionInfo);

      return {
        created: result.created,
        data: result.data.map(item => ({
          url: item.url,
          revised_prompt: prompt,
        })),
      };
    },
  },
};
