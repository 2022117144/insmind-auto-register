/**
 * 视频上传 - 桥接到 insMind 适配层
 *
 * 所有 insMind 特定实现已迁移到 src/adapters/insmind/upload.ts
 */
export {
  type VideoUploadResult,
  uploadVideoBuffer,
  uploadVideoFromUrl,
} from "@/adapters/insmind/upload.ts";

