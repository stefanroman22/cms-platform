"use client";

import { useRef, useState, useEffect } from "react";
import dynamic from "next/dynamic";
import {
  LazyMotion,
  domAnimation,
  m,
  AnimatePresence,
  useScroll,
  useInView,
  useMotionValueEvent,
  useReducedMotion,
  type MotionValue,
} from "motion/react";
import Snap from "lenis/snap";
import { cn } from "@/lib/utils";
import { useIsDesktop } from "@/hooks/useIsDesktop";
import { subscribeProgrammaticScroll } from "@/lib/scroll";
import { useLenisInstance } from "@/components/providers/LenisProvider";
import { MobileLaptopFallback } from "./MobileLaptopFallback";
import { progressToFeature, SCREEN_MOUNT_AT, FEATURE_START, FEATURE_COUNT } from "./showcase";

function HeroSceneSkeleton() {
  return <div className="absolute inset-0" aria-hidden="true" />;
}

const LaptopScene = dynamic(() => import("./LaptopScene"), {
  ssr: false,
  loading: () => <HeroSceneSkeleton />,
});

const SR_DESCRIPTION =
  "Decorative animation of a laptop opening to reveal the Roman Technologies content management system in use by Café Nordlys, a sample client.";

const EXPO = [0.16, 1, 0.3, 1] as const;

// Each caption owns a scroll segment; sides alternate left → right → left → right
// and sit in the outer margins so they never cover the laptop screen.
const CAPTIONS: { text: string; side: "left" | "right" }[] = [
  { text: "Manage your projects in one place", side: "left" },
  {
    text: "Change content and adjust your project yourself 24/7 using our agentic software",
    side: "right",
  },
  { text: "Hosted, secured, monitored — by us.", side: "left" },
  { text: "Every major release is human-reviewed to ensure correctness", side: "right" },
];

/** True only while a scrollToHash() jump is animating. Lets scroll-linked
 *  scenes freeze instead of scrubbing through their whole timeline. */
function useProgrammaticScroll() {
  const [active, setActive] = useState(false);
  useEffect(() => subscribeProgrammaticScroll(setActive), []);
  return active;
}

function ShowcaseCaptions({
  progress,
  reducedMotion,
  frozen,
}: {
  progress: MotionValue<number>;
  reducedMotion: boolean;
  frozen: boolean;
}) {
  const [active, setActive] = useState(reducedMotion ? 0 : -1);

  // reducedMotion resolves post-mount (SSR-safe gate); show the first caption.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: sync once when the post-mount media query resolves
    if (reducedMotion) setActive(0);
  }, [reducedMotion]);

  useMotionValueEvent(progress, "change", (p) => {
    // While a button-driven jump flies past this section, hold the current
    // caption instead of flashing through all of them.
    if (reducedMotion || frozen) return;
    // Same mapping the laptop screen uses, so caption ↔ shown feature stay in sync.
    setActive(p >= SCREEN_MOUNT_AT ? progressToFeature(p) : -1);
  });

  const side = active >= 0 ? CAPTIONS[active].side : "left";
  const dx = side === "left" ? -28 : 28;

  return (
    <div className="pointer-events-none absolute inset-0 z-10" aria-hidden="true">
      <AnimatePresence mode="wait">
        {active >= 0 && (
          <m.p
            key={active}
            initial={{ opacity: 0, x: dx }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: dx }}
            transition={{ duration: 0.55, ease: EXPO }}
            className={cn(
              "absolute top-1/2 max-w-[15rem] -translate-y-1/2 font-display text-[1.3rem] font-medium leading-[1.3] tracking-tight text-text-primary lg:max-w-[17rem] lg:text-[1.6rem]",
              side === "left" ? "left-[3vw] text-left" : "right-[3vw] text-right"
            )}
          >
            {CAPTIONS[active].text}
          </m.p>
        )}
      </AnimatePresence>
    </div>
  );
}

