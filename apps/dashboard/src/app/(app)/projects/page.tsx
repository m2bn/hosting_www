import { Button } from "@/components/ui/Button";
import { AppShell } from "@/components/layout/AppShell";
import { PageHeader } from "@/components/layout/PageHeader";
import { ProjectTable } from "@/components/dashboard/ProjectTable";

export default function ProjectsPage() {
  return (
    <AppShell>
      <PageHeader title="Projects" description="Projects are tenant-scoped runtime units with environments, domains, secrets, and deployments." actions={<Button>New project</Button>} />
      <ProjectTable />
    </AppShell>
  );
}
