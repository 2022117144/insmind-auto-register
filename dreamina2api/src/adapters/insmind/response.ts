/**
 * insMind 图片/视频 URL 提取工具
 */
import logger from "@/lib/logger.ts";

/**
 * 从 API 响应项中提取单个图片 URL
 */
export function extractImageUrl(item: any, index?: number): string | null {
  const logPrefix = index !== undefined ? `图片 ${index + 1}` : "图片";

  // insMind 响应: result.data[0].url
  if (item?.result?.data?.[0]?.url) return item.result.data[0].url;

  if (item?.url) return item.url;
  if (item?.image_url) return item.image_url;
  if (item?.data?.url) return item.data.url;
  if (item?.image?.url) return item.image.url;

  logger.warn(`${logPrefix}: 无法提取URL, 结构: ${JSON.stringify(item).substring(0, 200)}`);
  return null;
}

/**
 * 批量提取图片 URLs
 */
export function extractImageUrls(itemList: any[]): string[] {
  return itemList
    .map((item, index) => extractImageUrl(item, index))
    .filter((url): url is string => url !== null);
}

/**
 * 从响应项中提取视频 URL
 */
export function extractVideoUrl(item: any): string | null {
  if (item?.result?.data?.[0]?.url) return item.result.data[0].url;

  if (item?.url) return item.url;
  if (item?.video_url) return item.video_url;
  if (item?.video?.url) return item.video.url;
  if (item?.data?.url) return item.data.url;

  return null;
}

/**
 * 获取高质量视频下载 URL
 */
export async function fetchHighQualityVideoUrl(url: string): Promise<string | null> {
  return url || null;
}