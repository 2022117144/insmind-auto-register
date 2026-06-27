/**
 * insMind Token Refresh Module
 * 
 * Automatically refreshes expired Bearer JWTs using insMind's refresh token endpoint.
 * Tokens expire after 8 hours (28800s). This module checks every 5 minutes.
 * 
 * Refresh flow:
 *   1. Check token expiry (check access_token_expires_at)
 *   2. If within 5 min of expiry, call POST /api/gaoding-art/v1/oauth2/token/refresh
 *   3. Decode the new token.prod to extract new access_token
 *   4. Update the account in the pool
 *   5. If refresh fails (401/expired), mark account as expired
 */

import https from 'https';
import http from 'http';

// ============ Interfaces ============

interface InsMindAccount {
    email: string;
    token: string;       // inner JWT (access_token)
    userId: string;
    credits: number;
    refreshToken?: string;    // from token.prod.refresh_token cookie
    refreshTokenSig?: string; // from token.prod.refresh_token.sig cookie
    tokenExpiresAt?: number;  // unix timestamp when token expires
}

interface TokenProdPayload {
    access_token: string;
    access_token_expires_at: string;
    access_token_life_time: number;
    refresh_token: string;
    refresh_token_expires_at: string;
    refresh_token_life_time: number;
    merged: boolean;
    timestamp: number;
}

// ============ Helpers ============

function base64UrlDecode(str: string): string {
    // Add padding
    let s = str.replace(/-/g, '+').replace(/_/g, '/');
    while (s.length % 4) s += '=';
    return Buffer.from(s, 'base64').toString('utf-8');
}

function decodeJwtPayload<T>(jwt: string): T | null {
    try {
        const parts = jwt.split('.');
        if (parts.length !== 3) return null;
        const decoded = base64UrlDecode(parts[1]);
        return JSON.parse(decoded) as T;
    } catch {
        return null;
    }
}

function makeRequest(options: https.RequestOptions, body?: string): Promise<{ status: number; data: string }> {
    return new Promise((resolve, reject) => {
        const req = https.request(options, (res) => {
            let data = '';
            res.on('data', (chunk: Buffer) => { data += chunk.toString(); });
            res.on('end', () => resolve({ status: res.statusCode || 500, data }));
        });
        req.on('error', reject);
        req.setTimeout(15000, () => { req.destroy(new Error('Timeout')); });
        if (body) req.write(body);
        req.end();
    });
}

// ============ Token Refresh ============

let refreshTimer: NodeJS.Timeout | null = null;
let accountsRef: InsMindAccount[] = [];

/**
 * Parse the token.prod JWT to extract refresh_token and expiry info
 * Supports two formats:
 *   1. JWT format (3 parts, header.payload.signature)
 *   2. Base64-encoded JSON: {"access_token":"...","refresh_token":"...",...}
 */
export function parseTokenProd(tokenProdStr: string): {
    accessToken: string;
    refreshToken: string;
    expiresAt: number;
} | null {
    // Try JWT format first (3 dot-separated parts)
    const jwtPayload = decodeJwtPayload<TokenProdPayload>(tokenProdStr);
    if (jwtPayload) {
        return {
            accessToken: jwtPayload.access_token,
            refreshToken: jwtPayload.refresh_token,
            expiresAt: new Date(jwtPayload.access_token_expires_at).getTime(),
        };
    }

    // Fallback: try base64-encoded JSON format
    try {
        const padded = tokenProdStr + '='.repeat((4 - tokenProdStr.length % 4) % 4);
        const decoded = Buffer.from(padded, 'base64url').toString('utf-8');
        const payload = JSON.parse(decoded) as TokenProdPayload;
        if (payload && payload.access_token) {
            return {
                accessToken: payload.access_token,
                refreshToken: payload.refresh_token,
                expiresAt: new Date(payload.access_token_expires_at).getTime(),
            };
        }
    } catch {
        // ignore
    }

    return null;
}

/**
 * Refresh a single account's token via insMind's refresh endpoint
 */
