import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";

export default function AdminPage() {
  return (
    <AppShell>
      <PageHeader title="Admin" description="Operator-only surface for platform incidents, tenants, provisioning, and security events." />
      <div className="grid gap-6">
        <Alert variant="danger">UI visibility is not authorization. Backend operator permissions must enforce every admin action.</Alert>
        <Card>
          <CardHeader><CardTitle>Platform queue</CardTitle></CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <div className="flex justify-between"><span>Provisioning jobs</span><Badge variant="brand">12 queued</Badge></div>
            <div className="flex justify-between"><span>Failed webhooks</span><Badge variant="warning">2 open</Badge></div>
            <div className="flex justify-between"><span>Security events</span><Badge variant="danger">1 critical</Badge></div>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
