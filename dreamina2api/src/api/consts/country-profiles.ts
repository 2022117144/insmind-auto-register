/**
 * 地区站点配置 - 桥接到 insMind 适配层
 *
 * insMind 为单一平台，所有多地区配置已迁移到 src/adapters/insmind/region.ts
 */
export {
  type CountryProfile,
  type SiteFamily,
  getCountryProfile,
  getHomeReferer,
  getGenerateReferer,
  parseCountryCode,
} from "@/adapters/insmind/region.ts";
