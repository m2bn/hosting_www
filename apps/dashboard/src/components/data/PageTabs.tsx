import Link from "next/link";

type PageTab = {
  href: string;
  label: string;
};

export function PageTabs({ tabs }: { tabs: PageTab[] }) {
  return (
    <nav aria-label="Section navigation" className="mb-6 flex gap-2 overflow-x-auto border-b border-border">
      {tabs.map((tab) => (
        <Link key={tab.href} href={tab.href} className="whitespace-nowrap px-3 py-2 text-sm font-semibold text-subdued hover:text-ink">
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
