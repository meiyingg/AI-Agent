import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/theme-provider";
import { Toaster } from "@/components/toaster";
import { Intro } from "@/components/intro";
import { AuthProvider } from "@/lib/auth";
import { NotificationsProvider } from "@/lib/notifications";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Foodsta Kitchens AI Advisor",
  description: "Multi-Agent · Advanced RAG · Long-term Memory — AI operations & decision advisor for cloud kitchens",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <ThemeProvider>
          <AuthProvider>
            <NotificationsProvider>
              {children}
              <Toaster />
            </NotificationsProvider>
          </AuthProvider>
        </ThemeProvider>
        {/* 启动出场动画：覆盖全屏(含登录页)，播完/点击/跳过后淡出 */}
        <Intro />
      </body>
    </html>
  );
}
