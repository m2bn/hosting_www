"use client";

import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/Table";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { fetchOrganizations } from "@/lib/platform-api";
import { canAny } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";
import Link from "next/link";

export default function OrganizationsPage() {
  const { data, error, isLoading } = useApiResource(fetchOrganizations, []);
  const canCreateOrganization = data?.some((organization) => canAny(organization, ["organization:update", "members:manage"])) ?? false;

  return (
    <AppShell>
      <PageHeader
        title="Organizations"
        description="Organizations scope membership, RBAC, billing, projects, and audit trails."
        actions={canCreateOrganization ? <Button>New organization</Button> : null}
      />
      {isLoading ? <LoadingState label="Loading organizations..." /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data?.length === 0 ? <EmptyState title="No organizations" description="Organizations you belong to will appear here." /> : null}
      {data && data.length > 0 ? (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHead><tr><Th>Name</Th><Th>Your role</Th><Th>Status</Th><Th>Projects</Th><Th /></tr></TableHead>
              <TableBody>
                {data.map((org) => (
                  <tr key={org.id}>
                    <Td className="font-semibold">{org.name}</Td>
                    <Td>{org.role}</Td>
                    <Td><StatusBadge status={org.status} /></Td>
                    <Td>{org.projects_count ?? 0}</Td>
                    <Td><Link className="font-semibold text-brand-700" href={`/organizations/${org.id}`}>Open</Link></Td>
                  </tr>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      ) : null}
    </AppShell>
  );
}
