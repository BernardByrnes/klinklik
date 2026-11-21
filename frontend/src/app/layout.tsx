import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KlinKlik",
  applicationName: "KlinKlik",
  description: "Modern clinic operations and patient management software.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="font-sans">{children}</body>
    </html>
  );
}
