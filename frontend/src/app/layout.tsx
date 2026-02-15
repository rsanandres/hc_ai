import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import { Providers } from "@/components/Providers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const description = 'Healthcare AI powered by retrieval-augmented generation with Claude 3.5 Sonnet & Haiku';

export const metadata: Metadata = {
  metadataBase: new URL('https://hcai.rsanandres.com'),
  title: 'HC AI — Healthcare RAG Demo by Raphael San Andres',
  description,
  openGraph: {
    title: 'HC AI — Healthcare RAG Demo',
    description,
    url: 'https://hcai.rsanandres.com',
    siteName: 'HC AI',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'HC AI — Healthcare RAG Demo',
    description,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        <Providers>
          {children}
        </Providers>
        <Analytics />
      </body>
    </html>
  );
}
