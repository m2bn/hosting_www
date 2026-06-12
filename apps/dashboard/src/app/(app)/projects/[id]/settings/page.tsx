"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProjectTabs } from "@/components/projects/ProjectTabs";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { fetchProject, fetchProjectSettings } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function ProjectSettingsPage() {
  const id = String(useParams().id);
  const project = useApiResource(() => fetchProject(id), [id]);
  const settings = useApiResource(() => fetchProjectSettings(id), [id]);
  const canUpdate = canAccess(project.data ?? undefined, "projects:update");

  return (
    <AppShell>
      <PageHeader title="Project settings" description="Read-only project settings until a role with project management permission is present." actions={canUpdate ? <Button>Save changes</Button> : null} />
      <ProjectTabs id={id} />
      {project.isLoading || settings.isLoading ? <LoadingState label="Loading project settings..." /> : null}
      {project.error ? <ErrorState error={project.error} /> : null}
      {settings.error ? <ErrorState error={settings.error} /> : null}
      {settings.data ? (
        <Card>
          <CardHeader><CardTitle>Configuration</CardTitle></CardHeader>
          <CardContent className="grid gap-3 text-sm">
            <div className="flex justify-between gap-4"><span className="text-subdued">Name</span><strong>{settings.data.name}</strong></div>
            <div className="flex justify-between gap-4"><span className="text-subdued">Slug</span><strong>{settings.data.slug ?? "Not set"}</strong></div>
            <div className="flex justify-between gap-4"><span className="text-subdued">Runtime</span><strong>{settings.data.runtime ?? "static"}</strong></div>
            <div className="flex justify-between gap-4"><span className="text-subdued">Environments</span><strong>{settings.data.environment_count ?? 0}</strong></div>
          </CardContent>
        </Card>
      ) : null}
      {!project.isLoading && !settings.isLoading && !project.error && !settings.error && !settings.data ? (
        <EmptyState title="Settings unavailable" description="Settings could not be found for this project." />
      ) : null}
    </AppShell>
  );
}
