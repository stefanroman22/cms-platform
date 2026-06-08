"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, User } from "lucide-react";
import { Logo } from "@/components/ui/Logo";
import { backdrop, drawerRight, fadeIn, staggerFast } from "@/lib/animations";
import { ctaButtonCn, navLinkCn } from "@/lib/styles";
import { useAuth } from "@/context/auth";
import { NavLink } from "@/components/nav/NavLink";
import { NAV_LINKS } from "@/lib/nav-links";

export function HeaderRightCluster() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { isLoggedIn } = useAuth();
  const close = () => setMobileOpen(false);

  useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  return (
    <>
      {/* Desktop auth slot — fades in once auth state resolves */}
      <div className="relative ml-2 hidden h-8 w-8 md:block">
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
      </div>

      {/* Mobile hamburger */}
      <button
        onClick={() => setMobileOpen(true)}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-zinc-400 transition-colors duration-200 hover:bg-white/5 hover:text-white md:hidden"
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      <AnimatePresence>
        {mobileOpen && (
          <>
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
            <motion.div
              key="drawer"
              variants={drawerRight}
              initial="hidden"
              animate="visible"
              exit="exit"
              className="fixed right-0 top-0 z-[51] flex h-dvh w-4/5 max-w-sm flex-col border-l border-white/[0.08] bg-zinc-950 sm:w-3/5 md:hidden"
            >
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

              <motion.nav
                variants={staggerFast}
                initial="hidden"
                animate="visible"
                className="flex flex-col gap-1 p-4"
                aria-label="Mobile navigation"
              >
                {NAV_LINKS.map((link) => (
                  <motion.div key={link.label} variants={fadeIn}>
                    <NavLink
                      href={link.href}
                      onNavigate={close}
                      className={`block rounded-lg px-4 py-3 text-base ${navLinkCn}`}
                    >
                      {link.label}
                    </NavLink>
                  </motion.div>
                ))}

                <motion.div variants={fadeIn} className="pt-4">
                  {isLoggedIn ? (
                    <button
                      type="button"
                      onClick={() => {
                        close();
                        window.open("/dashboard", "cms-dashboard");
                      }}
                      className={ctaButtonCn}
                    >
                      Open Dashboard
                    </button>
                  ) : (
                    <Link href="/log-in" onClick={close} className={ctaButtonCn}>
                      Log In
                    </Link>
                  )}
                </motion.div>

                <motion.div variants={fadeIn} className="pt-2">
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
