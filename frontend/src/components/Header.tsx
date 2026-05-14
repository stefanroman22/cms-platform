import Link from "next/link";
import { Logo } from "@/components/ui/Logo";
import { navLinkCn } from "@/lib/styles";
import { HeaderRightCluster } from "@/components/HeaderRightCluster";
import { NAV_LINKS } from "@/lib/nav-links";

/**
 * Server Component. Static markup ships as HTML, no JS needed to render
 * the bar or nav links. The right-hand cluster (mobile drawer + auth
 * badge) is a small client island, mounted once. Entrance animation is
 * pure CSS (`.animate-fade-down` from globals.css).
 */
export default function Header() {
  return (
    <header className="fixed left-0 right-0 top-0 z-40 animate-fade-down border-b border-white/[0.1] bg-black">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:h-16 sm:px-6 lg:px-8">
        <Logo />

        {/* Right group: primary nav + auth cluster, end-aligned next to
            the Log In button. Mobile hamburger lives inside the cluster
            and renders alongside (the nav itself is `hidden md:flex`). */}
        <div className="flex items-center gap-1 md:gap-2">
          <nav className="hidden items-center gap-1 md:flex" aria-label="Primary navigation">
            {NAV_LINKS.map((link) => (
              <Link key={link.label} href={link.href} className={`px-4 py-2 ${navLinkCn}`}>
                {link.label}
              </Link>
            ))}
          </nav>

          <HeaderRightCluster />
        </div>
      </div>
    </header>
  );
}
