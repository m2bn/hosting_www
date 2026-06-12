import { UsageMetric } from "@/lib/platform-api";

function percentUsed(metric: UsageMetric): number {
  if (metric.limit <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((metric.used / metric.limit) * 100));
}

export function UsageList({ usage }: { usage: UsageMetric[] }) {
  return (
    <div className="grid gap-4">
      {usage.map((metric) => {
        const percent = percentUsed(metric);
        return (
          <div key={metric.key} className="grid gap-2">
            <div className="flex items-center justify-between gap-4 text-sm">
              <span className="font-semibold text-ink">{metric.label}</span>
              <span className="text-subdued">
                {metric.used} / {metric.limit} {metric.unit}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-brand-600" style={{ width: `${percent}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
