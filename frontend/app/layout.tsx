import type { Metadata } from "next";
import "./globals.css";
import { SiteNav, StatusFooter } from "@/components/SiteNav";

export const metadata: Metadata = {
  title: "HHG Fraud Intelligence — Analyst Console",
  description:
    "Multi-module analyst console over the validated HHGoa 2026 Phase 3 case outputs: cases, investigation pipeline, model/XAI and system architecture.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex h-full flex-col">
        <SiteNav />
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
        <StatusFooter />
      </body>
    </html>
  );
}
