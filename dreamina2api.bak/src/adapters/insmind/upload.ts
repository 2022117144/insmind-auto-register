/**
 * insMind 文件上传模块
 *
 * 真实抓包确认（2026-06-09）：
 * - 上传令牌: POST /api/tb-dam/asset/upload/tokens
 * - 上传到: insmind-gdesign-dam-static.xsbapp.com
 * - 编辑器保存: PUT /api/tb-dam/v2/editors/template/{content_id}
 */
import axios from "axios";
import logger from "@/lib/logger.ts";
import { request } from "./api.ts";
import {
  ImageUploadResult,
  FileUploadResult,
  VideoUploadResult,
} from "./types.ts";

// 显式重新导出类型，供桥接层使用
export type { ImageUploadResult, FileUploadResult, VideoUploadResult };

// ========== 图片上传 ==========

/**
 * 通过 insMind API 获取上传令牌，然后上传图片
 */
export async function uploadImageBuffer(
  imageBuffer: ArrayBuffer | Buffer,
  token: string,
  _regionInfo?: any
): Promise<ImageUploadResult> {
  try {
    const fileSize = imageBuffer.byteLength;
    logger.info(`uploadImageBuffer: 获取上传令牌 (size=${fileSize})`);

    const contentId = `${Date.now()}`;
    const uploadToken = await request("post", "/api/tb-dam/asset/upload/tokens", token, {
      data: {
        format: "png",
        content_id: contentId,
        dir: "",
        device_id: "",
        is_cname: false,
      },
    });

    const uploadUrl = uploadToken?.data?.upload_url || uploadToken?.upload_url;
    const cdnUrl = uploadToken?.data?.url || uploadToken?.url || uploadToken?.data?.cdn_url;
    if (!uploadUrl) {
      throw new Error("获取上传令牌失败: 无 upload_url");
    }

    logger.info(`uploadImageBuffer: 上传到 ${uploadUrl}`);
    await axios.put(uploadUrl, new Uint8Array(imageBuffer), {
      headers: { "Content-Type": "image/png" },
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
    });

    const resultUrl = cdnUrl || uploadUrl;
    if (!resultUrl) {
      throw new Error("上传完成但无法获取图片 URL");
    }

    const { width, height, format } = detectImageInfo(new Uint8Array(imageBuffer).buffer);

    return { uri: resultUrl, width, height, format };
  } catch (error: any) {
    logger.error(`uploadImageBuffer 失败: ${error.message}`);
    throw new Error(`图片上传失败: ${error.message}`);
  }
}

/**
 * 从 URL 上传图片（下载后再上传到 insMind CDN）
 */
export async function uploadImageFromUrl(
  imageUrl: string,
  token: string,
  regionInfo: any
): Promise<ImageUploadResult> {
  logger.info(`uploadImageFromUrl: 下载 ${imageUrl}`);
  const resp = await axios.get(imageUrl, {
    responseType: "arraybuffer",
    timeout: 30000,
  });
  const buffer = Buffer.from(resp.data);
  return uploadImageBuffer(buffer, token, regionInfo);
}

/**
 * 通用文件上传（保留向后兼容）
 */
export async function uploadFile(
  fileBuffer: ArrayBuffer | Buffer,
  token: string,
  fileName: string = "file"
): Promise<FileUploadResult> {
  try {
    const fileSize = fileBuffer.byteLength;
    logger.info(`uploadFile: 获取上传令牌 (size=${fileSize})`);

    const contentId = `${Date.now()}`;
    const uploadToken = await request("post", "/api/tb-dam/asset/upload/tokens", token, {
      data: {
        format: fileName.split(".").pop() || "png",
        content_id: contentId,
        dir: "",
        device_id: "",
        is_cname: false,
      },
    });

    const uploadUrl = uploadToken?.data?.upload_url || uploadToken?.upload_url;
    const cdnUrl = uploadToken?.data?.url || uploadToken?.url || uploadToken?.data?.cdn_url;
    if (!uploadUrl) {
      throw new Error("获取上传令牌失败: 无 upload_url");
    }

    logger.info(`uploadFile: 上传到 ${uploadUrl}`);
    await axios.put(uploadUrl, new Uint8Array(fileBuffer), {
      headers: { "Content-Type": "application/octet-stream" },
      maxBodyLength: Infinity,
      maxContentLength: Infinity,
    });

    return {
      url: cdnUrl || uploadUrl,
      uri: cdnUrl || uploadUrl,
    };
  } catch (error: any) {
    logger.error(`uploadFile 失败: ${error.message}`);
    throw new Error(`文件上传失败: ${error.message}`);
  }
}

