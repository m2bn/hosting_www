import Link from "next/link";

export const navigation = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/organizations", label: "Organizations" },
  { href: "/projects", label: "Projects" },
  { href: "/billing", label: "Billing" },
  { href: "/settings", label: "Settings" },
  { href: "/admin", label: "Admin" },
];

export function Sidebar() {
  return (
    <aside className="hidden min-h-screen w-64 border-r border-border bg-white lg:block">
      <div className="border-b border-border px-6 py-5">
        <Link href="/dashboard" className="text-lg font-bold text-ink">
          Hosting Control
        </Link>
        <p className="mt-1 text-xs font-medium text-subdued">SaaS platform dashboard</p>
      </div>
      <nav className="grid gap-1 px-3 py-4">
        {navigation.map((item) => (
          <Link key={item.href} href={item.href} className="rounded-md px-3 py-2 text-sm font-semibold text-subdued transition hover:bg-muted hover:text-ink">
            {item.label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
