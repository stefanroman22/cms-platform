"use client";

import { usePathname } from "next/navigation";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

export function SiteShell({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const isDashboard = pathname.startsWith("/dashboard");

    if (isDashboard) {
        return <>{children}</>;
    }

    return (
        <>
            <Header />
            <main className="min-h-screen pt-16">{children}</main>
            <Footer />
        </>
    );
}
