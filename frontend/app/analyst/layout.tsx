import "./analyst.css";
import { AppShell } from "@/components/app-shell";

export default function AnalystLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell role="analyst">{children}</AppShell>;
}
