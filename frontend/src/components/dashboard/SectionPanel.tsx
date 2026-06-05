"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";

interface SectionPanelProps {
  activeView: string;
  children: ReactNode;
}

/**
 * Wraps the active section body in the project's standard content-swap
 * animation (fade + 6px lift, mode="wait" so the old section fully exits
 * before the new one enters) — identical to ServiceGrid's tab swap.
 */
export function SectionPanel({ activeView, children }: SectionPanelProps) {
  return (
    <div
      role="tabpanel"
      id={`section-panel-${activeView}`}
      aria-labelledby={`section-tab-${activeView}`}
      className="min-w-0 flex-1"
    >
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={activeView}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.18, ease: [0.32, 0.72, 0, 1] }}
        >
          {children}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}
