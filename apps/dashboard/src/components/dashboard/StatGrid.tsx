import { Card, CardContent } from "@/components/ui/Card";

const stats = [
  { label: "Active projects", value: "12", trend: "+2 this week" },
  { label: "Deployments", value: "184", trend: "98.9% success" },
  { label: "Storage", value: "68 GB", trend: "42% of plan" },
  { label: "Open alerts", value: "3", trend: "1 high priority" },
];

export function StatGrid() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {stats.map((stat) => (
        <Card key={stat.label}>
          <CardContent>
            <p className="text-sm font-medium text-subdued">{stat.label}</p>
            <p className="mt-2 text-3xl font-bold text-ink">{stat.value}</p>
            <p className="mt-2 text-xs font-semibold text-brand-700">{stat.trend}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
