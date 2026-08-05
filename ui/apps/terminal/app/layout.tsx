import type { Metadata, Viewport } from 'next';
import { Inter, IBM_Plex_Mono } from 'next/font/google';
import './globals.css';
import { cn } from "@/lib/utils";

const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-inter',
  display: 'swap',
});

const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-plex-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'KAIRO — Autonomous AI Trading System',
  description: 'KAIRO — Autonomous AI Trading Operating System. Safety gate always on.',
};

export const viewport: Viewport = {
  themeColor: '#08080B',
  colorScheme: 'dark',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={cn("dark", inter.variable, plexMono.variable, "font-sans")}>
      <body>{children}</body>
    </html>
  );
}
