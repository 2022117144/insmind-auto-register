/**
 * 前端 mock 路由 — 为 insmind-api 提供 dreamina-auto-register 兼容端点
 *
 * 所有旧版 dreamina 前端页面（Dashboard/Accounts/Tasks/Proxies/Domains/Settings/Mailboxes）
 * 调用这些端点获取 mock 数据，确保页面能正常渲染。
 *
 * 内容生成（ContentGeneration）端点另由 content.ts 处理（桥接到 insmind 适配器）。
 */
import _ from "lodash";
import Request from "@/lib/request/Request.ts";

// ========== 共享数据存储（进程内内存） ==========
const db: Record<string, any[]> = {
  tasks: [],
  accounts: [],
  proxies: [],
  domains: [],
  outlook_mailboxes: [],
  content_jobs: [],
};
let nextId = 1;

export default [
  // ============================================================
  //  GET /api/health — 健康检查（Dashboard 需要）
  // ============================================================
  {
    prefix: "/api",
    get: {
      "/health": async () => ({
        services: {
          clash: "connected",
          cloudflare_kv: "configured",
        },
      }),
    },
  },

  // ============================================================
  //  GET /api/dashboard/stats — Dashboard 统计（核心页面）
  // ============================================================
  {
    prefix: "/api/dashboard",
    get: {
      "/stats": async () => ({
        accounts: {
          total: 128,
          success: 96,
          failed: 32,
          success_rate: 75,
          today_success: 12,
        },
        proxies: {
          total: 24,
          active: 18,
          online_ratio: "18/24",
        },
        trends: [
          { name: "周一", total: 15 },
          { name: "周二", total: 22 },
          { name: "周三", total: 18 },
          { name: "周四", total: 25 },
          { name: "周五", total: 20 },
          { name: "周六", total: 28 },
          { name: "周日", total: 12 },
        ],
      }),
    },
  },

  // ============================================================
  //  Accounts API — /api/accounts/*
  // ============================================================
  {
    prefix: "/api/accounts",
    get: {
      "(/)?" : async (request: Request) => {
        const page = parseInt(request.query.page || "1");
        const pageSize = parseInt(request.query.page_size || "50");
        const items = db.accounts.length > 0 ? db.accounts : generateMockAccounts(50);
        if (db.accounts.length === 0) db.accounts.push(...items);
        return items.slice((page - 1) * pageSize, page * pageSize);
      },
      "/count": async () => ({
        total: 128,
        success: 96,
        failed: 32,
        pending: 0,
        success_rate: 75,
        matched: 128,
      }),
      "/:id": async (request: Request) => {
        const id = parseInt(request.params.id);
        const account = db.accounts.find((a) => a.id === id);
        return account || { id, email: `user${id}@example.com`, status: "success", region: "us" };
      },
      "/export": async () => [],
    },
    post: {
      "/:id/refresh-status": async (request: Request) => {
        const id = parseInt(request.params.id);
        return { id, status: "success", last_login_status: "success" };
      },
      "/:id/checkin": async (request: Request) => {
        const id = parseInt(request.params.id);
        return { id, last_checkin_at: new Date().toISOString() };
      },
      "/batch/refresh-status": async () => ({ message: "已批量刷新状态", updated: 10 }),
      "/batch/checkin": async () => ({ message: "已批量签到", updated: 10 }),
      "/batch": async () => ({ message: "已批量删除", deleted: 5 }),
      "/manual": async (request: Request) => ({
        id: nextId++,
        email: request.body?.email || "manual@example.com",
        region: request.body?.region || "us",
        status: "active",
        created_at: new Date().toISOString(),
      }),
      "/manual/import": async () => ({ success: 3, skipped: 0, failed: 0, errors: [] }),
    },
  },

  // ============================================================
  //  Tasks API — /api/tasks/*
  // ============================================================
  {
    prefix: "/api/tasks",
    get: {
      "(/)?" : async () => db.tasks,
      "/:id": async (request: Request) => {
        const task = db.tasks.find((t) => t.task_id === request.params.id || String(t.id) === request.params.id);
        return task || { id: 1, task_id: request.params.id, status: "completed", total_count: 10, success_count: 8, failure_count: 2, progress: 100, created_at: new Date().toISOString() };
      },
    },
    post: {
      "(/)?" : async (request: Request) => {
        const task = {
          id: nextId++,
          task_id: `task-${nextId}`,
          status: "created",
          total_count: request.body?.total_count || 10,
          success_count: 0,
          failure_count: 0,
          progress: 0,
          created_at: new Date().toISOString(),
          ...request.body,
        };
        db.tasks.push(task);
        return task;
      },
      "/:id/start": async () => ({ message: "任务已启动" }),
      "/:id/pause": async () => ({ message: "任务已暂停" }),
      "/:id/cancel": async () => ({ message: "任务已取消" }),
    },
    delete: {
      "/:id": async () => ({ message: "任务已删除" }),
    },
  },

  // ============================================================
  //  Proxies API — /api/proxies/*
  // ============================================================
  {
    prefix: "/api/proxies",
    get: {
      "(/)?" : async () => [],
      "/clash-status": async () => ({ connected: true, current_node: "香港节点" }),
      "/pool/status": async () => ({ total: 24, active: 18, idle: 6 }),
    },
    post: {
      "/sync": async () => ({ message: "代理节点已同步", count: 24 }),
      "/:id/toggle": async (request: Request) => {
        const id = parseInt(request.params.id);
        return { id, is_enabled: true, name: `proxy-${id}` };
      },
      "/batch-toggle": async () => ({ message: "已批量切换", toggled: 5 }),
      "/test-latency": async () => ({ message: "延迟测试完成" }),
      "/:id/test-latency": async (request: Request) => {
        const id = parseInt(request.params.id);
        return { id, latency: 42, is_healthy: true };
      },
      "/pool/reload": async () => ({ message: "代理池已重载", count: 24 }),
    },
    put: {
      "/:id": async (request: Request) => {
        const id = parseInt(request.params.id);
        return { id, ...request.body };
      },
    },
  },

  // ============================================================
  //  Domains API — /api/domains/*
  // ============================================================
  {
    prefix: "/api/domains",
    get: {
      "(/)?" : async () => db.domains.length > 0 ? db.domains : [
        { id: 1, domain: "example.com", cf_zone_id: "zone1", is_enabled: true, usage_count: 0, usage_limit: 100, is_available: true, created_at: new Date().toISOString() },
      ],
    },
    post: {
      "(/)?" : async (request: Request) => {
        const domain = { id: nextId++, is_enabled: true, usage_count: 0, is_available: true, created_at: new Date().toISOString(), ...request.body };
        db.domains.push(domain);
        return domain;
      },
      "/:id/toggle": async (request: Request) => {
        const id = parseInt(request.params.id);
        return { id, is_enabled: true };
      },
      "/:id/test": async () => ({ message: "测试完成", success: true }),
    },
    put: {
      "/:id": async (request: Request) => {
        const id = parseInt(request.params.id);
        return { id, ...request.body };
      },
    },
    delete: {
      "/:id": async () => ({ message: "域名已删除" }),
    },
  },

  // ============================================================
  //  Settings API — /api/settings/*
  // ============================================================
  {
    prefix: "/api/settings",
    get: {
      "(/)?" : async () => ({
        dreamina_url: "https://www.insmind.com",
        register_timeout: 60000,
        verification_timeout: 30000,
        max_retry_count: 3,
        gen_async_enabled: true,
        gen_image_async_poll_interval: 3000,
        gen_video_async_poll_interval: 5000,
        register_interval_min: 5000,
        register_interval_max: 10000,
        password_length: 12,
        password_include_special: true,
        browser_headless: true,
        clash_controller_url: "http://127.0.0.1:9090",
        clash_secret: "",
        clash_proxy_port: 7890,
        clash_proxy_group: "Auto",
        proxy_pool_keywords: "",
        mihomo_binary_path: "",
        clash_config_path: "",
        max_concurrency: 5,
        proxy_pool_start_port: 10000,
        proxy_pool_size: 20,
        ext_proxy_file_path: "",
      }),
    },
    put: {
      "(/)?" : async (request: Request) => ({ message: "设置已保存", ...request.body }),
    },
  },

  // ============================================================
  //  Outlook Mailboxes API — /api/outlook-mailboxes/*
  // ============================================================
  {
    prefix: "/api/outlook-mailboxes",
    get: {
      "(/)?" : async (request: Request) => {
        const page = parseInt(request.query.page || "1");
        const pageSize = parseInt(request.query.page_size || "50");
        return {
          total: db.outlook_mailboxes.length || 10,
          page,
          page_size: pageSize,
          items: db.outlook_mailboxes.length > 0
            ? db.outlook_mailboxes
            : [
                { id: 1, email: "user1@outlook.com", is_enabled: true, usage_count: 5, created_at: new Date().toISOString() },
                { id: 2, email: "user2@outlook.com", is_enabled: false, usage_count: 2, created_at: new Date().toISOString() },
              ],
        };
      },
    },
    post: {
      "/batch": async (request: Request) => {
        const emails: string[] = request.body?.emails || [];
        const newBoxes = emails.map((email) => ({
          id: nextId++,
          email,
          is_enabled: true,
          usage_count: 0,
          created_at: new Date().toISOString(),
        }));
        db.outlook_mailboxes.push(...newBoxes);
        return { message: "导入成功", success: true, count: newBoxes.length };
      },
    },
    patch: {
      "/:id": async (request: Request) => {
        const id = parseInt(request.params.id);
        return { id, is_enabled: request.body?.is_enabled ?? true };
      },
    },
    delete: {
      "/:id": async () => ({ message: "邮箱已删除" }),
    },
  },
];

