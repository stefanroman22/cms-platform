"use client";
/* eslint-disable @next/next/no-img-element */

import { useRef, useState, type RefObject } from "react";
import { useFrame } from "@react-three/fiber";
import { RoundedBox, Html } from "@react-three/drei";
import { useMotionValueEvent, type MotionValue } from "motion/react";
import type { Group } from "three";
import {
  FEATURE_IMAGES,
  FEATURE_START,
  LID_OPEN_START,
  LID_OPEN_END,
  SCREEN_MOUNT_AT,
  progressToFeature,
} from "./showcase";

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
// ease-out-expo, mirrors --ease-out-expo
const easeOutExpo = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

const LID_CLOSED = Math.PI / 2; // lid lying flat on the deck
const LID_OPEN = -0.35; // ~110° from horizontal (20° past vertical)

// Brushed-aluminium body tone — light enough to read clearly against the black
// section, while staying metallic so the env reflections still play across it.
const BODY = "#54545c";

// ROMAN-key glow fades in from when the lid reveals the keyboard until the
// second caption, so it "arrives" on the second scroll rather than popping.
const GLOW_START = SCREEN_MOUNT_AT;
const GLOW_FULL = FEATURE_START + (1 - FEATURE_START) / FEATURE_IMAGES.length; // start of feature 2

// The keys are hidden until the lid lifts past them, then fade in as it opens.
// This is what stops the keyboard from showing on top of the still-closed lid
// (a DOM overlay would otherwise paint over the canvas before the lid moves).
const KB_REVEAL_START = 0.06;
const KB_REVEAL_END = 0.13;

type LaptopProps = {
  progress: MotionValue<number>;
  reducedMotion: boolean;
};

export function Laptop({ progress, reducedMotion }: LaptopProps) {
  const rootRef = useRef<Group>(null);
  const lidRef = useRef<Group>(null);

  useFrame(() => {
    const p = reducedMotion ? 1 : progress.get();
    const root = rootRef.current;
    const lid = lidRef.current;
    if (!root || !lid) return;

    // Lid snaps open fast within the first sliver of scroll, then locks open.
    const openT = easeOutExpo(clamp((p - LID_OPEN_START) / (LID_OPEN_END - LID_OPEN_START), 0, 1));
    lid.rotation.x = lerp(LID_CLOSED, LID_OPEN, openT);

    // Open, then add a yaw sway across the features so the laptop keeps
    // turning as you scroll — reads unmistakably as a 3D object.
    const featZ = clamp((p - LID_OPEN_END) / (1 - LID_OPEN_END), 0, 1);
    const sway = reducedMotion ? 0 : Math.sin(featZ * Math.PI) * 0.16;
    root.rotation.y = lerp(-0.3, 0, openT) + sway;
    root.scale.setScalar(1.04);
    // Glide the laptop down as you scroll the features, so the screen stays
    // fully framed while the camera zooms in and the keyboard rises into view.
    root.position.y = lerp(-0.12, 0.02, openT) - (reducedMotion ? 0 : featZ * 0.45);
  });

  return (
    <group ref={rootRef} rotation={[-0.06, -0.3, 0]} position={[0, -0.12, 0]}>
      {/* ── Deck ─────────────────────────────────────────────────── */}
      <RoundedBox args={[3.6, 0.12, 2.4]} radius={0.04} smoothness={6}>
        <meshStandardMaterial color={BODY} metalness={0.7} roughness={0.35} />
      </RoundedBox>

      {/* Keyboard tray (recess the keys sit in) */}
      <RoundedBox args={[3.1, 0.03, 1.2]} radius={0.02} smoothness={4} position={[0, 0.07, -0.22]}>
        <meshStandardMaterial color="#2b2b30" metalness={0.3} roughness={0.85} />
      </RoundedBox>

      {/* Keys — faded in as the lid opens (see KB_REVEAL_*). */}
      <Keyboard progress={progress} reducedMotion={reducedMotion} />

      {/* Trackpad */}
      <RoundedBox
        args={[1.15, 0.02, 0.72]}
        radius={0.02}
        smoothness={4}
        position={[0, 0.072, 0.72]}
      >
        <meshStandardMaterial color="#24242a" metalness={0.3} roughness={0.85} />
      </RoundedBox>

      {/* ── Lid pivot at the rear hinge ──────────────────────────── */}
      <group ref={lidRef} position={[0, 0.06, -1.2]} rotation={[LID_CLOSED, 0, 0]}>
        {/* Lid panel — authored standing up; bottom edge at the hinge. */}
        <RoundedBox args={[3.6, 2.4, 0.08]} radius={0.04} smoothness={6} position={[0, 1.2, 0]}>
          <meshStandardMaterial color={BODY} metalness={0.7} roughness={0.35} />
        </RoundedBox>

        {/* Screen face + bezel + the cross-fading feature image */}
        <group position={[0, 1.2, 0.041]}>
          <ScreenPlane />
          <ScreenFrame />
          <ScreenImage progress={progress} reducedMotion={reducedMotion} />
        </group>
      </group>
    </group>
  );
}

