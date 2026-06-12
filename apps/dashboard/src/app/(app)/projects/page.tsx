"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/Table";
import { fetchDashboard } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function ProjectsPage() {
  const { data, error, isLoading } = useApiResource(fetchDashboard, []);
  const canCreateProject = data ? canAccess({ permissions: data.permissions }, "projects:create") : false;

  return (
    <AppShell>
      <PageHeader
        title="Projects"
        description="Projects are tenant-scoped runtime units with environments, domains, secrets, and deployments."
        actions={canCreateProject ? <Button>New project</Button> : null}
      />
      {isLoading ? <LoadingState label="Loading projects..." /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data?.recent_projects.length === 0 ? <EmptyState title="No projects" description="Projects you can access will appear here." /> : null}
      {data && data.recent_projects.length > 0 ? (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHead><tr><Th>Name</Th><Th>Organization</Th><Th>Status</Th><Th>Deployments</Th><Th>Storage</Th><Th /></tr></TableHead>
              <TableBody>
                {data.recent_projects.map((project) => (
                  <tr key={project.id}>
                    <Td className="font-semibold">{project.name}</Td>
                    <Td>{project.organization_name ?? project.organization_id}</Td>
                    <Td><StatusBadge status={project.status} /></Td>
                    <Td>{project.deployments_count ?? 0}</Td>
                    <Td>{project.storage_gb ?? 0} GB</Td>
                    <Td><Link href={`/projects/${project.id}`} className="font-semibold text-brand-700">Open</Link></Td>
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
