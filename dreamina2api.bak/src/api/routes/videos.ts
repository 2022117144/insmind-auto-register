import _ from 'lodash';

import Request from '@/lib/request/Request.ts';
import { tokenSplit, parseRegionFromToken } from '@/api/controllers/core.ts';
import { generateVideo, DEFAULT_MODEL } from '@/api/controllers/videos.ts';
import util from '@/lib/util.ts';
import { createAsyncTask } from '@/lib/async-task-store.ts';

export default {
    prefix: '/v1/videos',

    post: {
        '/generations': async (request: Request) => {
            request
                .validate('body.model', v => _.isUndefined(v) || _.isString(v))
                .validate('body.prompt', _.isString)
                .validate('body.ratio', v => _.isUndefined(v) || _.isString(v))
                .validate('body.duration', v => _.isUndefined(v) || _.isFinite(v))
                .validate('body.image_url', v => _.isUndefined(v) || _.isString(v))
                .validate('body.async', v => _.isUndefined(v) || _.isBoolean(v) || _.isString(v))
                .validate('body.response_format', v => _.isUndefined(v) || _.isString(v))
                .validate('headers.authorization', _.isString);

            const tokens = tokenSplit(request.headers.authorization);
            const token = _.sample(tokens);
            const {
                model,
                prompt,
                ratio,
                duration,
                image_url,
                response_format,
            } = request.body;
            const finalModel = model || DEFAULT_MODEL;
            const responseFormat = _.defaultTo(response_format, "url");
            const asyncMode = _.toString(request.query.async || request.body.async || "").toLowerCase() === "true";
            const regionInfo = parseRegionFromToken(token);

            // 收集参考图
            const imageUrls: string[] = [];
            if (image_url) {
                imageUrls.push(image_url);
            }

            // 处理上传的文件
            if (request.files) {
                const uploadedFiles = request.files;
                for (const fieldName of Object.keys(uploadedFiles)) {
                    const file = uploadedFiles[fieldName];
                    if (file && file.filepath) {
                        // 文件已自动上传到临时目录，后续处理在 controller 中完成
                    }
                }
            }

            if (!asyncMode) {
                const result = await generateVideo(finalModel, prompt, {
                    ratio,
                    duration,
                    imageUrls,
                }, token, regionInfo);

                return {
                    created: result.created,
                    data: result.data,
                };
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
                responseFormat,
                historyId: taskId,
                endpoint: "/v1/videos/generations",
                model: finalModel,
                prompt,
                expectedItemCount: 1,
            });

            return {
                id: task.id,
                object: "task",
                kind: task.kind,
                status: task.status,
                created_at: task.createdAt,
                result: result,
            };
        }
    }
};