// ========== 工具函数 ==========

function generateMockAccounts(count: number) {
  const statuses = ["active", "success", "failed", "banned", "pending"];
  const regions = ["us", "sg", "jp", "hk", "kr", "de", "gb"];
  const healthStatuses = ["healthy", "expired", "banned", "unknown"];

  return Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    email: `dreamina_user${i + 1}@outlook.com`,
    password: `pwd_${Math.random().toString(36).slice(2, 10)}`,
    session_id: `session_${Math.random().toString(36).slice(2, 16)}`,
    status: statuses[i % statuses.length] as any,
    last_login_status: i % 3 === 0 ? "success" : "failed",
    is_valid: i % 2 === 0 ? "true" : "false",
    proxy_node_name: i % 3 === 0 ? `proxy-${(i % 10) + 1}` : null,
    region: regions[i % regions.length],
    health_status: healthStatuses[i % healthStatuses.length] as any,
    created_at: new Date(Date.now() - i * 86400000).toISOString(),
    credits_total: Math.floor(Math.random() * 1000),
    credits_gift: Math.floor(Math.random() * 500),
    credits_purchase: Math.floor(Math.random() * 300),
    credits_vip: Math.floor(Math.random() * 200),
    gen_enabled: i % 2 === 0,
    usage_count: Math.floor(Math.random() * 50),
  }));
}