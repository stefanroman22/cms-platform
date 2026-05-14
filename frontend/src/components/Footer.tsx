"use client";

import { motion } from "framer-motion";
import { Phone, Mail } from "lucide-react";
import { Logo } from "@/components/ui/Logo";
import { fadeUp, stagger } from "@/lib/animations";
import { dividerCn, sectionLabelCn } from "@/lib/styles";

/* ─── Data ───────────────────────────────────────────────────────────────── */

const CONTACT_ITEMS = [
  { href: "tel:+40751081184", icon: Phone, label: "+40751081184" },
  { href: "mailto:stefanromanpers@gmail.com", icon: Mail, label: "stefanromanpers@gmail.com" },
] as const;

/* ─── Component ──────────────────────────────────────────────────────────── */

export default function Footer() {
  return (
    <footer className="border-t border-white/[0.1] bg-black">
      <motion.div
        variants={stagger}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.5 }}
        className="mx-auto max-w-7xl px-4 py-10 sm:px-6 sm:py-14 lg:px-8 lg:py-16"
      >
        {/* ── Top: brand + contact ──────────────────────────────────────── */}
        <div className="flex flex-col gap-10 sm:flex-row sm:items-start sm:justify-between">
          {/* Brand */}
          <motion.div variants={fadeUp} className="flex flex-col gap-3">
            <Logo />
            <p className="max-w-[260px] text-sm leading-relaxed text-zinc-500">
              Premium software solutions for modern businesses.
            </p>
          </motion.div>

          {/* Contact */}
          <motion.div variants={fadeUp} className="flex flex-col gap-4">
            <p className={sectionLabelCn}>Contact</p>

            {CONTACT_ITEMS.map(({ href, icon: Icon, label }) => (
              <a
                key={href}
                href={href}
                className="group flex min-w-0 items-center gap-3 text-sm text-zinc-400 transition-colors duration-200 hover:text-white"
              >
                {/* Icon pill */}
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-white/5 transition-colors duration-200 group-hover:bg-white/10">
                  <Icon className="h-3.5 w-3.5 text-zinc-400 transition-colors duration-200 group-hover:text-white" />
                </span>
                {/* Label — break-all prevents long emails from overflowing on mobile */}
                <span className="break-all underline-offset-2 decoration-zinc-600 group-hover:underline">
                  {label}
                </span>
              </a>
            ))}
          </motion.div>
        </div>

        {/* ── Divider ───────────────────────────────────────────────────── */}
        <motion.div variants={fadeUp} className={`my-8 ${dividerCn}`} />

        {/* ── Copyright ─────────────────────────────────────────────────── */}
        <motion.p variants={fadeUp} className="text-center text-xs text-zinc-600">
          © {new Date().getFullYear()} Roman Technologies SRL. All rights reserved.
        </motion.p>
      </motion.div>
    </footer>
  );
}
