import { Badge } from "@/components/ui/Badge";

function variantForStatus(status: string) {
  if (["active", "verified", "success", "succeeded"].includes(status)) {
    return "success" as const;
  }
  if (["pending", "queued", "building", "deploying", "pending_verification"].includes(status)) {
    return "warning" as const;
  }
  if (["failed", "disabled", "deleted", "canceled"].includes(status)) {
    return "danger" as const;
  }
  return "neutral" as const;
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={variantForStatus(status)}>{status.replaceAll("_", " ")}</Badge>;
}
