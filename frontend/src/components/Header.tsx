"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, User } from "lucide-react";
import { Logo } from "@/components/ui/Logo";
import {
  backdrop,
  drawerRight,
  fadeIn,
  staggerFast,
} from "@/lib/animations";
import { ctaButtonCn, navLinkCn } from "@/lib/styles";
import { useAuth } from "@/context/auth";

/* ─── Data ───────────────────────────────────────────────────────────────── */

const NAV_LINKS = [
  { label: "Home", href: "/" },
  { label: "About", href: "/about" },
  { label: "Contact", href: "/contact" },
];

/* ─── Component ──────────────────────────────────────────────────────────── */

export default function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { isLoggedIn } = useAuth();

  const close = () => setMobileOpen(false);

  // Lock body scroll while drawer is open
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  return (
    <>
      {/* ── Header bar ───────────────────────────────────────────────────────
          z-40 sits below the drawer (z-51) so the drawer correctly overlays it.
          bg-black is fully opaque — avoids the blue backdrop-filter flash that
          semi-transparent backgrounds produce during the opacity animation.   */}
      <motion.header
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.4 }}
        className="fixed left-0 right-0 top-0 z-40 border-b border-white/[0.1] bg-black"
      >
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:h-16 sm:px-6 lg:px-8 border-">
          {/* Mobile Logo */}
          <div className="flex md:hidden">
            <Logo />
          </div>

          {/* Desktop Logo */}
          <motion.div
            initial={{ y: -20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.4, delay: 0.1 }}
            className="hidden md:flex"
          >
            <Logo />
          </motion.div>

          {/* ── Desktop nav (md and above) ───────────────────────────────── */}
          <nav
            className="hidden items-center gap-1 md:flex"
            aria-label="Primary navigation"
          >
            {NAV_LINKS.map((link, index) => (
              <motion.div
                key={link.label}
                initial={{ y: -20, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.2 + index * 0.1 }}
              >
                <Link href={link.href} className={`px-4 py-2 ${navLinkCn}`}>
                  {link.label}
                </Link>
              </motion.div>
            ))}

            <motion.div
              initial={{ y: -20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ duration: 0.4, delay: 0.2 + NAV_LINKS.length * 0.1 }}
              className="ml-2 relative h-8 w-8"
            >
              <AnimatePresence mode="wait">
                {isLoggedIn ? (
                  <motion.div
                    key="user-icon"
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{ duration: 0.2 }}
                    className="absolute inset-0"
                  >
                    <button
                      onClick={() => window.open("/dashboard", "cms-dashboard")}
                      className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-white transition-colors hover:bg-white/20"
                      aria-label="Open dashboard"
                    >
                      <User className="h-4 w-4 cursor-pointer" />
                    </button>
                  </motion.div>
                ) : (
                  <motion.div
                    key="login-btn"
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{ duration: 0.2 }}
                    className="absolute inset-0 flex items-center"
                  >
                    <Link href="/log-in" className={ctaButtonCn}>
                      Log In
                    </Link>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          </nav>

          {/* ── Hamburger (below md) ─────────────────────────────────────── */}
          <button
            onClick={() => setMobileOpen(true)}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-zinc-400 transition-colors duration-200 hover:bg-white/5 hover:text-white md:hidden"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>
        </div>
      </motion.header>

      {/* ── Drawer + backdrop (portal-style siblings in the fragment) ────────
          Stacking order: backdrop z-50 > header z-40 (dims the page behind).
          Drawer z-51 > backdrop z-50 (panel sits on top of everything).       */}
      <AnimatePresence>
        {mobileOpen && (
          <>
            {/* Dimmed backdrop — clicking it closes the drawer */}
            <motion.div
              key="backdrop"
              variants={backdrop}
              initial="hidden"
              animate="visible"
              exit="exit"
              onClick={close}
              className="fixed inset-0 z-50 bg-black/60 md:hidden"
              aria-hidden="true"
            />

            {/* Drawer panel — slides in from the right edge */}
            <motion.div
              key="drawer"
              variants={drawerRight}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed right-0 top-0 z-[51] flex h-dvh w-4/5 max-w-sm flex-col border-l border-white/[0.08] bg-zinc-950 sm:w-3/5 md:hidden"
            >
              {/* Drawer top bar: logo left, close button right */}
              <div className="flex h-14 shrink-0 items-center justify-between border-b border-white/[0.06] px-4 sm:h-16">
                <Logo />
                <button
                  onClick={close}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-zinc-400 transition-colors duration-200 hover:bg-white/5 hover:text-white"
                  aria-label="Close menu"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Nav links */}
              <motion.nav
                variants={staggerFast}
                initial="hidden"
                animate="visible"
                className="flex flex-col gap-1 p-4"
                aria-label="Mobile navigation"
              >
                {NAV_LINKS.map((link) => (
                  <motion.div key={link.label} variants={fadeIn}>
                    <Link
                      href={link.href}
                      onClick={close}
                      className={`block rounded-lg px-4 py-3 text-base ${navLinkCn}`}
                    >
                      {link.label}
                    </Link>
                  </motion.div>
                ))}

                {/* CTA — inline-flex keeps it at natural width, never stretches */}
                <motion.div variants={fadeIn} className="pt-4">
                  <Link href="/contact" onClick={close} className={ctaButtonCn}>
                    Get in touch
                  </Link>
                </motion.div>
              </motion.nav>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
