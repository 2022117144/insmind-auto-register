import fs from "fs-extra";
import path from "path";
import { createRequire } from "node:module";

import util from "@/lib/util.ts";

export type AsyncTaskKind = "image_generation" | "image_composition" | "video_generation";
export type AsyncTaskStatus = "submitted" | "processing" | "succeeded" | "failed";

export interface AsyncTaskRecord {
  id: string;
  kind: AsyncTaskKind;
  status: AsyncTaskStatus;
  createdAt: string;
  updatedAt: string;
  refreshToken: string;
  responseFormat: "url" | "b64_json";
  historyId: string;
  endpoint: string;
  model?: string;
  prompt?: string;
  expectedItemCount: number;
  remoteStatus?: number;
  finishTime?: number;
  failCode?: string;
  result?: {
    created?: number;
    data?: any[];
    itemCount?: number;
    outputType?: "image" | "video";
  };
  error?: {
    message: string;
    failCode?: string;
    details?: any;
  };
}

const DATA_DIR = path.resolve(process.cwd(), "data");
const DB_PATH = path.join(DATA_DIR, "async-tasks.sqlite");

type DatabaseSyncLike = {
  exec(sql: string): void;
  prepare(sql: string): {
    run(...params: any[]): any;
    get(...params: any[]): any;
  };
};

let db: DatabaseSyncLike | null = null;
const runtimeRequire = createRequire(path.join(process.cwd(), "package.json"));

function utc8Now(): string {
  const now = new Date();
  const shifted = new Date(now.getTime() + 8 * 60 * 60 * 1000);
  return shifted.toISOString().replace("Z", "+08:00");
}

function ensureDb(): DatabaseSyncLike {
  if (db) return db;
  const { DatabaseSync } = runtimeRequire("node:sqlite");
  fs.ensureDirSync(DATA_DIR);
  db = new DatabaseSync(DB_PATH);
  db.exec(`PRAGMA journal_mode = WAL; PRAGMA synchronous = NORMAL;`);
  db.exec(`
    CREATE TABLE IF NOT EXISTS async_tasks (
      id TEXT PRIMARY KEY,
      kind TEXT NOT NULL,
      status TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      refresh_token TEXT NOT NULL,
      response_format TEXT NOT NULL,
      history_id TEXT NOT NULL,
      endpoint TEXT NOT NULL,
      model TEXT,
      prompt TEXT,
      expected_item_count INTEGER NOT NULL,
      remote_status INTEGER,
      finish_time INTEGER,
      fail_code TEXT,
      result_json TEXT,
      error_json TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_async_tasks_status ON async_tasks(status);
    CREATE INDEX IF NOT EXISTS idx_async_tasks_history_id ON async_tasks(history_id);
    CREATE INDEX IF NOT EXISTS idx_async_tasks_updated_at ON async_tasks(updated_at);
  `);
  return db;
}

function rowToTask(row: any): AsyncTaskRecord {
  return {
    id: row.id,
    kind: row.kind,
    status: row.status,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
    refreshToken: row.refresh_token,
    responseFormat: row.response_format,
    historyId: row.history_id,
    endpoint: row.endpoint,
    model: row.model,
    prompt: row.prompt,
    expectedItemCount: row.expected_item_count,
    remoteStatus: row.remote_status,
    finishTime: row.finish_time,
    failCode: row.fail_code,
    result: row.result_json ? JSON.parse(row.result_json) : undefined,
    error: row.error_json ? JSON.parse(row.error_json) : undefined,
  };
}

/**
 * 创建异步任务记录
 */
export async function createAsyncTask(params: {
  id: string;
  kind: AsyncTaskKind;
  refreshToken: string;
  responseFormat: "url" | "b64_json";
  historyId: string;
  endpoint: string;
  model?: string;
  prompt?: string;
  expectedItemCount?: number;
}): Promise<AsyncTaskRecord> {
  const conn = ensureDb();
  const now = utc8Now();
  const task: AsyncTaskRecord = {
    id: params.id,
    kind: params.kind,
    status: "submitted",
    createdAt: now,
    updatedAt: now,
    refreshToken: params.refreshToken,
    responseFormat: params.responseFormat,
    historyId: params.historyId,
    endpoint: params.endpoint,
    model: params.model,
    prompt: params.prompt,
    expectedItemCount: params.expectedItemCount || 1,
  };

  const stmt = conn.prepare(`
    INSERT INTO async_tasks (id, kind, status, created_at, updated_at, refresh_token, response_format,
      history_id, endpoint, model, prompt, expected_item_count)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  stmt.run(task.id, task.kind, task.status, task.createdAt, task.updatedAt,
    task.refreshToken, task.responseFormat, task.historyId, task.endpoint,
    task.model, task.prompt, task.expectedItemCount);

  return task;
}

/**
 * 获取异步任务
 */
export async function getAsyncTask(taskId: string): Promise<AsyncTaskRecord | null> {
  const conn = ensureDb();
  const stmt = conn.prepare(`SELECT * FROM async_tasks WHERE id = ?`);
  const row = stmt.get(taskId);
  return row ? rowToTask(row) : null;
}

/**
 * 保存/更新异步任务
 */
export async function saveAsyncTask(task: AsyncTaskRecord): Promise<void> {
  const conn = ensureDb();
  const now = utc8Now();
  const stmt = conn.prepare(`
    UPDATE async_tasks SET
      status = ?, updated_at = ?, remote_status = ?, finish_time = ?,
      fail_code = ?, result_json = ?, error_json = ?
    WHERE id = ?
  `);
  stmt.run(task.status, now, task.remoteStatus ?? null, task.finishTime ?? null,
    task.failCode ?? null,
    task.result ? JSON.stringify(task.result) : null,
    task.error ? JSON.stringify(task.error) : null,
    task.id);
}

/**
 * 清理过期任务
 */
export async function cleanupExpiredTasks(maxAgeMs: number): Promise<number> {
  const conn = ensureDb();
  const cutoff = new Date(Date.now() - maxAgeMs).toISOString();
  const stmt = conn.prepare(`DELETE FROM async_tasks WHERE created_at < ?`);
  stmt.run(cutoff);
  return 0;
}
