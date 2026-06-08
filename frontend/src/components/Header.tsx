"use client";

import { useEffect, useRef } from "react";
import { useScroll, useMotionValueEvent } from "motion/react";
import { Logo } from "@/components/ui/Logo";
import { navLinkCn } from "@/lib/styles";
import { HeaderRightCluster } from "@/components/HeaderRightCluster";
import { NavLink } from "@/components/nav/NavLink";
import { NAV_LINKS } from "@/lib/nav-links";

/**
 * Fixed top bar. Its background, border and blur are tied directly to the
 * scroll position (not a threshold toggle), so it fades transparent → lifted
 * dark surface gradually and reverses just as smoothly when scrolling back up.
 * Tune FADE_RANGE to make the transition span more/less scroll distance.
 */
const FADE_RANGE = 100; // px over which the header fully lifts

export default function Header() {
  const ref = useRef<HTMLElement>(null);
  const { scrollY } = useScroll();

  const apply = (y: number) => {
    const el = ref.current;
    if (!el) return;
    const t = Math.min(1, Math.max(0, y / FADE_RANGE)); // 0 at top → 1 once lifted
    el.style.backgroundColor = `rgba(14, 14, 16, ${0.9 * t})`;
    el.style.borderBottomColor = `rgba(31, 31, 34, ${t})`;
    const blur = `blur(${12 * t}px)`;
    el.style.backdropFilter = blur;
    el.style.setProperty("-webkit-backdrop-filter", blur);
  };

  useMotionValueEvent(scrollY, "change", apply);

  // Set the correct state on mount (handles loading already scrolled).
  useEffect(() => {
    apply(window.scrollY);
  }, []);

  return (
    <header
      ref={ref}
      className="fixed left-0 right-0 top-0 z-40 animate-fade-down border-b border-transparent"
    >
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:h-16 sm:px-6 lg:px-8">
        <Logo />

        {/* Right group: primary nav + auth cluster, end-aligned next to
            the Log In button. Mobile hamburger lives inside the cluster
            and renders alongside (the nav itself is `hidden md:flex`). */}
        <div className="flex items-center gap-1 md:gap-2">
          <nav className="hidden items-center gap-1 md:flex" aria-label="Primary navigation">
            {NAV_LINKS.map((link) => (
              <NavLink key={link.label} href={link.href} className={`px-4 py-2 ${navLinkCn}`}>
                {link.label}
              </NavLink>
            ))}
          </nav>

          <HeaderRightCluster />
        </div>
      </div>
    </header>
  );
}
