"use client";

import { createContext, useContext, useEffect, useRef, useState } from "react";
import Lenis from "lenis";
import { useAnimationFrame } from "motion/react";
import { setActiveLenis, scrollToHash } from "@/lib/scroll";
import "lenis/dist/lenis.css";

const LenisContext = createContext<Lenis | null>(null);

/** Access the active Lenis instance (null when reduced-motion / not ready). */
export const useLenisInstance = () => useContext(LenisContext);

/**
 * Smooth-scroll wrapper. Initializes Lenis once on mount and drives its
 * RAF loop through Motion's useAnimationFrame so there is a single,
 * centralized frame loop shared with the scroll-linked hero animations.
 * Skips Lenis entirely when the user prefers reduced motion. Exposes the
 * instance via context so sections can add scroll snapping.
 */
export function LenisProvider({ children }: { children: React.ReactNode }) {
  const lenisRef = useRef<Lenis | null>(null);
  const [lenis, setLenis] = useState<Lenis | null>(null);

  // Hide the native scrollbar on the landing (scroll still works). Scoped here
  // so it only applies while the marketing page is mounted.
  useEffect(() => {
    document.documentElement.classList.add("hide-native-scrollbar");
    return () => document.documentElement.classList.remove("hide-native-scrollbar");
  }, []);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const instance = new Lenis({ lerp: 0.1, smoothWheel: true, wheelMultiplier: 1 });
    lenisRef.current = instance;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- intentional: publish the external Lenis instance to context after creation
    setLenis(instance);
    setActiveLenis(instance); // expose to the Header / hero (outside this context)

    return () => {
      instance.destroy();
      lenisRef.current = null;
      setLenis(null);
      setActiveLenis(null);
    };
  }, []);

  // On mount (incl. navigating TO the home page): if the URL has a hash, deep
  // link to that section; otherwise start at the very top. The browser / Next
  // can restore the previous scroll a frame or two after mount, and a fresh
  // Lenis instance would inherit it — so re-assert top via Lenis's own scrollTo
  // (authoritative; its RAF then holds it) a couple of times to win that race.
  useEffect(() => {
    const hash = window.location.hash;
    if (hash) {
      const t = setTimeout(() => scrollToHash(hash), 120);
      return () => clearTimeout(t);
    }
    const toTop = () => {
      lenisRef.current?.scrollTo(0, { immediate: true });
      window.scrollTo(0, 0);
    };
    toTop();
    const raf = requestAnimationFrame(toTop);
    const timer = setTimeout(toTop, 100);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, []);

  useAnimationFrame((time) => {
    lenisRef.current?.raf(time);
  });

  return <LenisContext.Provider value={lenis}>{children}</LenisContext.Provider>;
}
