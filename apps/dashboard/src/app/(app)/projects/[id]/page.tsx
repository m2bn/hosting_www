"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProjectTabs } from "@/components/projects/ProjectTabs";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { fetchProject } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function ProjectDetailPage() {
  const id = String(useParams().id);
  const { data, error, isLoading } = useApiResource(() => fetchProject(id), [id]);
  const canDeploy = canAccess(data ?? undefined, "projects:deploy");
  const canEdit = canAccess(data ?? undefined, "projects:update");

  return (
    <AppShell>
      <PageHeader
        title={data?.name ?? "Project"}
        description="Project overview, runtime state, deployments, custom domains, and project-scoped settings."
        actions={canDeploy ? <Button>Deploy</Button> : null}
      />
      <ProjectTabs id={id} />
      {isLoading ? <LoadingState label="Loading project..." /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <Card>
            <CardHeader><CardTitle>Overview</CardTitle></CardHeader>
            <CardContent className="grid gap-3 text-sm">
              <div className="flex justify-between gap-4"><span className="text-subdued">Status</span><StatusBadge status={data.status} /></div>
              <div className="flex justify-between gap-4"><span className="text-subdued">Organization</span><strong>{data.organization_name ?? data.organization_id}</strong></div>
              <div className="flex justify-between gap-4"><span className="text-subdued">Deployments</span><strong>{data.deployments_count ?? 0}</strong></div>
              <div className="flex justify-between gap-4"><span className="text-subdued">Domains</span><strong>{data.domains_count ?? 0}</strong></div>
            </CardContent>
          </Card>
          <Card className="lg:col-span-2">
            <CardHeader><CardTitle>Authorization boundary</CardTitle></CardHeader>
            <CardContent className="grid gap-4 text-sm leading-6 text-subdued">
              <p>Project actions are hidden when your role lacks permission, but the API remains the enforcement point for tenant isolation.</p>
              {canEdit ? <Button variant="secondary" className="w-fit">Edit project</Button> : null}
            </CardContent>
          </Card>
        </div>
      ) : null}
      {!isLoading && !error && !data ? <EmptyState title="Project unavailable" description="The project was not found or is not available to this account." /> : null}
    </AppShell>
  );
}
