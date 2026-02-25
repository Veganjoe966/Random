import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hifdh Coach — Teacher Dashboard",
  description: "AI-assisted Qur'an memorization platform for teachers and administrators",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" dir="ltr" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
