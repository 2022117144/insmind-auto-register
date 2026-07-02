# STATUS.md — 改造完成记录

## 改造目标
将 dreamina2api (jimeng-api) 改造为适配 insmind.com 的 API 服务，保留原有 OpenAI 兼容 API 的同时增加 insMind 风格原生 API。

## 已完成的工作

### 1. 新增文件

| 文件 | 说明 |
|------|------|
| `src/adapters/insmind/insmind-router.ts` | insMind 风格 API 路由。提供 `POST /api/ai/drawing`（文生图/图生图）、`POST /api/ai/video/generate`（视频生成）、`GET /api/models`（模型列表）、`GET /api/health`（健康检查）、`POST/GET /api/tasks/:id`（异步任务查询/刷新） |
| `src/adapters/insmind/insmind-models.ts` | insMind 模型映射表。将对外模型名（agent-gpt-image-2, Pixversev60, Wan27 等）映射到内部 scene_code，附带模型描述和能力标签 |
| `src/adapters/insmind/insmind-response.ts` | insMind 响应格式封装。提供 `success()`/`error()` 统一响应构建，以及常见错误快捷方法（badRequest, unauthorized 等） |

### 2. 修改文件

| 文件 | 变更 |
|------|------|
| `src/api/routes/index.ts` | 导入并注册 insmindRoutes，在根路由的 endpoints 中增加 insMind 风格端点说明 |
| `package.json` | 项目名改为 `insmind-api`，描述更新，关键词更新 |

### 3. 编译验证
- `tsc --noEmit` 通过 ✅（唯一的报错是 `node_modules/koa-body/index.d.ts` 的预存类型问题，与本次修改无关）

## 新增的 API 端点

| 方法 | 路径 | 说明 | 同步/异步 |
|------|------|------|-----------|
| POST | `/api/ai/drawing` | AI 绘图（文生图 + 图生图） | 支持 async 参数 |
| POST | `/api/ai/video/generate` | AI 视频生成 | 支持 async 参数 |
| GET | `/api/models` | 获取 insMind 风格模型列表 | - |
| GET | `/api/health` | 健康检查 | - |
| GET | `/api/tasks/:id` | 查询异步任务状态 | - |
| POST | `/api/tasks/:id/refresh` | 刷新异步任务状态 | - |

原有端点（`/v1/images/generations`, `/v1/videos/generations`, `/v1/models` 等）**保持不变**，新旧 API 并行运行。

## 依赖关系

新路由复用了现有基础设施：
- `src/api/controllers/images.ts` — 图片生成
- `src/api/controllers/videos.ts` — 视频生成
- `src/api/controllers/core.ts` — Token 解析、区域识别
- `src/api/controllers/task-poller.ts` — 异步任务轮询
- `src/adapters/insmind/` — 底层 API 适配层（已由之前的工作完成）

## 还差什么（待办）

### 认证适配
- [ ] insMind 使用 OAuth2 (ums.insmind.com)，现有代码基于 `refresh_token` 认证
- [ ] `src/adapters/insmind/auth.ts` 已有 OAuth2 框架，但缺少实际的 token 刷新逻辑
- [ ] Cookie 认证 (`token.prod`) 的实现需要更多抓包数据

### 实际测试
- [ ] 需要 insMind 的 API token 进行端到端测试
- [ ] 验证 `/api/ai/drawing` 的请求/响应格式是否与 insMind 前端兼容
- [ ] 验证视频生成任务提交和轮询流程
- [ ] 上传模块（`src/adapters/insmind/upload.ts`）需要实际环境验证

### 文档
- [ ] 补充 API 文档，说明两种接口格式（OpenAI 兼容 + insMind 原生）
- [ ] 说明 insMind token 获取方式

### 前端界面（可选）
- [ ] 可新增 insMind 风格的 Web UI（参考 REFACTOR_REPORT.md 方案三）

## 关键风险
1. **底层 API 依赖**：目前 insMind 适配层底层仍调用即梦 API 控制器。如果 insMind 后端 API 变更，需要同步更新 `src/adapters/insmind/` 下的文件
2. **insMind 底层也调即梦**：从 i18n 数据看，insMind 调用即梦/千问的 API，所以当前方案一（复用即梦控制器）短期内可行
3. **认证不匹配**：insMind 使用 OAuth2，但当前代码将 token 直接作为 access_token 使用，可能需要在网关层做 token 转换

## 文件结构总览
```
dreamina2api/
├── src/
│   ├── index.ts
│   ├── api/
│   │   ├── routes/
│   │   │   ├── index.ts         ← 已修改，注册新旧路由
│   │   │   ├── images.ts        ← 原有，不变
│   │   │   ├── videos.ts        ← 原有，不变
│   │   │   └── ...
│   │   ├── controllers/         ← 原有，不变
│   │   └── consts/common.ts     ← 原有桥接层，不变
│   └── adapters/
│       └── insmind/
│           ├── index.ts         ← 原有，不变
│           ├── constants.ts     ← 原有，不变
│           ├── types.ts         ← 原有，不变
│           ├── auth.ts          ← 原有，不变
│           ├── api.ts           ← 原有，不变
│           ├── upload.ts        ← 原有，不变
│           ├── builder.ts       ← 原有，不变
│           ├── models.ts        ← 原有，不变
│           ├── response.ts      ← 原有，不变
│           ├── poller.ts        ← 原有，不变
│           ├── credit.ts        ← 原有，不变
│           ├── errors.ts        ← 原有，不变
│           ├── region.ts        ← 原有，不变
│           ├── insmind-router.ts  ← **新增**
│           ├── insmind-models.ts  ← **新增**
│           └── insmind-response.ts ← **新增**
└── package.json                ← 已修改
```