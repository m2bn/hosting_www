import { PageTabs } from "@/components/data/PageTabs";

export function ProjectTabs({ id }: { id: string }) {
  return (
    <PageTabs
      tabs={[
        { href: `/projects/${id}`, label: "Overview" },
        { href: `/projects/${id}/deployments`, label: "Deployments" },
        { href: `/projects/${id}/domains`, label: "Domains" },
        { href: `/projects/${id}/settings`, label: "Settings" },
      ]}
    />
  );
}
