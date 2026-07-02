/**
 * 图片上传 - 桥接到 insMind 适配层
 *
 * 所有 insMind 特定实现已迁移到 src/adapters/insmind/upload.ts
 */
export {
  type ImageUploadResult,
  type FileUploadResult,
  uploadImageBuffer,
  uploadFile,
  uploadImageFromUrl,
  detectImageInfo,
} from "@/adapters/insmind/upload.ts";
