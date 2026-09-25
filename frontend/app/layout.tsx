import type { Metadata } from "next";
import "./globals.css";
import { SiteNav, StatusFooter } from "@/components/SiteNav";

export const metadata: Metadata = {
  title: "Gravex — Agentic Fraud Investigation Console",
  description:
    "Gravex: graph-grounded agentic fraud investigation over the validated HHGoa 2026 Phase 3 case outputs — cases, investigation pipeline, model/XAI and system architecture.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex h-full flex-col">
        {/* self-hosted Clash Display / Switzer / DM Mono (public/fonts) */}
        <link rel="stylesheet" href="/fonts/fonts.css" precedence="default" />
        {/* aurora + grain field the glass surfaces blur */}
        <div className="page-field" aria-hidden="true" />
        <SiteNav />
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
        <StatusFooter />
      </body>
    </html>
  );
}