async function refreshAccountToken(account: InsMindAccount): Promise<boolean> {
    if (!account.refreshToken) {
        console.log(`[TokenRefresh] ${account.email}: no refresh_token, skipping`);
        return false;
    }

    const body = JSON.stringify({ refresh_token: account.refreshToken });

    try {
        const result = await makeRequest({
            hostname: 'www.insmind.com',
            path: '/api/gaoding-art/v1/oauth2/token/refresh',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-product-type': 'INDIVIDUAL_FREE',
                'x-channel-id': '781',
                'origin': 'https://www.insmind.com',
                'referer': 'https://www.insmind.com/creation',
                'user-agent': 'insmind2api/1.1',
            },
        }, body);

        if (result.status === 200) {
            // Parse the new token.prod from response
            const parsed = parseTokenProd(result.data);
            if (parsed && parsed.accessToken) {
                account.token = parsed.accessToken;
                account.tokenExpiresAt = parsed.expiresAt;
                if (parsed.refreshToken) {
                    account.refreshToken = parsed.refreshToken;
                }
                console.log(`[TokenRefresh] ✅ ${account.email}: token refreshed, expires ${new Date(parsed.expiresAt).toISOString()}`);

                // Sync back to backend DB
                const backendBody = JSON.stringify({ token: parsed.accessToken });
                const backendReq = http.request({
                    hostname: 'localhost',
                    port: 8005,
                    path: `/api/insmind/accounts/${encodeURIComponent(account.email)}/token`,
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                        'Content-Length': Buffer.byteLength(backendBody),
                    },
                    timeout: 5000,
                }, (res) => {
                    if (res.statusCode === 200) {
                        console.log(`[TokenRefresh] 📤 ${account.email}: synced to backend`);
                    } else {
                        console.log(`[TokenRefresh] ⚠️ ${account.email}: backend sync returned ${res.statusCode}`);
                    }
                    res.resume();
                });
                backendReq.on('error', (err: any) => {
                    console.log(`[TokenRefresh] ⚠️ ${account.email}: backend sync error - ${err.message}`);
                });
                backendReq.write(backendBody);
                backendReq.end();

                return true;
            }
        }

        console.log(`[TokenRefresh] ❌ ${account.email}: refresh failed (${result.status})`);
        return false;
    } catch (err: any) {
        console.log(`[TokenRefresh] ❌ ${account.email}: refresh error - ${err.message}`);
        return false;
    }
}

/**
 * Check all accounts and refresh those near expiry
 */
async function checkAndRefreshAll(): Promise<void> {
    const now = Date.now();
    const fiveMinMs = 5 * 60 * 1000;

    for (const account of accountsRef) {
        // If no expiry info, try to parse from token
        if (!account.tokenExpiresAt) {
            const parsed = parseTokenProd(account.token);
            if (parsed) {
                account.tokenExpiresAt = parsed.expiresAt;
                if (parsed.refreshToken) account.refreshToken = parsed.refreshToken;
            }
        }

        if (!account.tokenExpiresAt) continue;

        const timeLeft = account.tokenExpiresAt - now;
        if (timeLeft < fiveMinMs && timeLeft > 0) {
            console.log(`[TokenRefresh] ${account.email}: expiring in ${Math.round(timeLeft / 1000)}s, refreshing...`);
            await refreshAccountToken(account);
        } else if (timeLeft <= 0 && account.refreshToken) {
            console.log(`[TokenRefresh] 🔴 ${account.email}: token expired ${Math.round(-timeLeft / 1000)}s ago, attempting refresh...`);
            await refreshAccountToken(account);
        } else if (timeLeft <= 0) {
            console.log(`[TokenRefresh] 🔴 ${account.email}: token expired, no refresh_token available`);
            account.credits = -1; // Mark as expired
        }
    }
}

/**
 * Start the token refresh interval. Call this once on startup.
 * @param accounts Reference to the accounts array in index.ts
 * @param intervalMs Check interval (default: 5 minutes)
 */
export function startTokenRefresh(
    accounts: InsMindAccount[],
    intervalMs: number = 5 * 60 * 1000
): void {
    if (refreshTimer) return;

    accountsRef = accounts;
    console.log(`[TokenRefresh] Starting refresh loop (every ${Math.round(intervalMs / 1000)}s)`);

    // Run immediately on start
    checkAndRefreshAll();

    // Then schedule periodically
    refreshTimer = setInterval(() => {
        checkAndRefreshAll();
    }, intervalMs);
}

/**
 * Stop the token refresh interval
 */
export function stopTokenRefresh(): void {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
        console.log('[TokenRefresh] Stopped');
    }
}

// ============ Singleton for easy import ============

let _initialized = false;

/**
 * Initialize token refresh with a callback to get the accounts array
 * @param getAccounts Function that returns the current accounts array
 */
export function initTokenRefresh(getAccounts: () => InsMindAccount[]): void {
    if (_initialized) return;
    _initialized = true;

    // Proxy pattern: use getAccounts to always get latest accounts
    const proxyArray = new Proxy<InsMindAccount[]>([] as any, {
        get(target, prop) {
            const real = getAccounts();
            if (prop === 'length') return real.length;
            if (prop === Symbol.iterator) return real[Symbol.iterator].bind(real);
            // Forward array method calls
            if (typeof prop === 'string' && !isNaN(Number(prop))) return real[Number(prop)];
            return (target as any)[prop];
        }
    });

    startTokenRefresh(proxyArray as any);
    console.log('[TokenRefresh] Initialized');
}
