# dreamina2api → insMind 改造方案报告

## 一、dreamina2api 项目架构分析

### 1.1 项目概览

**项目名称**: jimeng-api  
**描述**: 基于即梦AI（字节跳动/Dreamina）逆向工程的免费AI图像和视频生成API服务  
**技术栈**: Node.js (TypeScript) + Koa 框架  
**启动方式**: `tsup` 构建后运行在 5100 端口  
**部署**: 支持 Vercel 部署

### 1.2 完整文件结构

```
dreamina2api/
├── package.json              # 项目配置 (jimeng-api v1.0.0)
├── tsconfig.json             # TypeScript 配置 (NodeNext)
├── vercel.json               # Vercel 部署配置
├── .gitignore
├── configs/dev/
│   ├── service.yml           # 服务配置 (host: 0.0.0.0, port: 5100)
│   └── system.yml            # 系统配置 (日志、临时文件)
└── src/
    ├── index.ts              # 入口：启动Koa服务，挂载路由
    ├── api/
    │   ├── builders/
    │   │   └── payload-builder.ts   # 请求载荷构建器（分辨率、参数、草稿内容）
    │   ├── consts/
    │   │   ├── common.ts            # 通用常量（模型映射表、分辨率选项、地区）
    │   │   ├── country-profiles.ts  # 多地区站点配置（CN/US/HK/JP/SG）
    │   │   ├── dreamina.ts          # Dreamina特定URL常量
    │   │   └── exceptions.ts        # 错误码定义
    │   ├── controllers/
    │   │   ├── core.ts              # 核心：HTTP请求、Token解析、代理、区域识别
    │   │   ├── images.ts            # 图像生成控制器
    │   │   ├── videos.ts            # 视频生成控制器
    │   │   └── task-poller.ts       # 异步任务轮询器
    │   └── routes/
    │       ├── index.ts             # 路由聚合 + 根路由（服务状态）
    │       ├── images.ts            # POST /v1/images/generations
    │       ├── videos.ts            # POST /v1/videos/generations
    │       ├── models.ts            # GET /v1/models
    │       ├── tasks.ts             # GET /v1/tasks/:id
    │       ├── token.ts             # POST /token/{check,points,receive}
    │       └── ping.ts              # GET /ping
    └── lib/
        ├── async-task-store.ts      # SQLite异步任务持久化
        ├── aws-signature.ts         # AWS4-HMAC-SHA256签名算法
        ├── config.ts                # 配置管理
        ├── configs/
        │   ├── service-config.ts    # 服务配置加载（YAML）
        │   └── system-config.ts     # 系统配置加载（YAML）
        ├── consts/exceptions.ts     # 系统异常码
        ├── environment.ts           # 环境变量/命令行参数
        ├── error-handler.ts         # 统一错误处理
        ├── exceptions/
        │   ├── APIException.ts      # API异常
        │   └── Exception.ts         # 基础异常
        ├── http-status-codes.ts     # HTTP状态码常量
        ├── image-uploader.ts        # 图片上传到ImageX（字节图片CDN）
        ├── image-utils.ts           # 图片/视频URL提取工具
        ├── initialize.ts            # 进程信号处理
        ├── logger.ts                # 日志系统
        ├── region-utils.ts          # 地区配置工具
        ├── request/Request.ts       # 请求封装（参数验证）
        ├── response/
        │   ├── Body.ts              # 响应体基类
        │   ├── FailureBody.ts       # 错误响应体
        │   └── Response.ts          # 响应封装
        ├── server.ts                # Koa服务器封装（CORS、JSON解析）
        ├── smart-poller.ts          # 智能轮询器
        ├── util.ts                  # 工具函数集
        └── video-uploader.ts        # 视频上传到VOD（字节视频服务）
```

### 1.3 API端点清单

