/**
 * insMind 区域/站点配置
 *
 * insMind 为单一平台（海外版稿定设计），没有多地区差异。
 * 保留此模块以兼容原有的多地区路由架构。
 */
import {
  BASE_URL_INSMIND,
  BASE_URL_SSE,
  DEFAULT_IMAGE_MODEL,
  DEFAULT_VIDEO_MODEL,
} from "./constants.ts";
import { CountryProfile, ModelSetKey, SiteFamily } from "./types.ts";

export { CountryProfile, SiteFamily };

const INSMIND_WEB_ORIGIN = "https://www.insmind.com";

const INSMIND_PROFILE: CountryProfile = {
  code: "insmind",
  siteFamily: "insmind",
  requestBaseUrl: BASE_URL_INSMIND,
  sseBaseUrl: BASE_URL_SSE,
  webOrigin: INSMIND_WEB_ORIGIN,
  imageGeneratePath: "/ai-image-generator",
  videoGeneratePath: "/ai-video-generator",
  homePath: "/",
  assistantId: 0,
  modelSet: "cn",
  defaultImageModel: DEFAULT_IMAGE_MODEL,
  defaultVideoModel: DEFAULT_VIDEO_MODEL,
  supportsImageSafetyCheck: false,
  supportsOmniReference: false,
};

const PROFILES: CountryProfile[] = [INSMIND_PROFILE];

function getProfileByCode(code: string): CountryProfile | undefined {
  return PROFILES.find(p => p.code === code);
}

export function getCountryProfile(code: string): CountryProfile {
  return getProfileByCode(code) || INSMIND_PROFILE;
}

export function getHomeReferer(profile: CountryProfile): string {
  return `${profile.webOrigin}${profile.homePath}`;
}

export function getGenerateReferer(profile: CountryProfile, type: "image" | "video"): string {
  return `${profile.webOrigin}${type === "image" ? profile.imageGeneratePath : profile.videoGeneratePath}`;
}

export function parseCountryCode(code: string): string {
  return code || "insmind";
}