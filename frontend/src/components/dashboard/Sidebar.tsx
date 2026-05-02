import { SidebarPanel } from "./SidebarPanel";

/** Desktop / tablet sidebar. Hidden on mobile (< md). Mobile users get the
 *  drawer via `<MobileNav>` instead. */
export function Sidebar() {
  return (
    <aside className="hidden md:flex w-60 shrink-0 h-screen sticky top-0 flex-col border-r border-zinc-200 dark:border-zinc-800">
      <SidebarPanel />
    </aside>
  );
}
