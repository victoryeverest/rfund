import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";
import { AuthProvider } from "@/lib/auth";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "RFUND — Save. Build. Grow.",
    template: "%s | RFUND",
  },
  description:
    "RFUND provides digital savings (Digital Ajo), rural loans and FarmerCash for traders, artisans, cooperatives and smallholder farmers in underserved communities.",
  keywords: [
    "RFUND", "Digital Ajo", "rural savings", "rural loans", "FarmerCash",
    "financial inclusion", "Nigeria", "cooperative savings",
  ],
  openGraph: {
    title: "RFUND — Save. Build. Grow.",
    description:
      "Digital savings, rural loans and FarmerCash for underserved communities in Nigeria.",
    siteName: "RFUND",
    type: "website",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#123328",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} font-sans antialiased bg-background text-foreground`}>
        <AuthProvider>
          {children}
        </AuthProvider>
        <Toaster />
      </body>
    </html>
  );
}
