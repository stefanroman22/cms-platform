"use client";

import { motion, AnimatePresence } from "framer-motion";

interface LoadingScreenProps {
  isVisible: boolean;
}

export function LoadingScreen({ isVisible }: LoadingScreenProps) {
  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          key="loading-screen"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3, ease: "easeOut" }}
          className="fixed inset-0 z-[9999] flex flex-col items-center justify-center"
          style={{ backgroundColor: "#080808", gap: "20px" }}
        >
          {/* Arc spinner */}
          <div className="relative" style={{ width: 68, height: 68 }}>
            {/* Dim track ring */}
            <div
              className="absolute inset-0 rounded-full"
              style={{ border: "1.5px solid rgba(255,255,255,0.07)" }}
            />
            {/* Comet arc — rotates continuously */}
            <motion.div
              className="absolute inset-0 rounded-full"
              animate={{ rotate: 360 }}
              transition={{ duration: 1.3, repeat: Infinity, ease: "linear" }}
              style={{
                background:
                  "conic-gradient(from 0deg, transparent 0deg, transparent 190deg, rgba(255,255,255,0.03) 210deg, rgba(255,255,255,0.1) 240deg, rgba(255,255,255,0.35) 278deg, rgba(255,255,255,0.78) 322deg, #ffffff 352deg, transparent 360deg)",
                WebkitMask:
                  "radial-gradient(farthest-side, transparent calc(100% - 1.5px), #000 calc(100% - 1.5px))",
                mask: "radial-gradient(farthest-side, transparent calc(100% - 1.5px), #000 calc(100% - 1.5px))",
              }}
            />
          </div>

          {/* Brand name */}
          <p
            className="m-0 select-none  text-sm font-semibold tracking-tight text-white"

          >
            Roman Technologies
          </p>

          {/* Shimmer progress line */}
          <div
            className="relative overflow-hidden"
            style={{
              width: 148,
              height: 1,
              backgroundColor: "rgba(255,255,255,0.07)",
            }}
          >
            <motion.div
              className="absolute inset-y-0 left-0"
              animate={{ x: ["-100%", "280%"] }}
              transition={{
                duration: 2.1,
                repeat: Infinity,
                ease: "easeInOut",
                repeatDelay: 0.35,
              }}
              style={{
                width: "42%",
                background:
                  "linear-gradient(to right, transparent, rgba(255,255,255,0.52), transparent)",
              }}
            />
          </div>

          {/* Loading label */}
          <p
            className="m-0 select-none uppercase"
            style={{
              fontFamily: "var(--font-geist-mono)",
              fontSize: "8.5px",
              letterSpacing: "0.14em",
              color: "rgba(255,255,255,0.27)",
            }}
          >
            Loading experience
          </p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
