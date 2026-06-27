import fs from "fs-extra";
import path from "path";
import { createRequire } from "node:module";
// tsup currently rewrites node:sqlite to sqlite in bundled output on this project,
// so use a runtime-resolved import instead of a static import.

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
    run(params?: any): any;
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
    model: row.model || undefined,
    prompt: row.prompt || undefined,
    expectedItemCount: row.expected_item_count,
    remoteStatus: row.remote_status ?? undefined,
    finishTime: row.finish_time ?? undefined,
    failCode: row.fail_code || undefined,
    result: row.result_json ? JSON.parse(row.result_json) : undefined,
    error: row.error_json ? JSON.parse(row.error_json) : undefined,
  };
}

function saveTask(task: AsyncTaskRecord): void {
  const database = ensureDb();
  const stmt = database.prepare(`
    INSERT INTO async_tasks (
      id, kind, status, created_at, updated_at, refresh_token, response_format,
      history_id, endpoint, model, prompt, expected_item_count, remote_status,
      finish_time, fail_code, result_json, error_json
    ) VALUES (
      @id, @kind, @status, @createdAt, @updatedAt, @refreshToken, @responseFormat,
      @historyId, @endpoint, @model, @prompt, @expectedItemCount, @remoteStatus,
      @finishTime, @failCode, @resultJson, @errorJson
    )
    ON CONFLICT(id) DO UPDATE SET
      kind = excluded.kind,
      status = excluded.status,
      created_at = excluded.created_at,
      updated_at = excluded.updated_at,
      refresh_token = excluded.refresh_token,
      response_format = excluded.response_format,
      history_id = excluded.history_id,
      endpoint = excluded.endpoint,
      model = excluded.model,
      prompt = excluded.prompt,
      expected_item_count = excluded.expected_item_count,
      remote_status = excluded.remote_status,
      finish_time = excluded.finish_time,
      fail_code = excluded.fail_code,
      result_json = excluded.result_json,
      error_json = excluded.error_json
  `);

  stmt.run({
    id: task.id,
    kind: task.kind,
    status: task.status,
    createdAt: task.createdAt,
    updatedAt: task.updatedAt,
    refreshToken: task.refreshToken,
    responseFormat: task.responseFormat,
    historyId: task.historyId,
    endpoint: task.endpoint,
    model: task.model || null,
    prompt: task.prompt || null,
    expectedItemCount: task.expectedItemCount,
    remoteStatus: task.remoteStatus ?? null,
    finishTime: task.finishTime ?? null,
    failCode: task.failCode || null,
    resultJson: task.result ? JSON.stringify(task.result) : null,
    errorJson: task.error ? JSON.stringify(task.error) : null,
  });
}

export async function createAsyncTask(
  partial: Omit<AsyncTaskRecord, "id" | "createdAt" | "updatedAt">,
): Promise<AsyncTaskRecord> {
  const now = utc8Now();
  const task: AsyncTaskRecord = {
    ...partial,
    id: util.uuid(),
    createdAt: now,
    updatedAt: now,
  };
  saveTask(task);
  return task;
}

export async function saveAsyncTask(task: AsyncTaskRecord): Promise<void> {
  task.updatedAt = utc8Now();
  saveTask(task);
}

export async function getAsyncTask(taskId: string): Promise<AsyncTaskRecord | null> {
  const database = ensureDb();
  const row = database.prepare(`SELECT * FROM async_tasks WHERE id = ?`).get(taskId);
  if (!row) return null;
  return rowToTask(row);
}

export async function updateAsyncTask(
  taskId: string,
  updater: (task: AsyncTaskRecord) => AsyncTaskRecord | Promise<AsyncTaskRecord>,
): Promise<AsyncTaskRecord | null> {
  const task = await getAsyncTask(taskId);
  if (!task) return null;
  const nextTask = await updater(task);
  await saveAsyncTask(nextTask);
  return nextTask;
}
