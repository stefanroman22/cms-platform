"use client";

import { useEffect, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Environment, Lightformer, ContactShadows } from "@react-three/drei";
import type { MotionValue } from "motion/react";
import { Laptop } from "./Laptop";

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const easeOutExpo = (t: number) => (t >= 1 ? 1 : 1 - Math.pow(2, -10 * t));

type SceneProps = {
  progress: MotionValue<number>;
  reducedMotion: boolean;
};

// Reframes as the lid opens, then climbs and tilts down across the features so
// the keyboard is progressively revealed, while orbiting sideways for parallax.
// No OrbitControls — scroll drives everything.
function CameraRig({ progress, reducedMotion }: SceneProps) {
  useFrame(({ camera }) => {
    const p = reducedMotion ? 0.5 : progress.get();
    // Phase 1 — reframe quickly, in step with the fast lid open (head-on).
    const t = easeOutExpo(clamp((p - 0.02) / 0.12, 0, 1));
    // Phase 2 — across the features the camera RISES and TILTS DOWN so the
    // keyboard slides fully into view step by step, DOLLIES in, and swings
    // through a horizontal arc for strong parallax — clearly a 3D object.
    const z = clamp((p - 0.14) / 0.86, 0, 1);
    const ez = z * z * (3 - 2 * z); // smoothstep — eases the reveal across the steps
    const arc = Math.sin(z * Math.PI); // out to the side at mid-scroll, back by the end
    // Zoom in a bit more on each feature step and climb to look down over the
    // keyboard. The laptop itself glides DOWN as you scroll (see Laptop.tsx),
    // which keeps the screen fully framed despite the zoom and brings the
    // keyboard lower into view so the keys read clearly.
    camera.position.set(
      arc * 1.6,
      lerp(1.4, 2.0, t) + ez * 1.5,
      lerp(8.8, 8.4, t) - ez * 1.5 // dolly in across the steps
    );
    camera.lookAt(arc * 0.35, lerp(0.55, 0.92, t) - ez * 0.2, lerp(0, -0.3, ez));
  });
  return null;
}

// `active` is true only while the section is near the viewport. We render every
// frame then (smooth scroll-scrubbing) and freeze the loop when scrolled away.
// `warming` forces a few frames right after mount — even off-screen — so the
// shaders compile and geometry uploads up front, and the scene appears
// instantly (no cold-start hitch) the moment it scrolls into view.
export default function LaptopScene({
  progress,
  reducedMotion,
  active,
}: SceneProps & { active: boolean }) {
  const [warming, setWarming] = useState(true);
  useEffect(() => {
    const id = window.setTimeout(() => setWarming(false), 220);
    return () => window.clearTimeout(id);
  }, []);

  return (
    <Canvas
      dpr={[1, 1.5]}
      frameloop={warming || active ? "always" : "never"}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      camera={{ fov: 30, position: [0, 1.2, 6] }}
      style={{ background: "transparent" }}
    >
      <CameraRig progress={progress} reducedMotion={reducedMotion} />

      <ambientLight intensity={0.55} />
      <directionalLight position={[5, 8, 5]} intensity={1.35} />
      <directionalLight position={[-3, 4, -5]} intensity={0.6} color="#C9A961" />

      <Laptop progress={progress} reducedMotion={reducedMotion} />

      {/* Reflections come from a procedural studio environment, baked once
          (frames={1}), instead of a CDN HDRI. No network fetch, so it can
          never fail to load — this replaces the old preset="city" that threw
          "potsdamer_platz_1k.hdr: Failed to fetch" when the CDN was blocked. */}
      <Environment resolution={256} frames={1}>
        <Lightformer
          intensity={2.4}
          position={[0, 3, 4]}
          rotation={[-Math.PI / 3, 0, 0]}
          scale={[10, 5, 1]}
          color="#ffffff"
        />
        <Lightformer
          intensity={0.8}
          position={[-5, 1, 2]}
          rotation={[0, Math.PI / 4, 0]}
          scale={[5, 5, 1]}
          color="#9fb4d8"
        />
        <Lightformer
          intensity={1.0}
          position={[5, 2, -3]}
          rotation={[0, -Math.PI / 3, 0]}
          scale={[5, 5, 1]}
          color="#C9A961"
        />
        <Lightformer
          intensity={0.35}
          position={[0, -3, 0]}
          rotation={[Math.PI / 2, 0, 0]}
          scale={[10, 10, 1]}
          color="#101012"
        />
      </Environment>

      <ContactShadows
        position={[0, -0.32, 0]}
        opacity={0.5}
        scale={8}
        blur={2.6}
        far={4}
        resolution={512}
        color="#000000"
      />
    </Canvas>
  );
}
