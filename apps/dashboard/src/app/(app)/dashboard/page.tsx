import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProjectTable } from "@/components/dashboard/ProjectTable";
import { StatGrid } from "@/components/dashboard/StatGrid";

export default function DashboardPage() {
  return (
    <AppShell>
      <PageHeader title="Dashboard" description="Operational overview for organizations, projects, deployments, billing, and platform health." actions={<Button>Deploy</Button>} />
      <div className="grid min-w-0 gap-6">
        <Alert variant="warning">One certificate renewal needs attention before the next maintenance window.</Alert>
        <StatGrid />
        <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <ProjectTable />
          <Card>
            <CardHeader>
              <CardTitle>Security posture</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm">
              <div className="flex justify-between"><span className="text-subdued">2FA admins</span><strong>Enabled</strong></div>
              <div className="flex justify-between"><span className="text-subdued">RBAC checks</span><strong>Active</strong></div>
              <div className="flex justify-between"><span className="text-subdued">Audit log</span><strong>Append-only</strong></div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}
