import logger from "@/lib/logger.ts";
import { STATUS_CODE_MAP, POLLING_CONFIG } from "@/api/consts/common.ts";

/**
 * 轮询状态接口
 */
export interface PollingStatus {
  status: number;
  failCode?: string;
  itemCount: number;
  finishTime?: number;
  historyId?: string;
}

export interface PollingOptions {
  maxPollCount?: number;
  pollInterval?: number;
  stableRounds?: number;
  timeoutSeconds?: number;
  expectedItemCount?: number;
  type?: 'image' | 'video';
}

export interface PollingResult {
  status: number;
  failCode?: string;
  itemCount: number;
  elapsedTime: number;
  pollCount: number;
  exitReason: string;
}

/**
 * 智能轮询器
 */
export class SmartPoller {
  private pollCount = 0;
  private startTime = Date.now();
  private lastItemCount = 0;
  private stableItemCountRounds = 0;
  private options: Required<PollingOptions>;
  
  constructor(options: PollingOptions = {}) {
    this.options = {
      maxPollCount: options.maxPollCount ?? POLLING_CONFIG.MAX_POLL_COUNT,
      pollInterval: options.pollInterval ?? POLLING_CONFIG.POLL_INTERVAL,
      stableRounds: options.stableRounds ?? POLLING_CONFIG.STABLE_ROUNDS,
      timeoutSeconds: options.timeoutSeconds ?? POLLING_CONFIG.TIMEOUT_SECONDS,
      expectedItemCount: options.expectedItemCount ?? 4,
      type: options.type ?? 'image'
    };
  }
  
  private getStatusName(status: number): string {
    return STATUS_CODE_MAP[status] || `UNKNOWN(${status})`;
  }

  private getSmartInterval(status: number, itemCount: number): number {
    const baseInterval = this.options.pollInterval;
    switch (status) {
      case 20: return baseInterval;
      case 42: return baseInterval * 1.2;
      case 45: return baseInterval * 1.5;
      case 50: return baseInterval * 0.5;
      case 10: return 0;
      case 30: return 0;
      default: return baseInterval;
    }
  }

  /**
   * 执行单次轮询
   */
  async poll(fetchFn: () => Promise<PollingStatus>): Promise<PollingResult> {
    const maxPollCount = this.options.maxPollCount;
    const timeoutMs = this.options.timeoutSeconds * 1000;
    const expectedCount = this.options.expectedItemCount;

    while (this.pollCount < maxPollCount) {
      const elapsedTime = Date.now() - this.startTime;
      if (elapsedTime > timeoutMs) {
        return {
          status: -1,
          itemCount: this.lastItemCount,
          elapsedTime: Math.floor(elapsedTime / 1000),
          pollCount: this.pollCount,
          exitReason: 'timeout'
        };
      }

      this.pollCount++;
      const status = await fetchFn();
      
      if (status.itemCount > this.lastItemCount) {
        this.stableItemCountRounds++;
      } else {
        this.stableItemCountRounds = 0;
      }
      this.lastItemCount = status.itemCount;

      logger.info(
        `轮询 [${this.pollCount}/${maxPollCount}]: status=${this.getStatusName(status.status)}(${status.status}), ` +
        `items=${status.itemCount}/${expectedCount}, elapsed=${Math.floor(elapsedTime / 1000)}s`
      );

      // 生成完成
      if (status.status === 10 || status.status === 50) {
        return {
          status: status.status,
          failCode: status.failCode,
          itemCount: status.itemCount,
          elapsedTime: Math.floor(elapsedTime / 1000),
          pollCount: this.pollCount,
          exitReason: 'completed'
        };
      }

      // 生成失败
      if (status.status === 30) {
        return {
          status: status.status,
          failCode: status.failCode,
          itemCount: status.itemCount,
          elapsedTime: Math.floor(elapsedTime / 1000),
          pollCount: this.pollCount,
          exitReason: 'failed'
        };
      }

      // 结果稳定且数量足够
      if (this.stableItemCountRounds >= this.options.stableRounds && status.itemCount >= expectedCount) {
        return {
          status: status.status,
          failCode: status.failCode,
          itemCount: status.itemCount,
          elapsedTime: Math.floor(elapsedTime / 1000),
          pollCount: this.pollCount,
          exitReason: 'stable'
        };
      }

      const interval = this.getSmartInterval(status.status, status.itemCount);
      if (interval > 0) {
        await new Promise(resolve => setTimeout(resolve, interval));
      }
    }

    return {
      status: -1,
      itemCount: this.lastItemCount,
      elapsedTime: Math.floor((Date.now() - this.startTime) / 1000),
      pollCount: this.pollCount,
      exitReason: 'max_polls_reached'
    };
  }
}