export function LaptopShowcase() {
  const sectionRef = useRef<HTMLElement>(null);
  const isDesktop = useIsDesktop(768);

  const rawReduced = useReducedMotion() ?? false;
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  const prefersReduced = mounted && rawReduced;

  const { scrollYProgress } = useScroll({
    target: sectionRef,
    offset: ["start start", "end end"],
  });

  // The R3F scene is heavy (Three.js + WebGL). Don't let it fight the hero for
  // the main thread — mounting it mid-intro is what made the opening animation
  // feel like it was blocking. Mount it lazily on the first of two triggers:
  //   • the section scrolls into view (`once: true` latches it on), or
  //   • the hero intro has finished, then an idle slot warms it proactively
  //     so it's ready by the time the user scrolls down.
  // Kick off the heavy 3D chunk download immediately (network only) so it is
  // cached well before we mount — fast scrollers then get the scene with no
  // load wait. The dynamic() below reuses this same already-fetched chunk.
  useEffect(() => {
    void import("./LaptopScene");
  }, []);

  const nearView = useInView(sectionRef, { margin: "0px 0px -120px 0px", once: true });
  const [idleWarmed, setIdleWarmed] = useState(false);
  useEffect(() => {
    // Mount soon after first paint during an idle slot. The render loop is
    // gated by `active` below, so an early off-screen mount costs only a quick
    // one-time warm — it can't hitch the hero intro the way a live loop did.
    let idleId: number | undefined;
    const t = window.setTimeout(() => {
      if (typeof window.requestIdleCallback === "function") {
        idleId = window.requestIdleCallback(() => setIdleWarmed(true), { timeout: 1000 });
      } else {
        setIdleWarmed(true);
      }
    }, 800);
    return () => {
      window.clearTimeout(t);
      if (idleId !== undefined) window.cancelIdleCallback(idleId);
    };
  }, []);
  const showScene = nearView || idleWarmed;

  // Live viewport check (not latched): render every frame only while the
  // section is actually scrolled into view (bottom margin is negative so it
  // does NOT run while the hero is on screen), and freeze the loop otherwise.
  const active = useInView(sectionRef, { margin: "200px 0px -200px 0px" });

  // A button-driven jump (scrollToHash) flies the scroll across this 500vh
  // section in ~1s, which would scrub the laptop open + flash every caption.
  // Freeze the scene + captions for that window only — manual scrolling never
  // sets this flag, so the normal scroll-linked animation is untouched.
  const programmatic = useProgrammaticScroll();

  // Snap the scroll to each feature's centre while inside this section, so a
  // fast scroll always settles on a caption instead of blowing past them.
  const lenis = useLenisInstance();
  useEffect(() => {
    if (!lenis || prefersReduced || !isDesktop) return;
    const section = sectionRef.current;
    if (!section) return;

    const snap = new Snap(lenis, {
      type: "proximity",
      distanceThreshold: "55%",
      duration: 0.7,
      lerp: 0.12,
    });

    let removers: Array<() => void> = [];
    const build = () => {
      removers.forEach((r) => r());
      removers = [];
      const rect = section.getBoundingClientRect();
      const docTop = rect.top + window.scrollY;
      const scrollable = section.offsetHeight - window.innerHeight;
      const width = (1 - FEATURE_START) / FEATURE_COUNT;
      for (let i = 0; i < FEATURE_COUNT; i++) {
        const center = FEATURE_START + (i + 0.5) * width;
        removers.push(snap.add(Math.round(docTop + center * scrollable)));
      }
    };

    build();
    // Rebuild once layout/fonts settle and on resize so anchors stay accurate.
    const settle = window.setTimeout(build, 800);
    window.addEventListener("resize", build);

    return () => {
      window.clearTimeout(settle);
      window.removeEventListener("resize", build);
      removers.forEach((r) => r());
      snap.destroy();
    };
  }, [lenis, prefersReduced, isDesktop]);

  if (!isDesktop) {
    return (
      <LazyMotion features={domAnimation}>
        <MobileLaptopFallback />
      </LazyMotion>
    );
  }

  return (
    <LazyMotion features={domAnimation}>
      <section
        ref={sectionRef}
        className="relative bg-black"
        style={{ height: prefersReduced ? "100vh" : "500vh" }}
      >
        <div className="sticky top-0 h-screen w-full overflow-hidden">
          <div className="absolute inset-0 z-0" aria-hidden="true">
            {showScene ? (
              <LaptopScene
                progress={scrollYProgress}
                reducedMotion={prefersReduced}
                active={active && !programmatic}
              />
            ) : (
              <HeroSceneSkeleton />
            )}
          </div>

          <span className="sr-only">{SR_DESCRIPTION}</span>

          <ShowcaseCaptions
            progress={scrollYProgress}
            reducedMotion={prefersReduced}
            frozen={programmatic}
          />
        </div>
      </section>
    </LazyMotion>
  );
}
