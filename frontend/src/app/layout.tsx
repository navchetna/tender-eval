import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { ToastProvider } from "@/components/ToastProvider";
import { AuthProvider } from "@/components/AuthProvider";

const intelOne = localFont({
  src: [
    { path: "../../public/fonts/intelone-display-regular.ttf", weight: "400", style: "normal" },
    { path: "../../public/fonts/intelone-display-medium.ttf", weight: "500", style: "normal" },
  ],
  variable: "--font-intelone",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Reconcile — tender ↔ bid",
  description: "Frontend for tender and bid document compliance.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`h-full antialiased ${intelOne.variable}`}>
      <body className="h-full font-sans text-ink">
        <AuthProvider>
          <ToastProvider>{children}</ToastProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
