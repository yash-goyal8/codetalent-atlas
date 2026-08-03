/**
 * Page-level formatting helpers that extend (never fork) `lib/format`.
 */

import { NO_VALUE } from "../../lib/format";

/** "2026-08-01T23:00:00Z" -> "2026-08-01 23:00 UTC". */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return NO_VALUE;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return NO_VALUE;
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())} ${pad(date.getUTCHours())}:${pad(date.getUTCMinutes())} UTC`;
}

/** Bytes -> human scale, e.g. 1_500_000_000 -> "1.5 GB". */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes == null || !Number.isFinite(bytes) || bytes < 0) return NO_VALUE;
  if (bytes >= 1e12) return `${(bytes / 1e12).toFixed(1)} TB`;
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${(bytes / 1e6).toFixed(1)} MB`;
  if (bytes >= 1e3) return `${(bytes / 1e3).toFixed(1)} kB`;
  return `${Math.round(bytes)} B`;
}
