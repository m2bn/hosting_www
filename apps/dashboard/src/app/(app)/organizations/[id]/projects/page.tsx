"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { OrganizationTabs } from "@/components/organizations/OrganizationTabs";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/Table";
import { fetchOrganization, fetchOrganizationProjects } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function OrganizationProjectsPage() {
  const id = String(useParams().id);
  const org = useApiResource(() => fetchOrganization(id), [id]);
  const projects = useApiResource(() => fetchOrganizationProjects(id), [id]);
  const canCreateProject = canAccess(org.data ?? undefined, "projects:create");

  return (
    <AppShell>
      <PageHeader
        title="Organization projects"
        description="Projects are listed only within the current organization context."
        actions={canCreateProject ? <Button>New project</Button> : null}
      />
      <OrganizationTabs id={id} />
      {org.isLoading || projects.isLoading ? <LoadingState label="Loading organization projects..." /> : null}
      {org.error ? <ErrorState error={org.error} /> : null}
      {projects.error ? <ErrorState error={projects.error} /> : null}
      {projects.data?.length === 0 ? <EmptyState title="No projects" description="This organization does not have any visible projects yet." /> : null}
      {projects.data && projects.data.length > 0 ? (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHead><tr><Th>Name</Th><Th>Status</Th><Th>Deployments</Th><Th>Domains</Th><Th /></tr></TableHead>
              <TableBody>
                {projects.data.map((project) => (
                  <tr key={project.id}>
                    <Td className="font-semibold">{project.name}</Td>
                    <Td><StatusBadge status={project.status} /></Td>
                    <Td>{project.deployments_count ?? 0}</Td>
                    <Td>{project.domains_count ?? 0}</Td>
                    <Td><Link className="font-semibold text-brand-700" href={`/projects/${project.id}`}>Open</Link></Td>
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
