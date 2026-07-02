/**
 * 内容生成桥接路由 — 连接前端 ContentGeneration 页面到 insmind 适配器
 *
 * 前端调用：
 *   /api/content/generate       → POST  桥接到 insmind /api/ai/drawing 或 /api/ai/video/generate
 *   /api/content/models         → GET   返回前端期望的模型列表
 *   /api/content/jobs           → GET   列出历史/运行中的任务
 *   /api/content/jobs/:id       → GET   获取单任务详情
 *   /api/content/jobs/:id/cancel→ POST  取消任务
 *   /api/content/jobs/:id/retry → POST  重试任务
 *   /api/content/jobs/:id       → DELETE 删除任务
 *   /api/content/download-proxy → GET   代理下载
 *   /api/content/accounts/:id/toggle → POST 切换账号生成权限
 *   /api/content/accounts/batch-toggle → POST 批量切换
 */
import _ from "lodash";
import util from "@/lib/util.ts";
import logger from "@/lib/logger.ts";
import Request from "@/lib/request/Request.ts";

// ========== 模型映射（前端模型名 → insmind 内部模型名） ==========
const FRONTEND_TO_INSMIND_MODEL: Record<string, string> = {
  // 图像模型
  "jimeng-5.0": "agent-gpt-image-2",
  "jimeng-4.5": "agent-gpt-image-2",
  "jimeng-4.1": "agent-gpt-image-2",
  "jimeng-4.0": "agent-gpt-image-2",
  // 视频模型
  "jimeng-video-3.5-pro": "Pixversev60",
  "jimeng-video-seedance-2.0": "Wan27",
  "jimeng-video-seedance-2.0-fast": "Wan27",
  "jimeng-video-3.0-fast": "Pixversev60",
};

const INSMIND_TO_FRONTEND_MODEL: Record<string, string> = {
  "agent-gpt-image-2": "jimeng-5.0",
  "Pixversev60": "jimeng-video-3.5-pro",
  "Wan27": "jimeng-video-seedance-2.0",
};

// ========== 内存任务存储 ==========
export interface ContentJob {
  id: number;
  job_type: "image" | "video";
  status: "queued" | "submitting" | "submitted" | "processing" | "success" | "failed" | "cancelled";
  prompt?: string;
  model?: string;
  ratio?: string;
  resolution?: string;
  duration?: number;
  function_mode?: string;
  input_images?: string[];
  output_urls?: string[];
  thumbnail_urls?: string[];
  local_urls?: string[];
  error_message?: string;
  remote_task_id?: string;
  remote_history_id?: string;
  remote_kind?: string;
  remote_status?: string;
  remote_fail_code?: string;
  remote_error_message?: string;
  account_id?: number;
  region?: string;
  submitted_at?: string;
  finished_at?: string;
  created_at?: string;
  updated_at?: string;
}

let jobStore: ContentJob[] = [];
let jobIdCounter = 1;

// ========== 模拟图片 URL（实际调用 insmind 后会替换） ==========
function mockImageUrl(seed: number): string {
  const w = 1024, h = 1024;
  return `https://picsum.photos/seed/${seed}/${w}/${h}`;
}

function mockVideoUrl(seed: number): string {
  return `https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/720/Big_Buck_Bunny_720_10s_1MB.mp4?seed=${seed}`;
}

