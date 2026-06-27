import { RegionInfo } from "@/api/controllers/core.ts";

/**
 * 区域配置工具类
 * 统一管理不同区域的配置信息
 */
export class RegionUtils {
  /**
   * 获取ServiceId
   */
  static getServiceId(regionInfo: RegionInfo, providedServiceId?: string): string {
    if (providedServiceId) {
      return providedServiceId;
    }

    return regionInfo.profile.defaultServiceId;
  }

  /**
   * 获取ImageX URL
   */
  static getImageXUrl(regionInfo: RegionInfo): string {
    return regionInfo.profile.imagexUrl;
  }

  /**
   * 获取Origin
   */
  static getOrigin(regionInfo: RegionInfo): string {
    return regionInfo.profile.webOrigin;
  }

  /**
   * 获取AWS区域
   */
  static getAWSRegion(regionInfo: RegionInfo): string {
    return regionInfo.profile.awsRegion;
  }

  /**
   * 获取Referer路径
   */
  static getRefererPath(regionInfo: RegionInfo, path: string = '/ai-tool/generate'): string {
    const origin = this.getOrigin(regionInfo);
    return `${origin}${path}`;
  }
}