| 方法 | 路径 | 功能 | 同步/异步 |
|------|------|------|-----------|
| GET | `/` | 服务状态和信息 | - |
| POST | `/v1/images/generations` | 图像生成（文生图） | 支持async |
| POST | `/v1/images/compositions` | 图生图合成 | 支持async |
| POST | `/v1/videos/generations` | 视频生成 | 支持async |
| GET | `/v1/models` | 获取可用模型列表 | - |
| GET | `/v1/tasks/:id` | 查询异步任务状态 | - |
| GET | `/ping` | 健康检查 | - |
| POST | `/token/check` | Token有效性检查 | - |
| POST | `/token/points` | 查询积分 | - |
| POST | `/token/receive` | 收取每日积分 | - |

### 1.4 核心技术实现

- **认证**: 使用 refresh_token（即梦登录token），直接作为access_token使用
- **区域识别**: 根据token前缀识别CN/US/HK/JP/SG等地区，自动切换API域名和参数
- **图像上传**: 通过 ImageX（字节图片CDN）上传，使用 AWS4-HMAC-SHA256 签名
- **视频上传**: 通过 VOD（字节视频服务），使用 AWS4-HMAC-SHA256 签名
- **异步任务**: SQLite 持久化 + 智能轮询机制
- **模型映射**: 用户友好名 → 即梦内部模型名（如 `jimeng-4.5` → `high_aes_general_v40l`）
- **分辨率**: 支持 1k/2k/4k 多级分辨率，不同比例映射

---

## 二、insMind 网站分析

### 2.1 网站性质

**insMind (insmind.com) = 稿定设计(gaoding.com) 海外版**

稿定设计是一家厦门科技公司的在线设计平台。insMind 是其面向海外用户的版本，提供多语言支持（中/英/日/韩/法/德/西/葡/俄等20+语言）。

### 2.2 AI功能分析（从i18n数据提取）

#### 图像生成类
| 功能 | 内部名称 | 说明 |
|------|----------|------|
| AI绘图 | `aiDrawing` / `imageGenerationToolName` | 文生图、图生图 |
| AI素材 | `aiMaterial` | AI生成设计素材 |
| AI商品图 | `productImage` / `aiSceneGeneration` | 电商产品场景图 |
| AI做同款 | `makeSame` / `makeSameStyle` | 风格复制 |
| AI扩图 | `aiExpand` | 图像外扩 |
| AI消除 | `magicEraser` / `eraseDesc` | 智能消除 |
| AI替换 | `aiReplace` / `smearReplace` | 涂抹替换 |
| AI变清晰 | `ultraClear` / `makeClearDesc` | 图片增强/超清 |
| AI滤镜 | `filterDesc` / `styleTransfer` | 风格迁移/滤镜 |
| AI抠图 | `aiMatting` | 智能抠图 |
| AI背景 | `aiBackground` | 智能背景生成 |
| AI美颜 | `oneClickBeauty` | 一键美颜 |

#### 视频生成类
| 功能 | 内部名称 | 说明 |
|------|----------|------|
| AI视频生成 | `videoGenerate` / `aiVideoGeneration` | 文生视频 |
| 首尾帧 | `firstFrame` / `lastFrame` | 首帧/尾帧控制 |
| 口播视频 | `generateVideo` | 口播视频生成 |

#### AI对话/Agent类
| 功能 | 内部名称 | 说明 |
|------|----------|------|
| AI对话 | `aiChat` | AI对话助手 |
| Agent模式 | `agentMode` | 多Agent协作 |
| 数字分身 | `digitalAvatar` | 数字人 |
| 技能系统 | `skill` | 可定制技能 |

### 2.3 技术栈

| 层面 | 技术 |
|------|------|
| 前端框架 | Vue 2 + web-widget（微前端） |
| UI库 | Ant Design v4.4.5 |
| 认证 | `@gaoding/auth-next` (OAuth2) |
| 网络 | `@gaoding/axios-adapters` |
| 文件系统 | `@gaoding/file-ms` → gd-filems.dancf.com |
| 埋点 | `@gaoding/gd-tracker` |
| 国际化 | 内置 i18n（20+语言） |
| CDN | cdn.dancf.com / esm.dancf.com |
| 监控 | Google Analytics / Clarity / Yandex |

