"use client";

import { useParams } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { OrganizationTabs } from "@/components/organizations/OrganizationTabs";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { fetchOrganization } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { useApiResource } from "@/hooks/useApiResource";

export default function OrganizationDetailPage() {
  const id = String(useParams().id);
  const { data, error, isLoading } = useApiResource(() => fetchOrganization(id), [id]);
  const canEdit = canAccess(data ?? undefined, "organization:update");
  const canDelete = canAccess(data ?? undefined, "organization:delete");

  return (
    <AppShell>
      <PageHeader
        title={data?.name ?? "Organization"}
        description="Organization overview, membership context, tenant-scoped projects, and RBAC-sensitive actions."
        actions={canEdit ? <Button>Edit organization</Button> : null}
      />
      <OrganizationTabs id={id} />
      {isLoading ? <LoadingState label="Loading organization..." /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data ? (
        <div className="grid gap-6 lg:grid-cols-3">
          <Card>
            <CardHeader><CardTitle>Overview</CardTitle></CardHeader>
            <CardContent className="grid gap-3 text-sm">
              <div className="flex justify-between gap-4"><span className="text-subdued">Status</span><StatusBadge status={data.status} /></div>
              <div className="flex justify-between gap-4"><span className="text-subdued">Your role</span><strong>{data.role}</strong></div>
              <div className="flex justify-between gap-4"><span className="text-subdued">Projects</span><strong>{data.projects_count ?? 0}</strong></div>
              <div className="flex justify-between gap-4"><span className="text-subdued">Members</span><strong>{data.members_count ?? 0}</strong></div>
            </CardContent>
          </Card>
          <Card className="lg:col-span-2">
            <CardHeader><CardTitle>Authorization boundary</CardTitle></CardHeader>
            <CardContent className="grid gap-4 text-sm leading-6 text-subdued">
              <p>Visible controls reflect your current role, but every operation must still be authorized by the API with organization context.</p>
              {canDelete ? <Button variant="danger" className="w-fit">Delete organization</Button> : null}
            </CardContent>
          </Card>
        </div>
      ) : null}
      {!isLoading && !error && !data ? <EmptyState title="Organization unavailable" description="The organization was not found or is not available to this account." /> : null}
    </AppShell>
  );
}
