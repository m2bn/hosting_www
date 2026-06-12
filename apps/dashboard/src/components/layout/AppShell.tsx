import { ReactNode } from "react";
import Link from "next/link";
import { navigation, Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-muted">
      <div className="flex min-h-screen">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <nav aria-label="Primary navigation" className="flex gap-2 overflow-x-auto border-b border-border bg-white px-4 py-2 lg:hidden">
            {navigation.map((item) => (
              <Link key={item.href} href={item.href} className="whitespace-nowrap rounded-md px-3 py-2 text-sm font-semibold text-subdued">
                {item.label}
              </Link>
            ))}
          </nav>
          <main className="mx-auto w-full max-w-7xl min-w-0 flex-1 px-4 py-6 lg:px-6">{children}</main>
        </div>
      </div>
    </div>
  );
}
