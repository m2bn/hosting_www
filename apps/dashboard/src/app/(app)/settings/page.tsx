import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";

export default function SettingsPage() {
  return (
    <AppShell>
      <PageHeader title="Settings" description="Account, security, notification, and data protection controls." />
      <Card className="max-w-2xl">
        <CardHeader><CardTitle>Account settings</CardTitle></CardHeader>
        <CardContent className="grid gap-4">
          <Input label="Full name" defaultValue="Acme Admin" />
          <Input label="Email" defaultValue="admin@example.com" />
          <Button className="w-fit">Save changes</Button>
        </CardContent>
      </Card>
    </AppShell>
  );
}
