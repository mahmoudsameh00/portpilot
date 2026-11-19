import type { Metadata } from "next";
import { Geist, Geist_Mono, IBM_Plex_Sans_Arabic } from "next/font/google";
import { NextIntlClientProvider } from "next-intl";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

// Self-hosted at build time by next/font (no font request at run time; CSP font-src 'self'). MASTER §3.
// Geist for the interface; IBM Plex Sans Arabic only fills in when an answer is in Arabic.
const geist = Geist({ subsets: ["latin"], variable: "--font-geist", display: "swap" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap" });
const plexArabic = IBM_Plex_Sans_Arabic({
  subsets: ["arabic"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-arabic",
  display: "swap",
});

export const metadata: Metadata = { title: "PortPilot", robots: { index: false, follow: false } };

// Every page is rendered per request: the CSP nonce (src/proxy.ts) must reach Next's own scripts (plan §4.5).
export const dynamic = "force-dynamic";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: browser extensions (e.g. webcrx) add attributes to <html> before React loads; this
    // ignores attribute differences on this one element only, never on its children.
    <html
      lang="en"
      dir="ltr"
      className={`${geist.variable} ${geistMono.variable} ${plexArabic.variable}`}
      suppressHydrationWarning
    >
      <body>
        <NextIntlClientProvider>
          <TooltipProvider delayDuration={150}>{children}</TooltipProvider>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
