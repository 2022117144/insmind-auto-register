/**
 * AWS Signature module DISABLED for insMind.
 * insMind uses OAuth2 (ums.insmind.com) — no AWS signing needed.
 * This stub is kept to avoid import errors during migration.
 */
export function createSignature(): string {
  throw new Error("AWS Signature is not used in insMind mode");
}
