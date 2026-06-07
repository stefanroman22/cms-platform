"use client";

import { useState } from "react";
import { m, AnimatePresence } from "motion/react";
import { X, Bot, TrendingUp, ArrowUpRight } from "lucide-react";

/* NOTE for Stefan: replace /public/hero-mobile-demo-placeholder.mp4 with the
   real 5s silent screen-recording of the laptop opening. The modal below
   plays whatever lives at that path. */
const DEMO_SRC = "/hero-mobile-demo-placeholder.mp4";

export function MobileLaptopFallback() {
  const [open, setOpen] = useState(false);

  return (
    <section className="relative flex flex-col items-center bg-black px-6 pb-20 pt-4 text-center">
      <p className="mb-8 max-w-[34ch] text-[0.95rem] leading-relaxed text-text-secondary">
        A content system your customers never see — and you barely have to touch.
      </p>

      <div className="w-full max-w-[420px]">
        <StaticLaptop />
        <div className="mt-5 flex justify-center">
          <button
            onClick={() => setOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-[10px] border border-border bg-transparent px-4 py-2 text-[0.875rem] font-medium text-text-primary outline-none transition-colors hover:border-accent/50 hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
          >
            See it open
            <ArrowUpRight className="h-4 w-4 text-accent" strokeWidth={2} />
          </button>
        </div>
      </div>

      <AnimatePresence>
        {open && (
          <m.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-5 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          >
            <m.div
              initial={{ scale: 0.94, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.94, opacity: 0 }}
              transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
              className="relative w-full max-w-[640px] overflow-hidden rounded-[16px] border border-border bg-surface"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                onClick={() => setOpen(false)}
                aria-label="Close demo"
                className="absolute right-3 top-3 z-10 flex h-9 w-9 items-center justify-center rounded-full bg-black/50 text-text-primary outline-none transition-colors hover:bg-black/70 focus-visible:ring-2 focus-visible:ring-accent"
              >
                <X className="h-4 w-4" />
              </button>
              <video
                className="aspect-video w-full bg-black"
                src={DEMO_SRC}
                controls
                autoPlay
                muted
                loop
                playsInline
              >
                <p className="p-6 text-sm text-text-secondary">Demo video coming soon.</p>
              </video>
            </m.div>
          </m.div>
        )}
      </AnimatePresence>
    </section>
  );
}

/* Stylized open laptop built from DOM — crisp at any DPR, no asset needed. */
function StaticLaptop() {
  return (
    <div className="select-none">
      <div className="relative mx-auto w-full overflow-hidden rounded-[12px] border border-accent/30 bg-[#0E0E10] p-[3px] shadow-[0_30px_60px_-20px_rgba(0,0,0,0.8)]">
        <div className="overflow-hidden rounded-[9px]">
          <MiniCMS />
        </div>
      </div>
      <div className="mx-auto h-2.5 w-[112%] -translate-x-[5%] rounded-b-[10px] rounded-t-[3px] bg-gradient-to-b from-[#27272A] to-[#161618]" />
      <div className="mx-auto h-1 w-[18%] rounded-b-[4px] bg-[#0D0D0E]" />
    </div>
  );
}

function MiniCMS() {
  return (
    <div className="flex h-[210px] w-full bg-[#0E0E10] text-left text-text-primary">
      <div className="flex w-[42px] shrink-0 flex-col items-center gap-3 border-r border-white/[0.06] bg-[#0B0B0D] py-3">
        <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent text-[9px] font-bold text-bg">
          N
        </span>
        <span className="h-1.5 w-5 rounded-full bg-accent/70" />
        <span className="h-1.5 w-5 rounded-full bg-white/10" />
        <span className="h-1.5 w-5 rounded-full bg-white/10" />
        <span className="h-1.5 w-5 rounded-full bg-white/10" />
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-7 items-center justify-between border-b border-white/[0.06] px-2.5">
          <span className="h-1.5 w-14 rounded-full bg-white/12" />
          <span className="rounded bg-accent px-1.5 py-0.5 text-[7px] font-bold text-bg">
            Publish
          </span>
        </div>
        <div className="flex-1 px-2.5 py-2.5">
          <p className="text-[10px] font-semibold tracking-tight">Good morning, Lukas</p>
          <p className="mt-0.5 text-[7px] text-text-secondary">Café Nordlys · today</p>
          <div className="mt-2 grid grid-cols-2 gap-1.5">
            {[
              ["Bookings", "23"],
              ["Page views", "1,847"],
            ].map(([l, v]) => (
              <div key={l} className="rounded-md border border-white/[0.06] bg-white/[0.02] p-1.5">
                <p className="text-[6.5px] text-text-secondary">{l}</p>
                <div className="mt-0.5 flex items-center justify-between">
                  <span className="text-[12px] font-semibold leading-none">{v}</span>
                  <TrendingUp className="h-2.5 w-2.5 text-accent" strokeWidth={2.5} />
                </div>
              </div>
            ))}
          </div>
          <div className="mt-2 rounded-md border border-white/[0.06] bg-white/[0.02] p-1.5">
            <div className="flex items-center gap-1.5">
              <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-accent/15 text-accent">
                <Bot className="h-2 w-2" strokeWidth={2} />
              </span>
              <span className="h-1 flex-1 rounded-full bg-white/10" />
              <span className="rounded-full bg-accent/15 px-1 py-px text-[6px] font-bold uppercase text-accent">
                Auto
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