function ScreenPlane() {
  return (
    <mesh>
      <planeGeometry args={[3.32, 2.07]} />
      <meshStandardMaterial
        color="#0E0E10"
        emissive="#0E0E10"
        emissiveIntensity={0.5}
        roughness={0.4}
      />
    </mesh>
  );
}

// Four hairline neutral strips framing the screen — a subtle metallic bezel.
function ScreenFrame() {
  const w = 3.34;
  const h = 2.09;
  const t = 0.022;
  const mat = <meshStandardMaterial color="#5c5c64" metalness={0.7} roughness={0.4} />;
  return (
    <group position={[0, 0, 0.002]}>
      <mesh position={[0, h / 2, 0]}>
        <boxGeometry args={[w, t, 0.01]} />
        {mat}
      </mesh>
      <mesh position={[0, -h / 2, 0]}>
        <boxGeometry args={[w, t, 0.01]} />
        {mat}
      </mesh>
      <mesh position={[-w / 2, 0, 0]}>
        <boxGeometry args={[t, h, 0.01]} />
        {mat}
      </mesh>
      <mesh position={[w / 2, 0, 0]}>
        <boxGeometry args={[t, h, 0.01]} />
        {mat}
      </mesh>
    </group>
  );
}

/** Cross-fading feature mock images; the whole screen fades in as the lid opens. */
function ScreenImage({ progress, reducedMotion }: LaptopProps) {
  const init = reducedMotion || progress.get() >= SCREEN_MOUNT_AT;
  const [mounted, setMounted] = useState(init);
  const [active, setActive] = useState(() =>
    reducedMotion ? 0 : progressToFeature(progress.get())
  );
  const wrapRef = useRef<HTMLDivElement>(null);

  useMotionValueEvent(progress, "change", (p) => {
    if (reducedMotion) return;
    setMounted(p >= SCREEN_MOUNT_AT);
    setActive(progressToFeature(p));
    if (wrapRef.current) {
      wrapRef.current.style.opacity = String(clamp((p - SCREEN_MOUNT_AT) / 0.06, 0, 1));
    }
  });

  if (!mounted) return null;
  const initialOpacity = reducedMotion ? 1 : clamp((progress.get() - SCREEN_MOUNT_AT) / 0.06, 0, 1);

  return (
    <group position={[0, 0, 0.02]} scale={0.103}>
      <Html transform position={[0, 0, 0]} style={{ pointerEvents: "none" }}>
        <div
          ref={wrapRef}
          style={{
            position: "relative",
            width: 1280,
            height: 800,
            borderRadius: 8,
            overflow: "hidden",
            background: "#0E0E10",
            opacity: initialOpacity,
            transition: "opacity 0.2s linear",
          }}
        >
          {FEATURE_IMAGES.map((src, i) => (
            <img
              key={src}
              src={src}
              alt=""
              draggable={false}
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                objectFit: "cover",
                opacity: i === active ? 1 : 0,
                transition: "opacity 0.55s ease",
              }}
            />
          ))}
        </div>
      </Html>
    </group>
  );
}

// A complete laptop layout: function row, number row, QWERTY, home row, shift
// row, and a modifier + spacebar row. Letters/symbols are one unit wide; wider
// keys carry a `w` multiplier; the slim function keys carry a shorter `h`.
// The ROMAN keys glow as the showcase advances.
type Key = { l: string; w?: number; h?: number };
const FN_H = 24;
const KB_ROWS: Key[][] = [
  [
    { l: "esc", h: FN_H },
    { l: "F1", h: FN_H },
    { l: "F2", h: FN_H },
    { l: "F3", h: FN_H },
    { l: "F4", h: FN_H },
    { l: "F5", h: FN_H },
    { l: "F6", h: FN_H },
    { l: "F7", h: FN_H },
    { l: "F8", h: FN_H },
    { l: "F9", h: FN_H },
    { l: "F10", h: FN_H },
    { l: "F11", h: FN_H },
    { l: "F12", h: FN_H },
  ],
  [
    { l: "~" },
    { l: "1" },
    { l: "2" },
    { l: "3" },
    { l: "4" },
    { l: "5" },
    { l: "6" },
    { l: "7" },
    { l: "8" },
    { l: "9" },
    { l: "0" },
    { l: "-" },
    { l: "=" },
    { l: "delete", w: 1.7 },
  ],
  [
    { l: "tab", w: 1.5 },
    { l: "Q" },
    { l: "W" },
    { l: "E" },
    { l: "R" },
    { l: "T" },
    { l: "Y" },
    { l: "U" },
    { l: "I" },
    { l: "O" },
    { l: "P" },
    { l: "[" },
    { l: "]" },
    { l: "\\", w: 1.2 },
  ],
  [
    { l: "caps", w: 1.8 },
    { l: "A" },
    { l: "S" },
    { l: "D" },
    { l: "F" },
    { l: "G" },
    { l: "H" },
    { l: "J" },
    { l: "K" },
    { l: "L" },
    { l: ";" },
    { l: "'" },
    { l: "return", w: 2.0 },
  ],
  [
    { l: "shift", w: 2.3 },
    { l: "Z" },
    { l: "X" },
    { l: "C" },
    { l: "V" },
    { l: "B" },
    { l: "N" },
    { l: "M" },
    { l: "," },
    { l: "." },
    { l: "/" },
    { l: "shift", w: 2.5 },
  ],
  [
    { l: "fn" },
    { l: "ctrl", w: 1.25 },
    { l: "opt", w: 1.25 },
    { l: "cmd", w: 1.5 },
    { l: "", w: 6 },
    { l: "cmd", w: 1.5 },
    { l: "opt", w: 1.25 },
    { l: "◄", w: 0.9 },
    { l: "▲", w: 0.9 },
    { l: "►", w: 0.9 },
  ],
];
const KB_GLOW = new Set(["R", "O", "M", "A", "N"]);

