/**
 * 图片/视频 URL 提取 - 桥接到 insMind 适配层
 *
 * 所有 insMind 特定实现已迁移到 src/adapters/insmind/response.ts
 */
export {
  extractImageUrl,
  extractImageUrls,
  extractVideoUrl,
  fetchHighQualityVideoUrl,
} from "@/adapters/insmind/response.ts";
