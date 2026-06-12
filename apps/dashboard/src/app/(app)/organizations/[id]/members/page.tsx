"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { OrganizationTabs } from "@/components/organizations/OrganizationTabs";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/Table";
import { fetchOrganization, fetchOrganizationMembers } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function OrganizationMembersPage() {
  const id = String(useParams().id);
  const org = useApiResource(() => fetchOrganization(id), [id]);
  const members = useApiResource(() => fetchOrganizationMembers(id), [id]);
  const canManageMembers = canAccess(org.data ?? undefined, "members:manage");

  return (
    <AppShell>
      <PageHeader
        title="Organization members"
        description="Manage tenant membership and organization-scoped roles."
        actions={canManageMembers ? <Button>Invite member</Button> : null}
      />
      <OrganizationTabs id={id} />
      {org.isLoading || members.isLoading ? <LoadingState label="Loading members..." /> : null}
      {org.error ? <ErrorState error={org.error} /> : null}
      {members.error ? <ErrorState error={members.error} /> : null}
      {members.data?.length === 0 ? <EmptyState title="No members" description="Members will appear after they are invited to this organization." /> : null}
      {members.data && members.data.length > 0 ? (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHead><tr><Th>Name</Th><Th>Email</Th><Th>Role</Th><Th>Status</Th><Th /></tr></TableHead>
              <TableBody>
                {members.data.map((member) => (
                  <tr key={member.id}>
                    <Td className="font-semibold">{member.name}</Td>
                    <Td>{member.email}</Td>
                    <Td>{member.role}</Td>
                    <Td><StatusBadge status={member.status} /></Td>
                    <Td>{canManageMembers ? <Button variant="secondary">Change role</Button> : null}</Td>
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
