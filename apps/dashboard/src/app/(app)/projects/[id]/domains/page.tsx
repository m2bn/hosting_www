"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProjectTabs } from "@/components/projects/ProjectTabs";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { DomainManager } from "@/components/domains/DomainManager";
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
      <PageHeader title="Domains" description="Custom domains, DNS verification, and certificate status for this project." />
      <ProjectTabs id={id} />
      {project.isLoading || domains.isLoading ? <LoadingState label="Loading domains..." /> : null}
      {project.error ? <ErrorState error={project.error} /> : null}
      {domains.error ? <ErrorState error={domains.error} /> : null}
      {domains.data?.length === 0 ? <EmptyState title="No domains" description="Verified domains for this project will appear here." /> : null}
      {domains.data && domains.data.length > 0 ? (
        <DomainManager projectId={id} domains={domains.data} canManageDomains={canManageDomains} />
      ) : null}
    </AppShell>
  );
}
