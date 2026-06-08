/**
 * Shared timing + feature config for the laptop scroll showcase.
 * Both the captions (LaptopShowcase) and the on-screen image (Laptop) derive
 * the active feature index from the SAME function, so they always stay in sync.
 *
 * Replace the images in /public/laptop/ with real feature screenshots later —
 * just keep the same file names (or edit FEATURE_IMAGES below).
 */
export const FEATURE_IMAGES = [
  "/laptop/feature-1.svg",
  "/laptop/feature-2.svg",
  "/laptop/feature-3.svg",
  "/laptop/feature-4.svg",
] as const;

export const FEATURE_COUNT = FEATURE_IMAGES.length;

// The lid snaps open fast within the first sliver of scroll; the features then
// step across the rest of the scroll, each occupying ~one viewport (so one
// "scroll" advances roughly one feature). Tune these to retime the sequence.
export const LID_OPEN_START = 0.02;
export const LID_OPEN_END = 0.12; // lid fully open early
export const SCREEN_MOUNT_AT = 0.06; // screen content fades in as the lid lifts
export const FEATURE_START = 0.14; // first feature is settled by here

/** Active feature index (0 … FEATURE_COUNT-1) for a given scroll progress. */
export function progressToFeature(p: number): number {
  const t = (p - FEATURE_START) / (1 - FEATURE_START);
  return Math.min(FEATURE_COUNT - 1, Math.max(0, Math.floor(t * FEATURE_COUNT)));
}
