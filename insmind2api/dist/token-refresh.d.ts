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
interface InsMindAccount {
    email: string;
    token: string;
    userId: string;
    credits: number;
    refreshToken?: string;
    refreshTokenSig?: string;
    tokenExpiresAt?: number;
}
/**
 * Parse the token.prod JWT to extract refresh_token and expiry info
 */
export declare function parseTokenProd(tokenProdStr: string): {
    accessToken: string;
    refreshToken: string;
    expiresAt: number;
} | null;
/**
 * Start the token refresh interval. Call this once on startup.
 * @param accounts Reference to the accounts array in index.ts
 * @param intervalMs Check interval (default: 5 minutes)
 */
export declare function startTokenRefresh(accounts: InsMindAccount[], intervalMs?: number): void;
/**
 * Stop the token refresh interval
 */
export declare function stopTokenRefresh(): void;
/**
 * Initialize token refresh with a callback to get the accounts array
 * @param getAccounts Function that returns the current accounts array
 */
export declare function initTokenRefresh(getAccounts: () => InsMindAccount[]): void;
export {};
