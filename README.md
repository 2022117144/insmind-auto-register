# insMind Auto Register

insMind AI 视频/图片生成账号自动化管理与 API 代理服务。

## 架构

- **Backend** (`:8005`) — Python FastAPI 后端，账号管理、任务调度、OSS 上传
- **insmind2api** (`:5105`) — Node.js Koa 中间层，SSE 通信、账号池管理、视频生成
- **Frontend** (`:5177`) — Vite React 管理面板，账号注册、内容生成
- **register_insmind.py** — Playwright 自动化注册脚本

## 功能

- ✅ insMind 账号批量自动注册（Playwright）
- ✅ 文生视频（Text-to-Video）
- ✅ 图生视频（Image-to-Video，两轮 SSE 对话）
- ✅ 自动 OSS 上传（阿里云 STS + curl.exe --resolve）
- ✅ 失效账号自动清理
- ✅ 管理面板（React）

## 快速开始

```bash
# 启动后端
cd backend && .venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8005

# 启动 insmind2api
cd insmind2api && npm run build && python node_runner.py

# 启动前端
cd frontend && npx vite --port 5177
```