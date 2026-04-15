import { Sidebar } from "@/components/dashboard/Sidebar";
import { DashboardContent } from "@/components/dashboard/DashboardContent";
import { UserProvider } from "@/context/user";
import { ThemeProvider } from "@/context/theme";
import { ThemeShell } from "@/components/dashboard/ThemeShell";

export const metadata = {
    title: "Dashboard — Roman Technologies",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    return (
        <ThemeProvider>
            <UserProvider>
                <ThemeShell>
                    <Sidebar />
                    <div className="flex-1 overflow-y-auto no-scrollbar">
                        <DashboardContent>{children}</DashboardContent>
                    </div>
                </ThemeShell>
            </UserProvider>
        </ThemeProvider>
    );
}
