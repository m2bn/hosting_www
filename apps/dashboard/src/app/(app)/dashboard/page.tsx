"use client";

import Link from "next/link";
import { fetchDashboard } from "@/lib/platform-api";
import { canAccess } from "@/lib/rbac";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "@/components/data/ResourceStates";
import { StatusBadge } from "@/components/data/StatusBadge";
import { Table, TableBody, TableHead, Td, Th } from "@/components/ui/Table";
import { useApiResource } from "@/hooks/useApiResource";

export default function DashboardPage() {
  const { data, error, isLoading } = useApiResource(fetchDashboard, []);

  return (
    <AppShell>
      <PageHeader
        title="Dashboard"
        description="Operational overview for organizations, projects, deployments, billing, and platform health."
        actions={data && canAccess({ permissions: data.permissions }, "projects:create") ? <Button>New project</Button> : null}
      />
      {isLoading ? <LoadingState label="Loading organization dashboard..." /> : null}
      {error ? <ErrorState error={error} /> : null}
      {data ? (
        <div className="grid min-w-0 gap-6">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card><CardContent><p className="text-sm text-subdued">Organizations</p><strong className="mt-2 block text-3xl">{data.organizations_count}</strong></CardContent></Card>
            <Card><CardContent><p className="text-sm text-subdued">Projects</p><strong className="mt-2 block text-3xl">{data.projects_count}</strong></CardContent></Card>
            <Card><CardContent><p className="text-sm text-subdued">Deployments</p><strong className="mt-2 block text-3xl">{data.deployments_count}</strong></CardContent></Card>
            <Card><CardContent><p className="text-sm text-subdued">Failed deployments</p><strong className="mt-2 block text-3xl">{data.failed_deployments_count}</strong></CardContent></Card>
          </div>
          {data.recent_projects.length === 0 ? (
            <EmptyState title="No projects yet" description="Projects you can access will appear here after an organization creates them." />
          ) : (
            <Card>
              <CardHeader><CardTitle>Recent projects</CardTitle></CardHeader>
              <CardContent className="overflow-x-auto p-0">
                <Table>
                  <TableHead><tr><Th>Name</Th><Th>Organization</Th><Th>Status</Th><Th>Last deployment</Th><Th /></tr></TableHead>
                  <TableBody>
                    {data.recent_projects.map((project) => (
                      <tr key={project.id}>
                        <Td className="font-semibold">{project.name}</Td>
                        <Td>{project.organization_name ?? project.organization_id}</Td>
                        <Td><StatusBadge status={project.status} /></Td>
                        <Td>{project.last_deployment_at ?? "No deployments"}</Td>
                        <Td><Link className="font-semibold text-brand-700" href={`/projects/${project.id}`}>Open</Link></Td>
                      </tr>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
          <Card>
            <CardHeader>
              <CardTitle>Security posture</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm">
              <div className="flex justify-between"><span className="text-subdued">2FA admins</span><strong>Enabled</strong></div>
              <div className="flex justify-between"><span className="text-subdued">RBAC checks</span><strong>Active</strong></div>
              <div className="flex justify-between"><span className="text-subdued">Authorization</span><strong>Server enforced</strong></div>
            </CardContent>
          </Card>
        </div>
      ) : null}
    </AppShell>
  );
}
