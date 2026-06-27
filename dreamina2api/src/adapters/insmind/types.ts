/**
 * insMind API 类型定义
 *
 * insMind = 稿定设计海外版 (gaoding.com)
 * 底层调用即梦(Dreamina)和千问(Qwen)的API
 */

// ========== 认证相关 ==========

export interface TokenInfo {
  rawToken: string;
  accessToken: string;   // Bearer token (OAuth2 access_token)
  refreshToken?: string; // OAuth2 refresh_token (可选)
}

export interface TokenWithProxy {
  token: string;
  proxyUrl: string | null;
}

// ========== 区域/平台信息 ==========

export type SiteFamily = "insmind";

export interface CountryProfile {
  code: string;
  siteFamily: SiteFamily;
  requestBaseUrl: string;
  sseBaseUrl?: string;
  webOrigin: string;
  imageGeneratePath: string;
  videoGeneratePath: string;
  homePath: string;
  assistantId: number;
  modelSet: ModelSetKey;
  defaultImageModel: string;
  defaultVideoModel: string;
  supportsImageSafetyCheck: boolean;
  supportsOmniReference: boolean;
}

export interface RegionInfo {
  countryCode: string;
  profile: CountryProfile;
  isInternational: boolean;
  isCN: boolean;
}

// ========== 模型 ==========

export type ModelSetKey = "cn" | "us" | "asia";

export interface ModelResult {
  model: string;
  userModel: string;
}

// ========== 上传 ==========

export interface ImageUploadResult {
  uri: string;
  width: number;
  height: number;
  format: string;
}

export interface FileUploadResult {
  url: string;
  uri: string;
  width?: number;
  height?: number;
}

export interface VideoUploadResult {
  url: string;
  uri: string;
  width?: number;
  height?: number;
  videoMeta?: {
    width: number;
    height: number;
    duration: number;
    format: string;
  };
}

// ========== 积分/VIP ==========

export interface CreditInfo {
  totalCredit: number;
  usedCredit: number;
  availableCredit: number;
}

export interface VipInfo {
  isVip: boolean;
  level: string;
  expireTime: number;
}

// ========== 错误处理选项 ==========

export interface ErrorHandlerOptions {
  context?: string;
}

// ========== API 错误响应 ==========

export interface InsMindErrorResponse {
  ret?: string;
  code?: number | string;
  errmsg?: string;
  message?: string;
  data?: any;
}

// ========== 文件令牌 ==========

export interface FileAccessToken {
  accessToken: string;
  expireTime: number;
}

// ========== SSE 解析 ==========

export interface SseParseResult {
  taskId?: string;
  threadId?: string;
  content?: string;
}

// ========== 分辨率 ==========

export interface ResolutionResult {
  width: number;
  height: number;
  imageRatio: number;
  resolutionType: string;
  isForced: boolean;
}

// ========== AI Agent Payload ==========

export interface AiAgentPayloadParams {
  prompt: string;
  sceneCode: string;
  imageUrls?: string[];
  parameters?: Record<string, any>;
  threadId?: string;
  localMessageId?: string;
  inputSkillId?: string;
  extra?: Record<string, any>;
}

// ========== 图片生成参数 (Builder) ==========

export interface ImageGenerationParams {
  prompt: string;
  model: string;
  negativePrompt?: string;
  width: number;
  height: number;
  seed?: number;
  guidanceScale?: number;
  imageCount?: number;
  imageUrls?: string[];
}

// ========== 视频生成参数 (Builder) ==========

export interface VideoGenerationParams {
  prompt: string;
  model: string;
  imageUrls?: string[];
  videoUrls?: string[];
  duration?: number;
  resolution?: string;
  ratio?: string;
}

// ========== 轮询类型 ==========

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
