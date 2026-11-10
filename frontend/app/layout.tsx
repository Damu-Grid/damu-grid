import type { Metadata } from "next";
import { DM_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { AppRail } from "@/components/app-rail";
import { Providers } from "./providers";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Damu Grid",
  description:
    "Expiry-aware red cell redistribution review queue. Synthetic starter data, Terumo BCT Africa Hackathon 2026.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${dmSans.variable} ${plexMono.variable} grid min-h-screen font-sans text-[15px] antialiased md:grid-cols-[76px_minmax(0,1fr)]`}
      >
        <Providers>
          <AppRail />
          <main className="mx-auto w-full max-w-6xl px-4 py-6 md:px-8 md:py-8">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
