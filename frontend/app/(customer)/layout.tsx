import { AppShell } from "@/components/app-shell";
export default function CustomerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppShell role="customer">{children}</AppShell>;
}
