/**
 * 区域配置工具类
 * insMind 为单一平台，此类保留为无操作兼容层
 */

export class RegionUtils {
  static getServiceId(_regionInfo: any, _providedServiceId?: string): string {
    return "";
  }

  static getImageXUrl(_regionInfo: any): string {
    return "";
  }

  static getOrigin(_regionInfo: any): string {
    return "";
  }

  static getAWSRegion(_regionInfo: any): string {
    return "";
  }

  static getRefererPath(_regionInfo: any, _path: string = "/"): string {
    return _path;
  }
}