// ========== 视频上传 ==========

/**
 * 上传视频 Buffer
 */
export async function uploadVideoBuffer(
  videoBuffer: ArrayBuffer,
  token: string,
  _regionInfo?: any
): Promise<VideoUploadResult> {
  try {
    const fileSize = videoBuffer.byteLength;
    logger.info(`uploadVideoBuffer: 获取上传令牌 (size=${fileSize})`);

    const uploadInfo = await request("post", "/api/v3/file/upload/apply", token, {
      data: {
        file_size: fileSize,
        file_name: "video.mp4",
        content_type: "video/mp4",
      },
    });

    const uploadUrl = uploadInfo?.data?.upload_url || uploadInfo?.upload_url;
    const cdnUrl = uploadInfo?.data?.cdn_url || uploadInfo?.cdn_url;

    if (uploadUrl) {
      logger.info(`uploadVideoBuffer: 上传到 ${uploadUrl}`);
      const formData = new FormData();
      const blob = new Blob([new Uint8Array(videoBuffer)]);
      formData.append("file", blob, "video.mp4");
      formData.append("file", blob, "video.mp4");

      await axios.post(uploadUrl, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        maxBodyLength: Infinity,
        maxContentLength: Infinity,
      });

      const resultUrl = cdnUrl || uploadUrl;
      if (resultUrl) {
        return {
          url: resultUrl,
          uri: resultUrl,
          videoMeta: { width: 0, height: 0, duration: 0, format: "mp4" },
        };
      }
    }

    // 回退: 通过 API 代理上传
    logger.info("uploadVideoBuffer: 回退到 API 代理上传");
    const apiFormData = new FormData();
    const apiBlob = new Blob([new Uint8Array(videoBuffer)]);
    apiFormData.append("file", apiBlob, "video.mp4");

    const result = await request("post", "/api/v3/file/upload", token, {
      data: apiFormData,
      headers: { "Content-Type": "multipart/form-data" },
    });

    const fileUrl = result?.data?.url || result?.data?.file_url || result?.url;
    if (fileUrl) {
      return {
        url: fileUrl,
        uri: fileUrl,
        videoMeta: { width: 0, height: 0, duration: 0, format: "mp4" },
      };
    }

    throw new Error("上传成功但无法获取视频 URL");
  } catch (error: any) {
    logger.error(`uploadVideoBuffer 失败: ${error.message}`);
    throw new Error(`视频上传失败: ${error.message}`);
  }
}

/**
 * 从 URL 上传视频
 */
export async function uploadVideoFromUrl(
  videoUrl: string,
  token: string,
  regionInfo: any
): Promise<VideoUploadResult> {
  logger.info(`uploadVideoFromUrl: 下载 ${videoUrl}`);
  const resp = await axios.get(videoUrl, {
    responseType: "arraybuffer",
    timeout: 120000,
  });
  const buffer = Buffer.from(resp.data);
  return uploadVideoBuffer(buffer.buffer.slice(buffer.byteOffset, buffer.byteOffset + buffer.byteLength), token, regionInfo);
}

// ========== 内部工具 ==========

/**
 * 简易图片信息探测（仅解析 PNG/JPEG 的宽高）
 */
export function detectImageInfo(buffer: ArrayBuffer): { width: number; height: number; format: string } {
  const view = new Uint8Array(buffer);

  // PNG
  if (view[0] === 0x89 && view[1] === 0x50 && view[2] === 0x4E && view[3] === 0x47) {
    const width = (view[16] << 24) | (view[17] << 16) | (view[18] << 8) | view[19];
    const height = (view[20] << 24) | (view[21] << 16) | (view[22] << 8) | view[23];
    return { width, height, format: "png" };
  }

  // JPEG
  if (view[0] === 0xFF && view[1] === 0xD8) {
    let offset = 2;
    while (offset < view.length) {
      if (view[offset] !== 0xFF) break;
      const marker = view[offset + 1];
      if (marker === 0xC0 || marker === 0xC1 || marker === 0xC2) {
        const height = (view[offset + 5] << 8) | view[offset + 6];
        const width = (view[offset + 7] << 8) | view[offset + 8];
        return { width, height, format: "jpeg" };
      }
      const segLen = (view[offset + 2] << 8) | view[offset + 3];
      offset += 2 + segLen;
    }
  }

  return { width: 0, height: 0, format: "unknown" };
}