import Link from "next/link";
import { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";

type AuthCardProps = {
  title: string;
  description: string;
  children: ReactNode;
  footer?: ReactNode;
};

export function AuthCard({ title, description, children, footer }: AuthCardProps) {
  return (
    <main className="grid min-h-screen place-items-center bg-muted px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <Link href="/dashboard" className="text-sm font-semibold text-brand-700">
            Hosting Control
          </Link>
          <CardTitle className="mt-3 text-xl">{title}</CardTitle>
          <p className="mt-1 text-sm leading-6 text-subdued">{description}</p>
        </CardHeader>
        <CardContent>
          {children}
          {footer ? <div className="mt-5 text-sm text-subdued">{footer}</div> : null}
        </CardContent>
      </Card>
    </main>
  );
}
