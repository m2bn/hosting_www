"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProjectTabs } from "@/components/projects/ProjectTabs";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/Table";
import { fetchProject, fetchProjectDomains } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function ProjectDomainsPage() {
  const id = String(useParams().id);
  const project = useApiResource(() => fetchProject(id), [id]);
  const domains = useApiResource(() => fetchProjectDomains(id), [id]);
  const canManageDomains = canAccess(project.data ?? undefined, "domains:manage");

  return (
    <AppShell>
      <PageHeader title="Domains" description="Custom domains and certificate status for this project." actions={canManageDomains ? <Button>Add domain</Button> : null} />
      <ProjectTabs id={id} />
      {project.isLoading || domains.isLoading ? <LoadingState label="Loading domains..." /> : null}
      {project.error ? <ErrorState error={project.error} /> : null}
      {domains.error ? <ErrorState error={domains.error} /> : null}
      {domains.data?.length === 0 ? <EmptyState title="No domains" description="Verified domains for this project will appear here." /> : null}
      {domains.data && domains.data.length > 0 ? (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHead><tr><Th>Hostname</Th><Th>Status</Th><Th>Certificate</Th><Th /></tr></TableHead>
              <TableBody>
                {domains.data.map((domain) => (
                  <tr key={domain.id}>
                    <Td className="font-semibold">{domain.hostname}</Td>
                    <Td><StatusBadge status={domain.status} /></Td>
                    <Td>{domain.certificate_status ? <StatusBadge status={domain.certificate_status} /> : "Not requested"}</Td>
                    <Td>{canManageDomains ? <Button variant="secondary">Verify</Button> : null}</Td>
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
