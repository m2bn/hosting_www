import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SaaS Hosting Dashboard",
  description: "Control plane dashboard for SaaS hosting platform",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
