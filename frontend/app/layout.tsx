import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "AegisBank — Banking, intelligently protected",
    template: "%s · AegisBank",
  },
  description:
    "A complete, governed agentic banking workspace. Smart money, human control.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
