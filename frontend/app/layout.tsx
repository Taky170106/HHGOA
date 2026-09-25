import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HHG Fraud Intelligence — Analyst Console",
  description:
    "Local analyst dashboard over the validated HHGoa 2026 Phase 3 case outputs.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="h-full flex flex-col">{children}</body>
    </html>
  );
}
