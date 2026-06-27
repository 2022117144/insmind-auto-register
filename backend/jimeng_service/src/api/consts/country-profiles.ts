import {
  BASE_URL_CN,
  BASE_URL_US_COMMERCE,
  BASE_URL_HK_COMMERCE,
  DEFAULT_ASSISTANT_ID_CN,
  DEFAULT_ASSISTANT_ID_US,
  DEFAULT_ASSISTANT_ID_HK,
  DEFAULT_ASSISTANT_ID_JP,
  DEFAULT_ASSISTANT_ID_SG,
  DEFAULT_IMAGE_MODEL,
  DEFAULT_IMAGE_MODEL_US,
  DEFAULT_VIDEO_MODEL,
  DEFAULT_VIDEO_MODEL_ASIA,
  REGION_CN,
  REGION_US,
  REGION_HK,
  REGION_JP,
  REGION_SG,
  type ModelSetKey,
} from "@/api/consts/common.ts";
import { BASE_URL_DREAMINA_US, BASE_URL_DREAMINA_HK, BASE_URL_IMAGEX_US, BASE_URL_IMAGEX_HK } from "@/api/consts/dreamina.ts";

export type SiteFamily = "cn" | "international";

export interface CountryProfile {
  code: string;
  aliases?: string[];
  siteFamily: SiteFamily;
  regionParam: string;
  loc: string;
  lan: string;
  acceptLanguage: string;
  timeZone: string;
  requestBaseUrl: string;
  commerceBaseUrl: string;
  imagexUrl: string;
  webOrigin: string;
  imageGeneratePath: string;
  videoGeneratePath: string;
  homePath: string;
  awsRegion: string;
  assistantId: number;
  defaultServiceId: string;
  uploadTokenMode: "service_id" | "space_name";
  includeWebId: boolean;
  modelSet: ModelSetKey;
  defaultImageModel: string;
  defaultVideoModel: string;
  supportsImageSafetyCheck: boolean;
  supportsOmniReference: boolean;
  notes?: string;
}

const CN_WEB_ORIGIN = "https://jimeng.jianying.com";
const INTL_WEB_ORIGIN = "https://dreamina.capcut.com";
const CN_SERVICE_ID = "tb4s082cfz";
const INTL_SERVICE_ID = "wopfjsm1ax";

const CN_PROFILE: CountryProfile = {
  code: "cn",
  aliases: ["zh", "china", "mainland"],
  siteFamily: "cn",
  regionParam: REGION_CN,
  loc: "cn",
  lan: "zh-Hans",
  acceptLanguage: "zh-CN,zh;q=0.9",
  timeZone: "Asia/Shanghai",
  requestBaseUrl: BASE_URL_CN,
  commerceBaseUrl: BASE_URL_CN,
  imagexUrl: "https://imagex.bytedanceapi.com",
  webOrigin: CN_WEB_ORIGIN,
  imageGeneratePath: "/ai-tool/generate?type=image",
  videoGeneratePath: "/ai-tool/generate?type=video",
  homePath: "/ai-tool/home",
  awsRegion: "cn-north-1",
  assistantId: DEFAULT_ASSISTANT_ID_CN,
  defaultServiceId: CN_SERVICE_ID,
  uploadTokenMode: "service_id",
  includeWebId: true,
  modelSet: "cn",
  defaultImageModel: DEFAULT_IMAGE_MODEL,
  defaultVideoModel: DEFAULT_VIDEO_MODEL,
  supportsImageSafetyCheck: true,
  supportsOmniReference: true,
};

const US_PROFILE: CountryProfile = {
  code: "us",
  aliases: ["usa"],
  siteFamily: "international",
  regionParam: REGION_US,
  loc: "us",
  lan: "en",
  acceptLanguage: "en-US,en;q=0.9",
  timeZone: "America/New_York",
  requestBaseUrl: BASE_URL_DREAMINA_US,
  commerceBaseUrl: BASE_URL_US_COMMERCE,
  imagexUrl: BASE_URL_IMAGEX_US,
  webOrigin: INTL_WEB_ORIGIN,
  imageGeneratePath: "/ai-tool/generate?type=image",
  videoGeneratePath: "/ai-tool/generate?type=video",
  homePath: "/ai-tool/home",
  awsRegion: "us-east-1",
  assistantId: DEFAULT_ASSISTANT_ID_US,
  defaultServiceId: INTL_SERVICE_ID,
  uploadTokenMode: "space_name",
  includeWebId: false,
  modelSet: "us",
  defaultImageModel: DEFAULT_IMAGE_MODEL_US,
  defaultVideoModel: DEFAULT_VIDEO_MODEL,
  supportsImageSafetyCheck: false,
  supportsOmniReference: false,
};

const CA_PROFILE: CountryProfile = {
  ...US_PROFILE,
  code: "ca",
  aliases: ["canada"],
  regionParam: "CA",
  loc: "ca",
  lan: "en",
  acceptLanguage: "en-CA,en;q=0.9",
  timeZone: "America/Toronto",
  assistantId: DEFAULT_ASSISTANT_ID_US,
};

const GB_PROFILE: CountryProfile = {
  ...US_PROFILE,
  code: "gb",
  aliases: ["uk", "united kingdom", "great britain"],
  regionParam: "GB",
  loc: "gb",
  lan: "en",
  acceptLanguage: "en-GB,en;q=0.9",
  timeZone: "Europe/London",
  assistantId: DEFAULT_ASSISTANT_ID_US,
};

