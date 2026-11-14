import type { Metadata } from "next";
import { Montserrat } from "next/font/google";
import "./globals.css";

const brandFont = Montserrat({
  variable: "--font-brand",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PortfolioGuard AI",
  description: "Evidence-backed fictional portfolio comparison for AlphaForge AI",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-scroll-behavior="smooth">
      <body className={brandFont.variable}>{children}</body>
    </html>
  );
}
