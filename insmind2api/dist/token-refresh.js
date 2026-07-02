"use strict";
var __create = Object.create;
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __getProtoOf = Object.getPrototypeOf;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
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
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// src/token-refresh.ts
var token_refresh_exports = {};
__export(token_refresh_exports, {
  initTokenRefresh: () => initTokenRefresh,
  parseTokenProd: () => parseTokenProd,
  startTokenRefresh: () => startTokenRefresh,
  stopTokenRefresh: () => stopTokenRefresh
});
module.exports = __toCommonJS(token_refresh_exports);
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
    } else if (timeLeft <= 0) {
      console.log(`[TokenRefresh] \u{1F534} ${account.email}: token expired, marking as expired`);
      account.credits = -1;
    }
  }
}
function startTokenRefresh(accounts, intervalMs = 5 * 60 * 1e3) {
  if (refreshTimer)
    return;
  accountsRef = accounts;
  console.log(`[TokenRefresh] Starting refresh loop (every ${Math.round(intervalMs / 1e3)}s)`);
  checkAndRefreshAll();
  refreshTimer = setInterval(() => {
    checkAndRefreshAll();
  }, intervalMs);
}
function stopTokenRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
    console.log("[TokenRefresh] Stopped");
  }
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
// Annotate the CommonJS export names for ESM import in node:
0 && (module.exports = {
  initTokenRefresh,
  parseTokenProd,
  startTokenRefresh,
  stopTokenRefresh
});
