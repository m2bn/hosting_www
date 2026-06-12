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
import { fetchProject, fetchProjectDeployments } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function ProjectDeploymentsPage() {
  const id = String(useParams().id);
  const project = useApiResource(() => fetchProject(id), [id]);
  const deployments = useApiResource(() => fetchProjectDeployments(id), [id]);
  const canDeploy = canAccess(project.data ?? undefined, "projects:deploy");

  return (
    <AppShell>
      <PageHeader title="Deployments" description="Deployment history is scoped to this project." actions={canDeploy ? <Button>Deploy</Button> : null} />
      <ProjectTabs id={id} />
      {project.isLoading || deployments.isLoading ? <LoadingState label="Loading deployments..." /> : null}
      {project.error ? <ErrorState error={project.error} /> : null}
      {deployments.error ? <ErrorState error={deployments.error} /> : null}
      {deployments.data?.length === 0 ? <EmptyState title="No deployments" description="Deployments will appear after this project is released." /> : null}
      {deployments.data && deployments.data.length > 0 ? (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHead><tr><Th>Version</Th><Th>Status</Th><Th>Created</Th><Th>Actor</Th></tr></TableHead>
              <TableBody>
                {deployments.data.map((deployment) => (
                  <tr key={deployment.id}>
                    <Td className="font-semibold">{deployment.version}</Td>
                    <Td><StatusBadge status={deployment.status} /></Td>
                    <Td>{deployment.created_at}</Td>
                    <Td>{deployment.actor ?? "Platform"}</Td>
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
