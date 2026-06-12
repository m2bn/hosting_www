"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProjectTabs } from "@/components/projects/ProjectTabs";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { DeploymentForms } from "@/components/deployments/DeploymentForms";
import { isDeploymentInProgress } from "@/components/deployments/deployment-status";
import { Alert } from "@/components/ui/Alert";
import { Card, CardContent } from "@/components/ui/Card";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/Table";
import { Deployment, fetchProject, fetchProjectDeployments } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function ProjectDeploymentsPage() {
  const id = String(useParams().id);
  const project = useApiResource(() => fetchProject(id), [id]);
  const deployments = useApiResource(() => fetchProjectDeployments(id), [id]);
  const [localDeployments, setLocalDeployments] = useState<Deployment[]>([]);
  const [pollError, setPollError] = useState("");
  const canDeploy = canAccess(project.data ?? undefined, "projects:deploy");

  useEffect(() => {
    if (deployments.data) {
      setLocalDeployments(deployments.data);
    }
  }, [deployments.data]);

  useEffect(() => {
    if (!localDeployments.some((deployment) => isDeploymentInProgress(deployment.status))) {
      return undefined;
    }
    const interval = window.setInterval(() => {
      fetchProjectDeployments(id)
        .then((nextDeployments) => {
          setLocalDeployments(nextDeployments);
          setPollError("");
        })
        .catch(() => setPollError("Deployment status could not be refreshed."));
    }, 5000);
    return () => window.clearInterval(interval);
  }, [id, localDeployments]);

  function onDeploymentCreated(deployment: Deployment) {
    setLocalDeployments((current) => [deployment, ...current]);
  }

  return (
    <AppShell>
      <PageHeader title="Deployments" description="Deployment history is scoped to this project." />
      <ProjectTabs id={id} />
      {project.isLoading || deployments.isLoading ? <LoadingState label="Loading deployments..." /> : null}
      {project.error ? <ErrorState error={project.error} /> : null}
      {deployments.error ? <ErrorState error={deployments.error} /> : null}
      {pollError ? <Alert variant="warning">{pollError}</Alert> : null}
      {canDeploy ? <DeploymentForms projectId={id} onCreated={onDeploymentCreated} /> : null}
      {!canDeploy && project.data ? <Alert variant="info">Your role can view deployments, but cannot start new deployments.</Alert> : null}
      {localDeployments.length === 0 && deployments.data ? <EmptyState title="No deployments" description="Deployments will appear after this project is released." /> : null}
      {localDeployments.length > 0 ? (
        <Card>
          <CardContent className="overflow-x-auto p-0">
            <Table>
              <TableHead><tr><Th>Version</Th><Th>Type</Th><Th>Status</Th><Th>Created</Th><Th>Actor</Th><Th /></tr></TableHead>
              <TableBody>
                {localDeployments.map((deployment) => (
                  <tr key={deployment.id}>
                    <Td className="font-semibold">{deployment.version}</Td>
                    <Td>{deployment.type ?? "static"}</Td>
                    <Td><StatusBadge status={deployment.status} /></Td>
                    <Td>{deployment.created_at}</Td>
                    <Td>{deployment.actor ?? "Platform"}</Td>
                    <Td><Link className="font-semibold text-brand-700" href={`/projects/${id}/deployments/${deployment.id}`}>Details</Link></Td>
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
