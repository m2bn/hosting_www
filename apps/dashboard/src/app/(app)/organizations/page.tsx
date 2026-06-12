import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Card, CardContent } from "@/components/ui/Card";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/Table";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";

const organizations = [
  { name: "Acme Hosting", role: "owner", status: "active", projects: 8 },
  { name: "Northwind", role: "admin", status: "active", projects: 4 },
];

export default function OrganizationsPage() {
  return (
    <AppShell>
      <PageHeader title="Organizations" description="Organizations scope membership, RBAC, billing, projects, and audit trails." actions={<Button>New organization</Button>} />
      <Card>
        <CardContent className="overflow-x-auto p-0">
          <Table>
            <TableHead><tr><Th>Name</Th><Th>Your role</Th><Th>Status</Th><Th>Projects</Th></tr></TableHead>
            <TableBody>
              {organizations.map((org) => (
                <tr key={org.name}><Td className="font-semibold">{org.name}</Td><Td>{org.role}</Td><Td><Badge variant="success">{org.status}</Badge></Td><Td>{org.projects}</Td></tr>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </AppShell>
  );
}
