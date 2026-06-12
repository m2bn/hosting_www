"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProjectTabs } from "@/components/projects/ProjectTabs";
import { DeploymentLogs } from "@/components/deployments/DeploymentLogs";
import { isDeploymentInProgress } from "@/components/deployments/deployment-status";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Deployment, DeploymentLogLine, fetchProject, fetchProjectDeployment, fetchProjectDeploymentLogs, rollbackDeployment } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function DeploymentDetailPage() {
  const params = useParams();
  const projectId = String(params.id);
  const deploymentId = String(params.deploymentId);
  const project = useApiResource(() => fetchProject(projectId), [projectId]);
  const deployment = useApiResource(() => fetchProjectDeployment(projectId, deploymentId), [projectId, deploymentId]);
  const logs = useApiResource(() => fetchProjectDeploymentLogs(projectId, deploymentId), [projectId, deploymentId]);
  const [currentDeployment, setCurrentDeployment] = useState<Deployment | null>(null);
  const [currentLogs, setCurrentLogs] = useState<DeploymentLogLine[]>([]);
  const [actionError, setActionError] = useState("");
  const [isRollbackSubmitting, setIsRollbackSubmitting] = useState(false);
  const canDeploy = canAccess(project.data ?? undefined, "projects:deploy");

  useEffect(() => {
    if (deployment.data) {
      setCurrentDeployment(deployment.data);
    }
  }, [deployment.data]);

  useEffect(() => {
    if (logs.data) {
      setCurrentLogs(logs.data);
    }
  }, [logs.data]);

  useEffect(() => {
    if (!currentDeployment || !isDeploymentInProgress(currentDeployment.status)) {
      return undefined;
    }
    const interval = window.setInterval(() => {
      Promise.all([fetchProjectDeployment(projectId, deploymentId), fetchProjectDeploymentLogs(projectId, deploymentId)])
        .then(([nextDeployment, nextLogs]) => {
          setCurrentDeployment(nextDeployment);
          setCurrentLogs(nextLogs);
          setActionError("");
        })
        .catch(() => setActionError("Deployment status could not be refreshed."));
    }, 5000);
    return () => window.clearInterval(interval);
  }, [currentDeployment, deploymentId, projectId]);

  async function onRollback() {
    setActionError("");
    setIsRollbackSubmitting(true);
    try {
      setCurrentDeployment(await rollbackDeployment(projectId, deploymentId));
    } catch {
      setActionError("Rollback could not be started. Try again later.");
    } finally {
      setIsRollbackSubmitting(false);
    }
  }

  const canRollback = canDeploy && Boolean(currentDeployment?.can_rollback);

  return (
    <AppShell>
      <PageHeader title="Deployment details" description="Build status, deployment metadata, logs, and rollback controls." actions={canRollback ? <Button onClick={onRollback} disabled={isRollbackSubmitting}>{isRollbackSubmitting ? "Rolling back..." : "Rollback"}</Button> : null} />
      <ProjectTabs id={projectId} />
      {project.isLoading || deployment.isLoading || logs.isLoading ? <LoadingState label="Loading deployment details..." /> : null}
      {project.error ? <ErrorState error={project.error} /> : null}
      {deployment.error ? <ErrorState error={deployment.error} /> : null}
      {logs.error ? <ErrorState error={logs.error} /> : null}
      {actionError ? <Alert variant="warning">{actionError}</Alert> : null}
      {currentDeployment ? (
        <div className="grid gap-6">
          <Card>
            <CardHeader><CardTitle>{currentDeployment.version}</CardTitle></CardHeader>
            <CardContent className="grid gap-3 text-sm">
              <div className="flex justify-between gap-4"><span className="text-subdued">Status</span><StatusBadge status={currentDeployment.status} /></div>
              <div className="flex justify-between gap-4"><span className="text-subdued">Type</span><strong>{currentDeployment.type ?? "static"}</strong></div>
              <div className="flex justify-between gap-4"><span className="text-subdued">Created</span><strong>{currentDeployment.created_at}</strong></div>
              <div className="flex justify-between gap-4"><span className="text-subdued">Artifact</span><strong>{currentDeployment.artifact_name ?? currentDeployment.image_tag ?? "Not available"}</strong></div>
            </CardContent>
          </Card>
          <DeploymentLogs logs={currentLogs} />
        </div>
      ) : null}
      {!deployment.isLoading && !deployment.error && !currentDeployment ? <EmptyState title="Deployment unavailable" description="The deployment was not found or is not available to this account." /> : null}
    </AppShell>
  );
}
