import { UserProvider } from "@/context/user";
import { ThemeProvider } from "@/context/theme";
import { ThemeShell } from "@/components/dashboard/ThemeShell";
import { DashboardShell } from "@/components/dashboard/DashboardShell";

export const metadata = {
  title: "Dashboard — Roman Technologies",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <UserProvider>
        <ThemeShell>
          <DashboardShell>{children}</DashboardShell>
        </ThemeShell>
      </UserProvider>
    </ThemeProvider>
  );
}