const DE_PROFILE: CountryProfile = {
  ...US_PROFILE,
  code: "de",
  aliases: ["germany", "deutschland"],
  regionParam: "DE",
  loc: "de",
  lan: "de",
  acceptLanguage: "de-DE,de;q=0.9,en;q=0.8",
  timeZone: "Europe/Berlin",
  assistantId: DEFAULT_ASSISTANT_ID_US,
};

const HK_PROFILE: CountryProfile = {
  code: "hk",
  aliases: ["hongkong"],
  siteFamily: "international",
  regionParam: REGION_HK,
  loc: "hk",
  lan: "en",
  acceptLanguage: "zh-HK,zh;q=0.9,en;q=0.8",
  timeZone: "Asia/Hong_Kong",
  requestBaseUrl: BASE_URL_DREAMINA_HK,
  commerceBaseUrl: BASE_URL_HK_COMMERCE,
  imagexUrl: BASE_URL_IMAGEX_HK,
  webOrigin: INTL_WEB_ORIGIN,
  imageGeneratePath: "/ai-tool/generate?type=image",
  videoGeneratePath: "/ai-tool/generate?type=video",
  homePath: "/ai-tool/home",
  awsRegion: "ap-singapore-1",
  assistantId: DEFAULT_ASSISTANT_ID_HK,
  defaultServiceId: INTL_SERVICE_ID,
  uploadTokenMode: "space_name",
  includeWebId: false,
  modelSet: "asia",
  defaultImageModel: DEFAULT_IMAGE_MODEL_US,
  defaultVideoModel: DEFAULT_VIDEO_MODEL,
  supportsImageSafetyCheck: false,
  supportsOmniReference: false,
};

const JP_PROFILE: CountryProfile = {
  ...HK_PROFILE,
  code: "jp",
  aliases: ["japan"],
  regionParam: REGION_JP,
  loc: "jp",
  lan: "ja",
  acceptLanguage: "ja-JP,ja;q=0.9,en;q=0.8",
  timeZone: "Asia/Tokyo",
  assistantId: DEFAULT_ASSISTANT_ID_JP,
};

const SG_PROFILE: CountryProfile = {
  ...HK_PROFILE,
  code: "sg",
  aliases: ["singapore"],
  regionParam: REGION_SG,
  loc: "sg",
  lan: "en",
  acceptLanguage: "en-SG,en;q=0.9,zh;q=0.8",
  timeZone: "Asia/Singapore",
  assistantId: DEFAULT_ASSISTANT_ID_SG,
};

const TW_PROFILE: CountryProfile = {
  ...SG_PROFILE,
  code: "tw",
  aliases: ["taiwan"],
  regionParam: "TW",
  loc: "TW",
  lan: "en",
  acceptLanguage: "en-US,en;q=0.9,zh-TW;q=0.8",
  timeZone: "Asia/Shanghai",
  assistantId: 513641,
  defaultVideoModel: DEFAULT_VIDEO_MODEL_ASIA,
  supportsOmniReference: true,
  notes: "Taiwan routes through the SG international cluster with TW region and TW loc values.",
};

const INTL_DEFAULT_PROFILE: CountryProfile = {
  ...SG_PROFILE,
  code: "intl-default",
  aliases: ["intl", "international", "global"],
  regionParam: REGION_SG,
  loc: "sg",
  lan: "en",
  acceptLanguage: "en-US,en;q=0.9",
  timeZone: "Asia/Singapore",
  assistantId: DEFAULT_ASSISTANT_ID_SG,
  notes: "Fallback profile for international countries without dedicated routing.",
};

export const COUNTRY_PROFILES: Record<string, CountryProfile> = {
  cn: CN_PROFILE,
  us: US_PROFILE,
  ca: CA_PROFILE,
  gb: GB_PROFILE,
  de: DE_PROFILE,
  hk: HK_PROFILE,
  jp: JP_PROFILE,
  sg: SG_PROFILE,
  tw: TW_PROFILE,
  "intl-default": INTL_DEFAULT_PROFILE,
};

const COUNTRY_ALIAS_INDEX = new Map<string, CountryProfile>();
for (const profile of Object.values(COUNTRY_PROFILES)) {
  COUNTRY_ALIAS_INDEX.set(profile.code.toLowerCase(), profile);
  for (const alias of profile.aliases || []) {
    COUNTRY_ALIAS_INDEX.set(alias.toLowerCase(), profile);
  }
}

export function getCountryProfile(code?: string | null): CountryProfile {
  if (!code) return COUNTRY_PROFILES.cn;
  const normalized = code.toLowerCase();
  return COUNTRY_ALIAS_INDEX.get(normalized) || COUNTRY_PROFILES[normalized] || COUNTRY_PROFILES["intl-default"];
}

export function isKnownCountryCode(code?: string | null): boolean {
  if (!code) return false;
  return COUNTRY_ALIAS_INDEX.has(code.toLowerCase()) || Boolean(COUNTRY_PROFILES[code.toLowerCase()]);
}

export function getGenerateReferer(profile: CountryProfile, type: "image" | "video"): string {
  const path = type === "image" ? profile.imageGeneratePath : profile.videoGeneratePath;
  return `${profile.webOrigin}${path}`;
}

export function getHomeReferer(profile: CountryProfile): string {
  return `${profile.webOrigin}${profile.homePath}`;
}
