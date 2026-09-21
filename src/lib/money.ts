/**
 * Money formatting — display only. The backend is authoritative for all
 * financial figures (§21, §103); the frontend never computes balances.
 */

export function parseMoney(value: string | number | null | undefined): number {
  if (value === null || value === undefined) return 0;
  const n = typeof value === "number" ? value : parseFloat(value);
  return Number.isFinite(n) ? n : 0;
}

export function formatNaira(
  value: string | number | null | undefined,
  options: { compact?: boolean; decimals?: boolean } = {}
): string {
  const n = parseMoney(value);
  if (options.compact && Math.abs(n) >= 1_000_000) {
    return `₦${(n / 1_000_000).toFixed(1)}M`;
  }
  if (options.compact && Math.abs(n) >= 100_000) {
    return `₦${(n / 1_000).toFixed(0)}k`;
  }
  return `₦${n.toLocaleString("en-NG", {
    minimumFractionDigits: options.decimals === false ? 0 : 2,
    maximumFractionDigits: options.decimals === false ? 0 : 2,
  })}`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value.includes("T") ? value : `${value}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleDateString("en-NG", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString("en-NG", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function titleize(value: string | null | undefined): string {
  if (!value) return "—";
  return value
    .toLowerCase()
    .split(/[_\s]+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

/** Trust UX (§136): pending operations show "processing", never success. */
export function statusTone(status: string): "success" | "warning" | "destructive" | "secondary" {
  const s = status.toUpperCase();
  if (["SUCCESS", "POSTED", "PAID", "COMPLETED", "VERIFIED", "ACTIVE", "SETTLED", "MATCHED", "ACCEPTED", "APPROVED", "CLEARED"].includes(s)) {
    return "success";
  }
  if (["PENDING", "PROCESSING", "INITIALIZED", "REQUESTED", "UNDER_REVIEW", "DUE", "UPCOMING", "SETTLEMENT_REQUESTED", "PENDING_SETTLEMENT", "INFO_REQUESTED", "WAITING_CUSTOMER"].includes(s)) {
    return "warning";
  }
  if (["FAILED", "REJECTED", "CANCELLED", "REVERSED", "MISSED", "LATE", "DELINQUENT", "DEFAULTED", "EXPIRED", "CONFIRMED"].includes(s)) {
    return "destructive";
  }
  return "secondary";
}
