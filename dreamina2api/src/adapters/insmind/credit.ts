/**
 * insMind 积分/Credit 查询模块
 *
 * 真实抓包确认:
 * - 权益查询: GET /api/trade/rights-overview?goodsTypeEnums=GAODOU
 * - VIP 查询: GET /api/mns/current/vips
 */
import logger from "@/lib/logger.ts";
import { request } from "./api.ts";
import { CreditInfo, VipInfo, FileAccessToken } from "./types.ts";

/**
 * 查询用户积分（点数）
 */
export async function getCredit(token: string): Promise<CreditInfo> {
  try {
    const result = await request("get", "/api/trade/rights-overview?goodsTypeEnums=GAODOU", token);
    return {
      totalCredit: result?.data?.total || result?.total || 0,
      usedCredit: result?.data?.used || result?.used || 0,
      availableCredit: result?.data?.available || result?.available || 0,
    };
  } catch (error: any) {
    logger.warn(`查询积分失败: ${error.message}`);
    return { totalCredit: 0, usedCredit: 0, availableCredit: 0 };
  }
}

/**
 * 查询 VIP 状态
 */
export async function getVipStatus(token: string): Promise<VipInfo | null> {
  try {
    const result = await request("get", "/api/mns/current/vips", token);
    const data = result?.data || result;
    if (data && data.vip) {
      return {
        isVip: true,
        level: data.level || data.vip_level || "",
        expireTime: data.expire_time || data.expireTime || 0,
      };
    }
    return { isVip: false, level: "", expireTime: 0 };
  } catch {
    return null;
  }
}

/**
 * 领取每日积分（insMind 暂未发现签到接口）
 */
export async function receiveCredit(_token: string): Promise<boolean> {
  return false;
}

/**
 * Token 有效性检测
 */
export async function getTokenLiveStatus(token: string): Promise<boolean> {
  try {
    const result = await request("get", "/api/mns/current/vips", token);
    return result !== null && result !== undefined;
  } catch {
    return false;
  }
}

/**
 * 获取文件系统访问 Token
 */
export async function getFileAccessToken(token: string): Promise<FileAccessToken | null> {
  try {
    const result = await request("get", "/api/filems/access/token", token);
    const data = result?.data || result;
    if (data?.access_token || data?.accessToken) {
      return {
        accessToken: data.access_token || data.accessToken,
        expireTime: data.expire_time || data.expireTime || 0,
      };
    }
    return null;
  } catch {
    return null;
  }
}