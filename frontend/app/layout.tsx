// AI-generated with Claude (Anthropic).
import type { Metadata } from "next";
import { Instrument_Serif, Schibsted_Grotesk } from "next/font/google";
import { BRAND } from "@/lib/brand";
import "./globals.css";

const display = Instrument_Serif({ variable: "--font-display", subsets: ["latin"], weight: "400", style: ["normal", "italic"] });
const grotesk = Schibsted_Grotesk({ variable: "--font-grotesk", subsets: ["latin"] });

export const metadata: Metadata = {
  title: `${BRAND} · Weather hedging for small businesses`,
  description: "Pool opposite weather exposures and hedge the remainder on Gemini prediction markets.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${grotesk.variable}`}>
      <body>{children}</body>
    </html>
  );
}
