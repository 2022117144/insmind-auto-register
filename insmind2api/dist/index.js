"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toESM = (mod, isNodeMode, target) => (target = mod != null ? __create(__getProtoOf(mod)) : {}, __copyProps(
  // If the importer is in node compatibility mode or this is not an ESM
  // file that has been converted to a CommonJS file using a Babel-
  // compatible transform (i.e. "__esModule" has not been set), then set
  // "default" to the CommonJS "module.exports" for node compatibility.
  isNodeMode || !mod || !mod.__esModule ? __defProp(target, "default", { value: mod, enumerable: true }) : target,
  mod
));

// src/index.ts
var import_koa = __toESM(require("koa"));
var import_cors = __toESM(require("@koa/cors"));
var import_koa_router = __toESM(require("koa-router"));
var import_koa_body = require("koa-body");
var import_https2 = __toESM(require("https"));
var import_http2 = __toESM(require("http"));
var import_crypto = __toESM(require("crypto"));
var import_child_process = __toESM(require("child_process"));
var import_fs = __toESM(require("fs"));

// src/token-refresh.ts
var import_https = __toESM(require("https"));
var import_http = __toESM(require("http"));
function base64UrlDecode(str) {
  let s = str.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4)
    s += "=";
  return Buffer.from(s, "base64").toString("utf-8");
}
function decodeJwtPayload(jwt) {
  try {
    const parts = jwt.split(".");
    if (parts.length !== 3)
      return null;
    const decoded = base64UrlDecode(parts[1]);
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}
function makeRequest(options, body) {
  return new Promise((resolve, reject) => {
    const req = import_https.default.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => {
        data += chunk.toString();
      });
      res.on("end", () => resolve({ status: res.statusCode || 500, data }));
    });
    req.on("error", reject);
    req.setTimeout(15e3, () => {
      req.destroy(new Error("Timeout"));
    });
    if (body)
      req.write(body);
    req.end();
  });
}
var refreshTimer = null;
var accountsRef = [];
function parseTokenProd(tokenProdStr) {
  const jwtPayload = decodeJwtPayload(tokenProdStr);
  if (jwtPayload) {
    return {
      accessToken: jwtPayload.access_token,
      refreshToken: jwtPayload.refresh_token,
      expiresAt: new Date(jwtPayload.access_token_expires_at).getTime()
    };
  }
  try {
    const padded = tokenProdStr + "=".repeat((4 - tokenProdStr.length % 4) % 4);
    const decoded = Buffer.from(padded, "base64url").toString("utf-8");
    const payload = JSON.parse(decoded);
    if (payload && payload.access_token) {
      return {
        accessToken: payload.access_token,
        refreshToken: payload.refresh_token,
        expiresAt: new Date(payload.access_token_expires_at).getTime()
      };
    }
  } catch {
  }
  return null;
}
async function refreshAccountToken(account) {
  if (!account.refreshToken) {
    console.log(`[TokenRefresh] ${account.email}: no refresh_token, skipping`);
    return false;
  }
  const body = JSON.stringify({ refresh_token: account.refreshToken });
  try {
    const result = await makeRequest({
      hostname: "www.insmind.com",
      path: "/api/gaoding-art/v1/oauth2/token/refresh",
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-product-type": "INDIVIDUAL_FREE",
        "x-channel-id": "781",
        "origin": "https://www.insmind.com",
        "referer": "https://www.insmind.com/creation",
        "user-agent": "insmind2api/1.1"
      }
    }, body);
    if (result.status === 200) {
      const parsed = parseTokenProd(result.data);
      if (parsed && parsed.accessToken) {
        account.token = parsed.accessToken;
        account.tokenExpiresAt = parsed.expiresAt;
        if (parsed.refreshToken) {
          account.refreshToken = parsed.refreshToken;
        }
        console.log(`[TokenRefresh] \u2705 ${account.email}: token refreshed, expires ${new Date(parsed.expiresAt).toISOString()}`);
        const backendBody = JSON.stringify({ token: parsed.accessToken });
        const backendReq = import_http.default.request({
          hostname: "localhost",
          port: 8005,
          path: `/api/insmind/accounts/${encodeURIComponent(account.email)}/token`,
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
            "Content-Length": Buffer.byteLength(backendBody)
          },
          timeout: 5e3
        }, (res) => {
          if (res.statusCode === 200) {
            console.log(`[TokenRefresh] \u{1F4E4} ${account.email}: synced to backend`);
          } else {
            console.log(`[TokenRefresh] \u26A0\uFE0F ${account.email}: backend sync returned ${res.statusCode}`);
          }
          res.resume();
        });
        backendReq.on("error", (err) => {
          console.log(`[TokenRefresh] \u26A0\uFE0F ${account.email}: backend sync error - ${err.message}`);
        });
        backendReq.write(backendBody);
        backendReq.end();
        return true;
      }
    }
    console.log(`[TokenRefresh] \u274C ${account.email}: refresh failed (${result.status})`);
    return false;
  } catch (err) {
    console.log(`[TokenRefresh] \u274C ${account.email}: refresh error - ${err.message}`);
    return false;
  }
}
async function checkAndRefreshAll() {
  const now = Date.now();
  const fiveMinMs = 5 * 60 * 1e3;
  for (const account of accountsRef) {
    if (!account.tokenExpiresAt) {
      const parsed = parseTokenProd(account.token);
      if (parsed) {
        account.tokenExpiresAt = parsed.expiresAt;
        if (parsed.refreshToken)
          account.refreshToken = parsed.refreshToken;
      }
    }
    if (!account.tokenExpiresAt)
      continue;
    const timeLeft = account.tokenExpiresAt - now;
    if (timeLeft < fiveMinMs && timeLeft > 0) {
      console.log(`[TokenRefresh] ${account.email}: expiring in ${Math.round(timeLeft / 1e3)}s, refreshing...`);
      await refreshAccountToken(account);
    } else if (timeLeft <= 0 && account.refreshToken) {
      console.log(`[TokenRefresh] \u{1F534} ${account.email}: token expired ${Math.round(-timeLeft / 1e3)}s ago, attempting refresh...`);
      await refreshAccountToken(account);
    } else if (timeLeft <= 0) {
      console.log(`[TokenRefresh] \u{1F534} ${account.email}: token expired, no refresh_token available`);
      account.credits = -1;
    }
  }
}
function startTokenRefresh(accounts2, intervalMs = 5 * 60 * 1e3) {
  if (refreshTimer)
    return;
  accountsRef = accounts2;
  console.log(`[TokenRefresh] Starting refresh loop (every ${Math.round(intervalMs / 1e3)}s)`);
  checkAndRefreshAll();
  refreshTimer = setInterval(() => {
    checkAndRefreshAll();
  }, intervalMs);
}
var _initialized = false;
function initTokenRefresh(getAccounts) {
  if (_initialized)
    return;
  _initialized = true;
  const proxyArray = new Proxy([], {
    get(target, prop) {
      const real = getAccounts();
      if (prop === "length")
        return real.length;
      if (prop === Symbol.iterator)
        return real[Symbol.iterator].bind(real);
      if (typeof prop === "string" && !isNaN(Number(prop)))
        return real[Number(prop)];
      return target[prop];
    }
  });
  startTokenRefresh(proxyArray);
  console.log("[TokenRefresh] Initialized");
}

