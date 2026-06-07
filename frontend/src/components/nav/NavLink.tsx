"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { scrollToHash } from "@/lib/scroll";

/**
 * Navigation link shared by the desktop header and mobile drawer. For in-page
 * section links ("/#projects") it smooth-scrolls when already on that page, and
 * otherwise lets Next.js navigate to the route+hash (LenisProvider scrolls to
 * the section once the page mounts). Plain route links ("/about") behave as
 * normal <Link>s. `onNavigate` lets the mobile drawer close on click.
 */
export function NavLink({
  href,
  className,
  onNavigate,
  children,
}: {
  href: string;
  className?: string;
  onNavigate?: () => void;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const hashIndex = href.indexOf("#");
  const isAnchor = hashIndex !== -1;

  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (isAnchor) {
      const path = href.slice(0, hashIndex) || "/";
      const hash = href.slice(hashIndex + 1);
      if (pathname === path) {
        e.preventDefault();
        scrollToHash(hash);
      }
    }
    onNavigate?.();
  };

  return (
    <Link href={href} className={className} onClick={handleClick}>
      {children}
    </Link>
  );
}
