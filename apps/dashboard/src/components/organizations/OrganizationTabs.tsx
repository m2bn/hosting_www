import { PageTabs } from "@/components/data/PageTabs";

export function OrganizationTabs({ id }: { id: string }) {
  return (
    <PageTabs
      tabs={[
        { href: `/organizations/${id}`, label: "Overview" },
        { href: `/organizations/${id}/members`, label: "Members" },
        { href: `/organizations/${id}/projects`, label: "Projects" },
      ]}
    />
  );
}
