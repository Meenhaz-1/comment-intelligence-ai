import type { Metadata } from "next";

import { NavigationProgressProvider } from "@/components/navigation/navigation-progress";

import "./globals.css";

export const metadata: Metadata = {
  title: "Recipe Intelligence",
  description: "Internal dashboard for editorial recipe performance.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>
        <NavigationProgressProvider>{children}</NavigationProgressProvider>
      </body>
    </html>
  );
}