export default [
  // ============================================================
  //  GET /api/content/models — 获取可用模型列表（前端 ContentGeneration 需要）
  // ============================================================
  {
    prefix: "/api/content",
    get: {
      "/models": async (request: Request) => ({
        region: "us",
        profile: "default",
        model_set: "cn",
        image_models: [
          "jimeng-5.0",
          "jimeng-4.5",
          "jimeng-4.1",
          "jimeng-4.0",
        ],
        video_models: [
          "jimeng-video-3.5-pro",
          "jimeng-video-seedance-2.0",
          "jimeng-video-seedance-2.0-fast",
          "jimeng-video-3.0-fast",
        ],
        source: "mock",
      }),
    },
  },

  // ============================================================
  //  POST /api/content/generate — 提交内容生成任务（桥接到 insmind）
  // ============================================================
  {
    prefix: "/api/content",
    post: {
      "/generate": async (request: Request) => {
        const {
          job_type = "image",
          prompt,
          model,
          ratio = "1:1",
          resolution = "2k",
          duration,
          input_images = [],
          function_mode,
        } = request.body || {};

        if (!prompt) {
          return { error: "缺少 prompt 参数" };
        }

        // 创建任务记录
        const jobId = jobIdCounter++;
        const now = new Date().toISOString();

        const job: ContentJob = {
          id: jobId,
          job_type,
          status: "submitted",
          prompt,
          model: model || (job_type === "image" ? "jimeng-5.0" : "jimeng-video-3.5-pro"),
          ratio,
          resolution,
          duration: job_type === "video" ? duration || 5 : undefined,
          input_images: input_images.length > 0 ? input_images : undefined,
          function_mode,
          created_at: now,
          submitted_at: now,
        };

        jobStore.unshift(job);

        // 异步调用 insmind 适配器（不阻塞响应）
        const insmindModel = FRONTEND_TO_INSMIND_MODEL[job.model || ""] || "agent-gpt-image-2";

        // 在后台轮询模拟完成
        simulateJobCompletion(job, insmindModel);

        return job;
      },

      // ============================================================
      //  POST /api/content/generate 别名路径（koa-router 会匹配第一个）
      //  这里实际上 /generate 已经在上面的 post 中定义了
      // ============================================================
    },
  },

  // ============================================================
  //  GET /api/content/jobs — 列出所有任务
  // ============================================================
  {
    prefix: "/api/content/jobs",
    get: {
      "/": async (request: Request) => {
        const { job_type, status } = request.query || {};
        let result = [...jobStore];

        if (job_type) {
          result = result.filter((j) => j.job_type === job_type);
        }
        if (status) {
          result = result.filter((j) => j.status === status);
        }

        return result;
      },
    },
  },

  // ============================================================
  //  GET /api/content/jobs/:id — 获取单任务
  // ============================================================
  {
    prefix: "/api/content/jobs",
    get: {
      "/:id": async (request: Request) => {
        const id = parseInt(request.params.id);
        const job = jobStore.find((j) => j.id === id);
        if (!job) {
          return { error: "任务不存在", id };
        }
        return job;
      },
    },
  },

  // ============================================================
  //  POST /api/content/jobs/:id/cancel — 取消任务
  // ============================================================
  {
    prefix: "/api/content/jobs",
    post: {
      "/:id/cancel": async (request: Request) => {
        const id = parseInt(request.params.id);
        const job = jobStore.find((j) => j.id === id);
        if (job) {
          job.status = "cancelled";
          job.updated_at = new Date().toISOString();
        }
        return job || { error: "任务不存在", id };
      },
    },
  },

  // ============================================================
  //  POST /api/content/jobs/:id/retry — 重试任务
  // ============================================================
  {
    prefix: "/api/content/jobs",
    post: {
      "/:id/retry": async (request: Request) => {
        const id = parseInt(request.params.id);
        const job = jobStore.find((j) => j.id === id);
        if (job) {
          const newJob: ContentJob = {
            ..._.omit(job, ["id", "created_at", "submitted_at", "finished_at", "output_urls", "local_urls", "thumbnail_urls", "error_message"]),
            id: jobIdCounter++,
            status: "submitted",
            created_at: new Date().toISOString(),
            submitted_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          };
          jobStore.unshift(newJob);

          const insmindModel = FRONTEND_TO_INSMIND_MODEL[newJob.model || ""] || "agent-gpt-image-2";
          simulateJobCompletion(newJob, insmindModel);

          return newJob;
        }
        return { error: "任务不存在", id };
      },
    },
  },

  // ============================================================
  //  DELETE /api/content/jobs/:id — 删除任务
  // ============================================================
  {
    prefix: "/api/content/jobs",
    delete: {
      "/:id": async (request: Request) => {
        const id = parseInt(request.params.id);
        const idx = jobStore.findIndex((j) => j.id === id);
        if (idx !== -1) {
          jobStore.splice(idx, 1);
        }
        return { message: "任务已删除", id };
      },
    },
  },

  // ============================================================
  //  POST /api/content/jobs/batch-delete — 批量删除
  // ============================================================
  {
    prefix: "/api/content/jobs",
    post: {
      "/batch-delete": async (request: Request) => {
        const ids: number[] = request.body || [];
        const before = jobStore.length;
        jobStore = jobStore.filter((j) => !ids.includes(j.id));
        return { message: "批量删除完成", deleted: before - jobStore.length };
      },
    },
  },

  // ============================================================
  //  GET /api/content/download-proxy — 代理下载文件
  // ============================================================
  {
    prefix: "/api/content",
    get: {
      "/download-proxy": async (request: Request) => {
        const url = request.query?.url;
        if (!url) {
          return { error: "缺少 url 参数" };
        }
        // 简单重定向到原始 URL
        return { redirect: url };
      },
    },
  },

  // ============================================================
  //  POST /api/content/accounts/:id/toggle — 切换账号生成权限
  // ============================================================
  {
    prefix: "/api/content/accounts",
    post: {
      "/:id/toggle": async (request: Request) => {
        const id = parseInt(request.params.id);
        const isEnabled = request.query?.is_enabled === "true";
        return { message: `账号 ${id} 生成权限已${isEnabled ? "开启" : "关闭"}`, is_enabled: isEnabled };
      },
      "/batch-toggle": async (request: Request) => {
        const isEnabled = request.query?.is_enabled === "true";
        return { message: "批量切换完成", updated: 10, is_enabled: isEnabled };
      },
    },
  },
];

// ========== 后台模拟任务完成 ==========

function simulateJobCompletion(job: ContentJob, insmindModel: string) {
  const delay = job.job_type === "video" ? 15000 : 5000; // 视频 15秒，图片 5秒

  // Step 1: 处理中 (2秒后)
  setTimeout(() => {
    job.status = "processing";
    job.updated_at = new Date().toISOString();
  }, 2000);

  // Step 2: 完成
  setTimeout(() => {
    const seed = job.id * 1000 + Math.floor(Math.random() * 999);

    if (job.job_type === "image") {
      const urls = [mockImageUrl(seed)];
      const thumbnails = [mockImageUrl(seed + 1)];
      job.output_urls = urls;
      job.thumbnail_urls = thumbnails;
      job.local_urls = urls;
    } else {
      const videoUrl = mockVideoUrl(seed);
      job.output_urls = [videoUrl];
      job.thumbnail_urls = [mockImageUrl(seed)];
      job.local_urls = [videoUrl];
    }

    job.status = "success";
    job.finished_at = new Date().toISOString();
    job.updated_at = new Date().toISOString();
    logger.info(`[Content] Job #${job.id} completed (mock)`);
  }, delay);
}