### 2.4 关键发现

从 i18n 数据中发现一条重要信息：
> "点击'同意'即视为您允许您所选择的内容（图片等）通过AI工具，并发送至**即梦、千问**三方服务进行创作。"

**这意味着 insMind 的底层AI能力部分是调用即梦(Dreamina)和千问(Qwen)的API。** insMind 作为聚合平台，在其上层的AI功能背后可能使用了与即梦相同的底层模型能力。

---

## 三、对比分析

### 3.1 平台差异

| 维度 | dreamina2api（即梦） | insMind（稿定海外） |
|------|---------------------|-------------------|
| **母公司** | 字节跳动 | 稿定科技（厦门） |
| **平台定位** | 纯AI生成平台 | 在线设计工具平台 |
| **核心业务** | AIGC图像/视频生成 | 设计模板+AI辅助 |
| **API域名** | jimeng.jianying.com / dreamina-api.us.capcut.com | dancf.com（稿定CDN） |
| **前端框架** | React SPA | Vue 2 + web-widget |
| **底层模型** | 自研（jimeng/seedance系列） | 聚合（即梦+千问等） |
| **多地区策略** | 多站独立部署 | 单站多语言 |

### 3.2 API架构差异

| 维度 | dreamina2api | insMind |
|------|-------------|---------|
| **API风格** | RESTful (/mweb/v1/*) | 稿定内部微服务（无公开API） |
| **认证方式** | refresh_token | OAuth2 (@gaoding/auth-next) |
| **签名算法** | AWS4-HMAC-SHA256 | 稿定内部签名 |
| **文件上传** | ImageX（字节）/ VOD（字节） | gd-filems（稿定文件系统） |
| **模型命名** | jimeng-4.5 / seedance-2.0 | 稿定内部命名 |
| **响应格式** | 自定义JSON | 稿定内部格式 |
| **公开程度** | 无官方API（逆向工程） | 无公开API，全前端渲染 |

### 3.3 核心结论

**dreamina2api 和 insMind 是两个完全独立的平台，底层API体系完全不同。**  
dreamina2api 封装的是字节跳动的即梦API，而 insMind 是稿定设计的海外版。

关键点：insMind 本身也在调用即梦的模型能力（通过其自己的后端转发）。这意味着即梦的 API 是 insMind 的后端数据源之一，但 insMind 的前端并不直接暴露即梦的API端点。

---

## 四、改造方案

### 方案一：保留即梦API + 增加insMind前端适配（推荐用于快速上线）

**思路**：保留 dreamina2api 对即梦API的封装，但增加一层insMind风格的前端界面。

这种方法不动核心业务逻辑，只是让接口暴露方式更贴近insMind的调用习惯。

```
dreamina2api (现有) → 增加insMind适配层
```

**改造步骤**：

1. **新增 `src/adapters/insmind/` 目录**
   - `insmind-router.ts` — 模仿insMind风格的API路由
   - `insmind-models.ts` — insMind模型 ↔ 即梦模型映射
   - `insmind-response.ts` — insMind格式的响应封装

2. **新增insMind API端点**
   - `POST /api/ai/drawing` → 映射到即梦图像生成
   - `POST /api/ai/video/generate` → 映射到即梦视频生成
   - `GET /api/models` → 返回insMind格式模型列表

3. **修改路由聚合** (`src/api/routes/index.ts`)
   - 同时注册原有即梦API和新insMind API

4. **模型映射表**
   ```
   insMind → 即梦
   "jimeng-4.5" → "high_aes_general_v40l" (已有)
   ```

### 方案二：纯逆向 + 重写适配层（完整方案，推荐）

**思路**：逆向分析insMind的实际API调用，仿照dreamina2api的模式重新封装。

**分析阶段**：
1. 使用浏览器开发者工具抓取 insMind 网站的API请求
2. 分析 insMind AI 功能的实际 API 端点、认证方式、请求格式
3. 识别 insMind 调用了哪些底层模型（即梦？千问？自研？）
4. 记录所有 API 端点的请求/响应格式

**实现阶段**：

1. **新建项目结构**（基于dreamina2api的架构模式）
   ```
   insmind2api/
   ├── src/
   │   ├── index.ts           # 入口
   │   ├── api/
   │   │   ├── routes/        # insMind API路由
   │   │   ├── controllers/   # 业务逻辑控制器
   │   │   ├── consts/        # 常量配置
   │   │   └── builders/      # 请求载荷构建
   │   └── lib/               # 通用库
   ```

2. **核心改动点**
   - **认证模块**：替换refresh_token为稿定OAuth2认证
   - **请求模块**：替换AWS4签名为稿定签名
   - **上传模块**：替换ImageX/VOD为稿定文件系统
   - **模型映射**：替换即梦模型映射为insMind模型映射
   - **响应格式**：适配insMind的JSON响应格式

### 方案三：前端界面改造（视觉效果）

**思路**：保持dreamina2api的后端不变，但提供一个insMind风格的前端UI界面。

```
dreamina2api (后端不变)
  + insmind-style-frontend (新增前端)
```

**改造步骤**：
1. 新增 `public/` 或 `views/` 目录，放置insMind风格的前端页面
2. 使用 HTML/CSS/JS 实现insMind风格的AI创作界面
3. 前端页面调用 dreamina2api 的后端API

### 方案四：混合架构（推荐长期方案）

将方案一和方案二结合：

1. **短期**：直接复用 dreamina2api 的即梦API封装能力（因为insMind底层也是调用即梦）
2. **中期**：逆向分析insMind的实际API调用过程，逐步替换后端适配层
3. **长期**：完全独立于即梦API，直接与稿定/insMind的API集成

---

## 五、具体实施路径（推荐方案一）

### 第一阶段：基础适配（3-5天）

```
新增文件:
src/api/routes/insmind/
├── index.ts           # insMind路由聚合
├── drawing.ts         # POST /api/ai/drawing - AI绘图
├── video.ts           # POST /api/ai/video - AI视频
└── models.ts          # GET /api/models - 模型列表
```

### 第二阶段：模型映射（1-2天）

```typescript
// src/api/consts/insmind-models.ts
export const INSMIND_IMAGE_MODEL_MAP = {
  "insmind-v1": "jimeng-4.5",
  "insmind-hd": "jimeng-5.0",
  // ... 映射到即梦模型
};
```

### 第三阶段：认证适配（2-3天）

```
新增 src/lib/auth/insmind-auth.ts
- 处理insMind风格的认证token
- 支持多用户token轮询
```

### 第四阶段：前端界面（可选，3-5天）

```
新增 frontend/ 目录
- insMind风格AI创作界面
- 对话式交互（类似insMind的AI Chat）
```

---

## 六、总结

| 方案 | 难度 | 工期 | 效果 |
|------|------|------|------|
| 方案一（API适配） | ⭐⭐ | 1-2周 | 后端兼容，前端不变 |
| 方案二（纯逆向） | ⭐⭐⭐⭐⭐ | 1-2月 | 深度集成 |
| 方案三（前端界面） | ⭐⭐ | 1-2周 | 视觉模仿，内核不变 |
| 方案四（混合架构） | ⭐⭐⭐⭐ | 1月+ | 渐进式改造 |

**建议优先采用方案一（保留即梦API+增加insMind适配层）**，因为：
1. insMind底层也在调用即梦的模型能力
2. dreamina2api已经封装了完整的即梦API
3. 工期短、风险低
4. 可以快速验证市场需求