// src/index.ts
process.on("unhandledRejection", (reason, promise) => {
  console.error(`\u26A0\uFE0F Unhandled rejection caught: ${reason instanceof Error ? reason.message : reason}`);
});
process.on("uncaughtException", (err) => {
  console.error(`\u26A0\uFE0F Uncaught exception caught: ${err.message}`);
});
var OSS_ACCELERATE_IP = "47.253.30.33";
var app = new import_koa.default();
var router = new import_koa_router.default({ prefix: "/api" });
var BACKEND_URL = "http://127.0.0.1:8005";
var accounts = [];
var currentAccountIndex = 0;
async function refreshAccounts() {
  try {
    const data = await new Promise((resolve, reject) => {
      const req = import_http2.default.get(`${BACKEND_URL}/api/insmind/accounts`, (res) => {
        let d = "";
        res.on("data", (c) => d += c.toString());
        res.on("end", () => resolve(d));
      });
      req.on("error", reject);
      req.setTimeout(5e3, () => {
        req.destroy(new Error("Timeout"));
      });
    });
    const raw = JSON.parse(data);
    accounts = raw.map((a) => ({
      email: a.email || "",
      token: a.token || "",
      userId: a.user_id || a.userId || "0",
      credits: a.credits || 0,
      refreshToken: a.refresh_token || a.refreshToken,
      orgId: a.org_id || a.orgId,
      tokenExpiresAt: void 0
    }));
    console.log(`[Accounts] Refreshed from backend: ${accounts.length} accounts`);
  } catch (e) {
    console.log(`[Accounts] Backend refresh failed: ${e.message}, keeping ${accounts.length} cached`);
  }
}
setInterval(() => refreshAccounts(), 3e4);
refreshAccounts().then(() => {
  console.log(`\u{1F4E7} Accounts pool: ${accounts.length}`);
  initTokenRefresh(() => accounts);
  console.log("\u{1F504} Token refresh initialized (check every 5 min)");
});
function getNextAccount() {
  for (let attempt = 0; attempt < accounts.length * 2; attempt++) {
    const idx = currentAccountIndex % accounts.length;
    currentAccountIndex++;
    const account = accounts[idx];
    if (!account)
      continue;
    const parsed = parseTokenProd(account.token);
    if (parsed && parsed.expiresAt < Date.now()) {
      console.log(`\u{1F9F9} Removing expired account: ${account.email}`);
      accounts.splice(idx, 1);
      if (accounts.length === 0)
        return null;
      continue;
    }
    return account;
  }
  return null;
}
var SCENE_CODE_MAP = {
  "Pixverse-V6.0": "Pixversev60",
  "Wan-2.7": "Wan27",
  "Wan-2.2": "Wan22",
  "Kling-3.0": "Kling30",
  "Seedance-2.0": "Seedance20",
  "Seedance-2.0-Mini": "Seedance20Mini",
  "VEO-3.1": "VEO31"
};
function getInnerToken(account) {
  const parsed = parseTokenProd(account.token);
  return parsed ? parsed.accessToken : account.token;
}
function makeRequest2(options, body) {
  return new Promise((resolve, reject) => {
    const req = import_https2.default.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => {
        data += chunk.toString();
      });
      res.on("end", () => resolve({ status: res.statusCode || 500, data }));
    });
    req.on("error", reject);
    if (body)
      req.write(body);
    req.end();
  });
}
async function getStsToken(account, format) {
  const body = JSON.stringify({
    format,
    content_id: "",
    dir: "",
    device_id: "undefined"
  });
  const result = await makeRequest2({
    hostname: "www.insmind.com",
    path: "/api/tb-dam/asset/upload/tokens",
    method: "POST",
    timeout: 15e3,
    headers: {
      "Content-Type": "application/json",
      "Content-Length": Buffer.byteLength(body),
      "Authorization": `Bearer ${getInnerToken(account)}`,
      "x-product-type": "INDIVIDUAL_FREE",
      "x-channel-id": "781",
      "x-business-id": "124",
      "x-device-id": "node-uploader",
      "origin": "https://www.insmind.com",
      "referer": "https://www.insmind.com/creation",
      "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
      "Cookie": account.orgId ? `token.prod=${account.token}; token.org_id.prod=${account.orgId}` : `token.prod=${account.token}`
    }
  }, body);
  if (result.status !== 200) {
    throw new Error(`STS token request failed: ${result.status} ${result.data.substring(0, 100)}`);
  }
  return JSON.parse(result.data);
}
async function uploadMedia(account, dataUrl) {
  const matches = dataUrl.match(/^data:(image\/(\w+));base64,(.+)$/);
  if (!matches)
    throw new Error("Invalid data URL format");
  const mimeType = matches[1];
  const format = matches[2];
  const base64Data = matches[3];
  const imageBuffer = Buffer.from(base64Data, "base64");
  const sts = await getStsToken(account, format);
  const ext = format === "jpeg" ? "jpg" : format;
  const objectKey = `${sts.path}/${Date.now()}.${ext}`;
  const date = (/* @__PURE__ */ new Date()).toUTCString();
  const bucket = sts.bucket_name;
  const hostname = `${bucket}.oss-accelerate.aliyuncs.com`;
  const url = `https://${hostname}/${objectKey}`;
  const cdnUrl = `${sts.host}/${objectKey}`;
  const stringToSign = `PUT

${mimeType}
${date}
x-oss-security-token:${sts.security_token}
/${bucket}/${objectKey}`;
  const sig = import_crypto.default.createHmac("sha1", sts.access_key_secret).update(stringToSign).digest("base64");
  const auth = `OSS ${sts.access_key_id}:${sig}`;
  console.log(`\u{1F511} Signing: [${stringToSign.substring(0, 80)}...] sig=${sig.substring(0, 20)}...`);
  const tmpPath = `${process.env.TEMP || "/tmp"}/insmind-oss-${Date.now()}.${ext}`;
  import_fs.default.writeFileSync(tmpPath, imageBuffer);
  let result = "unknown";
  try {
    result = await new Promise((resolve) => {
      const curl = import_child_process.default.spawn("C:/Windows/System32/curl.exe", [
        "-s",
        "--max-time",
        "30",
        "-w",
        "%{http_code}",
        "-X",
        "PUT",
        "-H",
        `Content-Type: ${mimeType}`,
        "-H",
        `Date: ${date}`,
        "-H",
        `Authorization: ${auth}`,
        "-H",
        `x-oss-security-token: ${sts.security_token}`,
        "--data-binary",
        `@${tmpPath}`,
        "--insecure",
        "--resolve",
        `${hostname}:443:${OSS_ACCELERATE_IP}`,
        url
      ], { stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
      let stdout = "";
      let stderr = "";
      curl.stdout.on("data", (d) => stdout += d.toString());
      curl.stderr.on("data", (d) => stderr += d.toString());
      curl.on("close", (code) => {
        if (code !== 0) {
          resolve(`ERROR:curl_exit_${code} ${stderr.substring(0, 100)}`);
        } else {
          resolve(stdout.trim());
        }
      });
      curl.on("error", (err) => resolve(`ERROR:${err.message}`));
    });
    if (result === "200") {
      console.log(`\u2705 OSS upload success: ${cdnUrl}`);
      return cdnUrl;
    }
    console.log(`\u26A0\uFE0F OSS upload failed (primary): ${result}`);
  } finally {
    try {
      import_fs.default.unlinkSync(tmpPath);
    } catch {
    }
  }
  const standbyHost = sts.standby_endpoint ? sts.standby_endpoint.hostname || new URL(sts.standby_endpoint).hostname : null;
  if (standbyHost) {
    const standbyUrl = `https://${standbyHost}/${bucket}/${objectKey}`;
    console.log(`\u26A0\uFE0F Trying standby: ${standbyHost}`);
    try {
      const result2 = await new Promise((resolve) => {
        const curl = import_child_process.default.spawn("C:/Windows/System32/curl.exe", [
          "-s",
          "--max-time",
          "30",
          "-w",
          "%{http_code}",
          "-X",
          "PUT",
          "-H",
          `Content-Type: ${mimeType}`,
          "-H",
          `Date: ${date}`,
          "-H",
          `Authorization: ${auth}`,
          "-H",
          `x-oss-security-token: ${sts.security_token}`,
          "--data-binary",
          `@${tmpPath}`,
          "--insecure",
          url
        ], { stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
        let o = "";
        let e = "";
        curl.stdout.on("data", (d) => o += d.toString());
        curl.stderr.on("data", (d) => e += d.toString());
        curl.on("close", (code) => resolve(code === 0 ? o.trim() : `ERROR:${e.substring(0, 100)}`));
        curl.on("error", (err) => resolve(`ERROR:${err.message}`));
      });
      if (result2 === "200") {
        console.log(`\u2705 OSS upload success (standby): ${cdnUrl}`);
        return cdnUrl;
      }
    } catch {
    }
  }
  throw new Error(`OSS upload failed: ${result || "unknown"}`);
}
router.get("/accounts", async (ctx) => {
  ctx.body = {
    total: accounts.length,
    accounts: accounts.map((a) => ({
      email: a.email,
      userId: a.userId,
      credits: a.credits
    }))
  };
});
router.post("/accounts", async (ctx) => {
  const { email, token, userId, credits = 0, refreshToken, orgId } = ctx.request.body;
  if (!email || !token) {
    ctx.status = 400;
    ctx.body = { error: "email and token required" };
    return;
  }
  const existing = accounts.find((a) => a.email === email);
  if (!existing) {
    accounts.push({ email, token, userId: String(userId || "0"), credits, refreshToken, orgId });
  } else {
    existing.token = token;
    existing.userId = String(userId || existing.userId);
    if (orgId)
      existing.orgId = orgId;
  }
  ctx.body = { success: true, total: accounts.length };
});
router.get("/models", async (ctx) => {
  const IMAGE_MODELS = [
    { id: "jimeng-4.5", name: "Jimeng 4.5", points: 10 },
    { id: "jimeng-5.0", name: "Jimeng 5.0", points: 20 }
  ];
  const VIDEO_MODELS = [
    { id: "Pixverse-V6.0", name: "Pixverse V6.0", points: 50 },
    { id: "Wan-2.7", name: "Wan 2.7", points: 80 },
    { id: "Wan-2.2", name: "Wan 2.2", points: 20 },
    { id: "Kling-3.0", name: "Kling 3.0", points: 60 },
    { id: "Seedance-2.0", name: "Seedance 2.0", points: 40 },
    { id: "Seedance-2.0-Mini", name: "Seedance 2.0 Mini", points: 20 },
    { id: "VEO-3.1", name: "VEO 3.1", points: 70 }
  ];
  ctx.body = {
    image: IMAGE_MODELS,
    video: VIDEO_MODELS
  };
});
async function sseFetch(url, bodyStr, headers, timeoutMs = 3e5) {
  try {
    const resp = await fetch(url, {
      method: "POST",
      headers,
      body: bodyStr,
      signal: AbortSignal.timeout(timeoutMs)
    });
    return await resp.text();
  } catch {
    return "";
  }
}
router.post("/v1/videos/pricing", async (ctx) => {
  const { model = "Pixverse-V6.0", duration = 10, resolution = "360P" } = ctx.request.body;
  const baseCosts = {
    "Pixverse-V6.0": 50,
    "Wan-2.7": 80,
    "Wan-2.2": 20,
    "Kling-3.0": 60,
    "Seedance-2.0": 40,
    "Seedance-2.0-Mini": 20,
    "VEO-3.1": 70
  };
  const baseCost = baseCosts[model] || 50;
  const resolutionMultiplier = { "360P": 1, "480P": 1.2, "540P": 1.5, "720P": 2, "1080P": 3 };
  const durationMultiplier = Math.ceil(duration / 5);
  ctx.body = { cost: Math.round(baseCost * (resolutionMultiplier[resolution] || 1) * durationMultiplier), model, duration, resolution, currency: "points" };
});
router.post("/v1/videos/generations", async (ctx) => {
  const body = ctx.request.body;
  const { prompt, model = "Pixverse-V6.0", duration = 10, resolution = "360P", aspect_ratio = "16:9" } = body;
  const account = getNextAccount();
  if (!account) {
    ctx.status = 402;
    ctx.body = { error: "No accounts available" };
    return;
  }
  if (!account.orgId) {
    ctx.status = 400;
    ctx.body = { error: "Account has no orgId" };
    return;
  }
  const sceneCode = SCENE_CODE_MAP[model] || "Pixversev60";
  const taskId = `insmind-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
  const payload = {
    content: {
      type: "plain",
      scene_code: sceneCode,
      prompt: [{ type: "text", content: prompt || "" }],
      parameters: {
        ratio: aspect_ratio === "16:9" ? "" : aspect_ratio,
        resolution,
        duration: String(duration),
        styleCode: sceneCode
      },
      duration: String(duration),
      resolution,
      text: prompt || ""
    },
    name: "user",
    role: "user",
    local_thread_id: taskId,
    local_message_id: `${taskId}-msg`,
    thread_id: "",
    attachments: [],
    extra: {
      prompt_suffix: `Using video tool: ${model},Resolution: ${resolution},Duration: ${duration} seconds`,
      enable_websearch: false
    }
  };
  const bodyStr = JSON.stringify(payload);
  const sseHeaders = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${getInnerToken(account)}`,
    "x-user-id": account.userId,
    "x-content-id": taskId,
    "x-product-type": "INDIVIDUAL_FREE",
    "x-channel-id": "781",
    "origin": "https://www.insmind.com",
    "referer": "https://www.insmind.com/creation",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Cookie": account.orgId ? `token.prod=${account.token}; token.org_id.prod=${account.orgId}` : `token.prod=${account.token}`
  };
  let rawData;
  try {
    rawData = await sseFetch("https://sse.insmind.com/api/ai-agent/v1/thread/completion", bodyStr, sseHeaders);
    console.log(`\u{1F4E1} SSE response: ${rawData.length} chars`);
    if (rawData.length > 0)
      console.log(`\u{1F4C4} SSE snippet: ${rawData.substring(0, 500)}`);
  } catch (fetchErr) {
    console.error(`\u274C SSE fetch failed: ${fetchErr.message}`);
    ctx.status = 502;
    ctx.body = { error: "SSE request failed", detail: fetchErr.message };
    return;
  }
  try {
    let videoUrl = null;
    const m1 = rawData.match(/https:\/\/[^\"\\, ]+\.mp4/);
    const m2 = rawData.match(/https?:\\\/\\\/[^\"\\, ]+\.mp4/);
    if (m1)
      videoUrl = m1[0];
    else if (m2)
      videoUrl = m2[0].replace(/\\\//g, "/");
    const tidMatch = rawData.match(/"thread_id"\s*:\s*"([^"]+)"/);
    const pollTaskId = tidMatch ? tidMatch[1] : taskId;
    if (!videoUrl && (rawData.includes("function_call") || rawData.includes("Pixverse") || rawData.includes("video-generation"))) {
      console.log(`\u23F3 function_call detected, polling records with task_id=${pollTaskId.substring(0, 20)}... after 30s`);
      await new Promise((resolve) => setTimeout(resolve, 3e4));
      try {
        const pollResult = await makeRequest2({
          hostname: "www.insmind.com",
          path: `/api/dam/ai/records?task_id=${pollTaskId}`,
          method: "GET",
          headers: {
            "Authorization": `Bearer ${getInnerToken(account)}`,
            "x-product-type": "INDIVIDUAL_FREE",
            "x-channel-id": "781",
            "origin": "https://www.insmind.com",
            "referer": "https://www.insmind.com/creation",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          }
        });
        if (pollResult.status === 200) {
          const records = JSON.parse(pollResult.data);
          const items = Array.isArray(records) ? records : records?.data ?? [];
          if (items.length > 0) {
            const latest = items[0];
            const videoUrlFromRecord = latest?.generation_result || latest?.assets?.find((a) => a?.url?.includes(".mp4"))?.url || latest?.result_ext?.content_url;
            if (videoUrlFromRecord)
              videoUrl = videoUrlFromRecord;
          }
        }
      } catch {
      }
    }
    ctx.body = {
      id: taskId,
      status: "processing",
      model,
      prompt,
      duration,
      resolution,
      aspect_ratio,
      account: account.email,
      video_url: videoUrl,
      response: rawData,
      poll_interval_seconds: 15
    };
  } catch (err) {
    ctx.status = 502;
    ctx.body = { error: "Failed to process SSE response", detail: err.message, task_id: taskId };
  }
});
router.post("/v1/videos/generations-image", async (ctx) => {
  const { prompt, model = "Pixverse-V6.0", duration = 10, resolution = "360P", aspect_ratio = "16:9", image_url, account_email } = ctx.request.body;
  if (!image_url) {
    ctx.status = 400;
    ctx.body = { error: "image_url is required for image-to-video generation" };
    return;
  }
  let account = null;
  if (account_email) {
    account = accounts.find((a) => a.email === account_email) || null;
  }
  if (!account) {
    account = getNextAccount();
  }
  if (!account) {
    ctx.status = 402;
    ctx.body = { error: "No accounts available" };
    return;
  }
  if (!account.orgId) {
    ctx.status = 400;
    ctx.body = { error: "Account has no orgId" };
    return;
  }
  const sceneCode = SCENE_CODE_MAP[model] || "Pixversev60";
  const taskId = `insmind-img-${Date.now()}-${Math.random().toString(36).substring(2, 8)}`;
  let cdnUrl = image_url;
  if (typeof image_url === "string" && image_url.startsWith("data:")) {
    console.log(`\u{1F5BC}\uFE0F Uploading data URL to OSS... (${(image_url.length / 1024).toFixed(0)}KB)`);
    try {
      cdnUrl = await uploadMedia(account, image_url);
      console.log(`\u{1F5BC}\uFE0F CDN URL: ${cdnUrl}`);
    } catch (uploadErr) {
      console.log(`\u26A0\uFE0F Upload failed, falling back to data URL: ${uploadErr.message}`);
      cdnUrl = image_url;
    }
  }
  const mimeGuess = cdnUrl.endsWith(".webp") ? "image/webp" : cdnUrl.endsWith(".jpg") || cdnUrl.endsWith(".jpeg") ? "image/jpeg" : cdnUrl.endsWith(".gif") ? "image/gif" : "image/png";
  const convPayload = {
    content: {
      type: "plain",
      scene_code: sceneCode,
      prompt: [
        { type: "media", url: cdnUrl, mime: mimeGuess, name: "1." + mimeGuess.split("/")[1] },
        { type: "text", content: prompt || "" }
      ],
      parameters: {
        ratio: aspect_ratio === "16:9" ? "" : aspect_ratio,
        resolution,
        duration: String(duration),
        styleCode: sceneCode
      },
      duration: String(duration),
      resolution,
      text: prompt || ""
    },
    name: "user",
    role: "user",
    local_thread_id: taskId,
    local_message_id: `${taskId}-msg`,
    thread_id: "",
    attachments: [{ url: cdnUrl, mime_type: mimeGuess, name: "input." + mimeGuess.split("/")[1] }],
    extra: {
      prompt_suffix: "",
      enable_websearch: false
    }
  };
  const sseHeaders = {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${getInnerToken(account)}`,
    "x-user-id": account.userId,
    "x-content-id": taskId,
    "x-product-type": "INDIVIDUAL_FREE",
    "x-channel-id": "781",
    "origin": "https://www.insmind.com",
    "referer": "https://www.insmind.com/creation",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Cookie": account.orgId ? `token.prod=${account.token}; token.org_id.prod=${account.orgId}` : `token.prod=${account.token}`
  };
  let finalRawData;
  try {
    finalRawData = await sseFetch("https://sse.insmind.com/api/ai-agent/v1/thread/completion", JSON.stringify(convPayload), sseHeaders, 3e5);
    console.log(`📡 SSE response (1st): ${finalRawData.length} chars, model=${model}, resolution=${resolution}, duration=${duration}`);
    console.log(`📄 SSE snippet: ${finalRawData.substring(0, 500)}`);
  } catch (fetchErr) {
    console.error(`\u274C SSE fetch failed: ${fetchErr.message}`);
    ctx.status = 502;
    ctx.body = { error: "SSE request failed", detail: fetchErr.message };
    return;
  }
  let rawData = finalRawData;
  const firstMp4 = rawData.match(/https:\/\/[^\"\\, ]+\.mp4/) || rawData.match(/https?:\\\/\\\/[^\"\\, ]+\.mp4/);
  if (firstMp4) {
    const videoUrl = firstMp4[0].replace(/\\\\/g, "/");
    console.log(`\u2705 Video URL found in 1st SSE response`);
    ctx.body = {
      id: taskId,
      status: "processing",
      model,
      prompt,
      duration,
      resolution,
      aspect_ratio,
      account: account.email,
      video_url: videoUrl,
      cdn_url: cdnUrl,
      image_url,
      conversation: "single-turn",
      response: rawData,
      poll_interval_seconds: 15
    };
    return;
  }
  const threadMatch = rawData.match(/"thread_id"\s*:\s*"([^"]+)"/);
  let threadId = threadMatch ? threadMatch[1] : "";
  if (threadId) {
    console.log(`\u{1F4AC} Confirming function_call on thread ${threadId}`);
    const confirmPayload = JSON.parse(JSON.stringify(convPayload));
    confirmPayload.thread_id = threadId;
    confirmPayload.local_message_id = `${taskId}-confirm`;
    confirmPayload.content.prompt = [
      { type: "text", content: `Yes, generate the video now. ${prompt}` }
    ];
    try {
      const confirmResult = await sseFetch("https://sse.insmind.com/api/ai-agent/v1/thread/completion", JSON.stringify(confirmPayload), sseHeaders, 3e5);
      console.log(`\u{1F4E1} SSE response (2nd): ${confirmResult.length} chars`);
      if (confirmResult.length > 0)
        rawData = confirmResult;
    } catch (confirmErr) {
      console.error(`\u274C SSE confirmation failed: ${confirmErr.message}`);
    }
  }
  try {
    let videoUrl = null;
    for (const src of [rawData, finalRawData].filter(Boolean)) {
      const m1 = src.match(/https:\/\/[^\"\\, ]+\.mp4/);
      const m2 = src.match(/https?:\\\/\\\/[^\"\\, ]+\.mp4/);
      if (m1) {
        videoUrl = m1[0];
        break;
      }
      if (m2) {
        videoUrl = m2[0].replace(/\\\\/g, "/");
        break;
      }
    }
    const hasGenCall = ["Pixverse", "Wan-2", "Kling", "Seedance", "VEO", "video-generation"].some((kw) => rawData.includes(kw) || finalRawData.includes(kw));
    if (!videoUrl && hasGenCall) {
      console.log(`\u23F3 video-generation detected, polling records up to 3 times`);
      for (let attempt = 0; attempt < 3; attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 3e4));
        try {
          const pollResult = await makeRequest2({
            hostname: "www.insmind.com",
            path: `/api/dam/ai/records?task_id=${threadId || taskId}`,
            method: "GET",
            headers: {
              "Authorization": `Bearer ${getInnerToken(account)}`,
              "x-product-type": "INDIVIDUAL_FREE",
              "x-channel-id": "781",
              "origin": "https://www.insmind.com",
              "referer": "https://www.insmind.com/creation",
              "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
          });
          if (pollResult.status === 200) {
            const records = JSON.parse(pollResult.data);
            const items = Array.isArray(records) ? records : records?.data ?? [];
            if (items.length > 0) {
              const latest = items[0];
              const videoUrlFromRecord = latest?.generation_result || latest?.assets?.find((a) => a?.url?.includes(".mp4"))?.url || latest?.result_ext?.content_url;
              if (videoUrlFromRecord) {
                videoUrl = videoUrlFromRecord;
                console.log(`\u2705 Video found: ${videoUrl.substring(0, 60)}...`);
                break;
              }
            }
          }
        } catch {
        }
      }
    }
    ctx.body = {
      id: taskId,
      status: "processing",
      model,
      prompt,
      duration,
      resolution,
      aspect_ratio,
      account: account.email,
      video_url: videoUrl,
      cdn_url: cdnUrl,
      image_url,
      conversation: "two-turn",
      response: rawData,
      poll_interval_seconds: 15
    };
  } catch (err) {
    ctx.status = 502;
    ctx.body = { error: "Failed to process img2vid response", detail: err.message, task_id: taskId };
  }
});
router.get("/v1/tasks/:id", async (ctx) => {
  const account = getNextAccount();
  if (!account) {
    ctx.body = { id: ctx.params.id, status: "unknown", message: "No account for status check" };
    return;
  }
  try {
    const result = await makeRequest2({
      hostname: "www.insmind.com",
      path: "/api/dam/ai/records?page=1&size=10&type=video",
      method: "GET",
      headers: {
        "Authorization": `Bearer ${getInnerToken(account)}`,
        "x-product-type": "INDIVIDUAL_FREE",
        "x-channel-id": "781",
        "origin": "https://www.insmind.com",
        "referer": "https://www.insmind.com/creation",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
      }
    });
    if (result.status === 200) {
      try {
        ctx.body = { id: ctx.params.id, status: "completed", records: JSON.parse(result.data) };
      } catch {
        ctx.body = { id: ctx.params.id, status: "processing", raw: result.data.substring(0, 200) };
      }
    } else {
      ctx.body = { id: ctx.params.id, status: "processing", message: "Still generating..." };
    }
  } catch {
    ctx.body = { id: ctx.params.id, status: "processing", message: "Status check failed, retrying..." };
  }
});
app.use((0, import_cors.default)());
app.use((0, import_koa_body.koaBody)());
app.use(router.routes()).use(router.allowedMethods());
var PORT = 5105;
app.listen(PORT, () => {
  console.log(`\u{1F680} insMind2API v1.3 running on http://127.0.0.1:${PORT}`);
  console.log(`\u{1F4CB} Media upload enabled (STS + OSS for img2vid)`);
  console.log(`\u{1F4E7} Accounts pool: ${accounts.length} (add via POST /api/accounts)`);
  initTokenRefresh(() => accounts);
  console.log("\u{1F504} Token refresh initialized (check every 5 min)");
});
