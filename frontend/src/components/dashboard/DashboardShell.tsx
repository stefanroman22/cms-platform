"use client";

import { useState } from "react";
import { Sidebar } from "./Sidebar";
import { MobileNav } from "./MobileNav";
import { DashboardContent } from "./DashboardContent";

/** Top-level dashboard layout. Owns the mobile-drawer open/close state.
 *
 *  Desktop / tablet (md+): the existing sticky `<Sidebar>` remains exactly
 *  as it was, side-by-side with the scrollable content.
 *
 *  Mobile (< md): the desktop sidebar is hidden; a slim top bar with a
 *  hamburger button drives a slide-in drawer (framer-motion). Body scroll
 *  is locked while the drawer is open. ESC and backdrop-tap close it.
 */
export function DashboardShell({ children }: { children: React.ReactNode }) {
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  return (
    <>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <MobileNav
          open={mobileNavOpen}
          onOpen={() => setMobileNavOpen(true)}
          onClose={() => setMobileNavOpen(false)}
        />
        <div className="flex-1 overflow-y-auto no-scrollbar">
          <DashboardContent>{children}</DashboardContent>
        </div>
      </div>
    </>
  );
}