function Keyboard({ progress, reducedMotion }: LaptopProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useMotionValueEvent(progress, "change", (p) => {
    if (reducedMotion) return;
    const el = containerRef.current;
    if (!el) return;
    el.style.setProperty(
      "--kbglow",
      String(clamp((p - GLOW_START) / (GLOW_FULL - GLOW_START), 0, 1))
    );
    el.style.opacity = String(
      clamp((p - KB_REVEAL_START) / (KB_REVEAL_END - KB_REVEAL_START), 0, 1)
    );
  });

  const initialGlow = reducedMotion
    ? 1
    : clamp((progress.get() - GLOW_START) / (GLOW_FULL - GLOW_START), 0, 1);
  const initialOpacity = reducedMotion
    ? 1
    : clamp((progress.get() - KB_REVEAL_START) / (KB_REVEAL_END - KB_REVEAL_START), 0, 1);

  return (
    <group position={[0, 0.09, -0.22]} rotation={[-Math.PI / 2, 0, 0]} scale={0.135}>
      <Html transform position={[0, 0, 0]} style={{ pointerEvents: "none" }}>
        <KeyboardDOM
          containerRef={containerRef}
          initialGlow={initialGlow}
          initialOpacity={initialOpacity}
        />
      </Html>
    </group>
  );
}

const KEY_UNIT = 48; // base key width; wider keys multiply it
const KEY_GAP = 5;
const KEY_HEIGHT = 42;

function KeyboardDOM({
  containerRef,
  initialGlow,
  initialOpacity,
}: {
  containerRef: RefObject<HTMLDivElement | null>;
  initialGlow: number;
  initialOpacity: number;
}) {
  return (
    <div
      ref={containerRef}
      style={
        {
          // glow factor 0 → 1; ROMAN keys interpolate their glow from it
          ["--kbglow" as string]: initialGlow,
          // hidden until the lid lifts past the keys (set each scroll frame)
          opacity: initialOpacity,
          // Promote to its own compositor layer: as the camera moves, the
          // browser re-transforms this cached texture instead of repainting all
          // the keys every frame — the main scroll-jank source.
          willChange: "transform, opacity",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: KEY_GAP,
          padding: 12,
          width: 880,
          fontFamily: "var(--font-geist-sans), Arial, sans-serif",
        } as React.CSSProperties
      }
    >
      {KB_ROWS.map((row, r) => (
        <div key={r} style={{ display: "flex", gap: KEY_GAP }}>
          {row.map((key, i) => {
            const glow = KB_GLOW.has(key.l);
            const kh = key.h ?? KEY_HEIGHT;
            const fontSize = kh < 32 ? 9 : key.l.length > 1 ? 11 : 19;
            return (
              <div
                key={i}
                style={{
                  width: KEY_UNIT * (key.w ?? 1),
                  height: kh,
                  borderRadius: 8,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize,
                  fontWeight: 600,
                  color: glow
                    ? "color-mix(in srgb, #9a9aa0, #FBE7B0 calc(var(--kbglow) * 100%))"
                    : "#a2a2aa",
                  background: glow
                    ? "color-mix(in srgb, #1f1f23, #241d0c calc(var(--kbglow) * 100%))"
                    : "linear-gradient(180deg,#26262b,#1b1b1f)",
                  border: glow
                    ? "1.5px solid color-mix(in srgb, #34343a, #C9A961 calc(var(--kbglow) * 100%))"
                    : "1px solid #34343a",
                  boxShadow: glow
                    ? "0 0 22px 3px rgba(201,169,97,calc(0.6*var(--kbglow))), inset 0 0 10px rgba(201,169,97,calc(0.4*var(--kbglow))), inset 0 -3px 0 rgba(0,0,0,0.5)"
                    : "inset 0 -3px 0 rgba(0,0,0,0.55), 0 1px 2px rgba(0,0,0,0.4)",
                  textShadow: glow ? "0 0 14px rgba(201,169,97,calc(0.95*var(--kbglow)))" : "none",
                }}
              >
                {key.l}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
