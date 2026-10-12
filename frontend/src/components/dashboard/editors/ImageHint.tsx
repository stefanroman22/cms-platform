export interface ImageSize {
  width: number;
  height: number;
}

const LARGE_FILE_BYTES = 1024 * 1024;

const gcd = (a: number, b: number): number => (b ? gcd(b, a % b) : a);

/** "8:3" when both reduced terms are ≤ 32, else a decimal like "2.67:1". */
function ratioLabel({ width, height }: ImageSize): string {
  const g = gcd(width, height);
  const w = width / g;
  const h = height / g;
  return w <= 32 && h <= 32 ? `${w}:${h}` : `${(width / height).toFixed(2)}:1`;
}

const orientation = ({ width, height }: ImageSize) =>
  width > height ? "landscape" : width < height ? "portrait" : "square";

/** A schema `hint` / service `_hint` (ADR-0011), or undefined if malformed. */
export function readHint(raw: unknown): ImageSize | undefined {
  if (typeof raw !== "object" || raw === null) return undefined;
  const { width, height } = raw as Record<string, unknown>;
  const ok = (v: unknown): v is number => typeof v === "number" && Number.isInteger(v) && v > 0;
  return ok(width) && ok(height) ? { width, height } : undefined;
}

/** Natural size of a picked raster file; null for SVG or when it can't be decoded. */
export function measureImage(file: File): Promise<ImageSize | null> {
  if (file.type === "image/svg+xml" || typeof URL.createObjectURL !== "function") {
    return Promise.resolve(null);
  }
  return new Promise((resolve) => {
    const src = URL.createObjectURL(file);
    const img = new Image();
    const done = (size: ImageSize | null) => {
      URL.revokeObjectURL(src);
      resolve(size);
    };
    img.onload = () =>
      done(
        img.naturalWidth && img.naturalHeight
          ? { width: img.naturalWidth, height: img.naturalHeight }
          : null
      );
    img.onerror = () => done(null);
    img.src = src;
  });
}

export function ImageHint({
  hint,
  measured,
  bytes,
}: {
  hint?: ImageSize;
  measured?: ImageSize;
  bytes?: number;
}) {
  const text = hint
    ? `Recommended: ${hint.width} × ${hint.height} px (${orientation(hint)} ${ratioLabel(hint)}) · JPG or WebP · under 500 KB`
    : "Recommended: JPG, WebP or PNG, at least 1200 px wide, under 500 KB. SVG for logos and illustrations.";

  const warnings: string[] = [];
  if (hint && measured) {
    const slot = hint.width / hint.height;
    if (Math.abs(measured.width / measured.height / slot - 1) > 0.15) {
      warnings.push(
        `This image is ${ratioLabel(measured)} but the slot is ${ratioLabel(hint)}; it will be cropped.`
      );
    }
    if (measured.width < 0.5 * hint.width) {
      warnings.push("Smaller than recommended; it may look blurry.");
    }
  }
  if (bytes !== undefined && bytes > LARGE_FILE_BYTES) {
    warnings.push("Large file; compress it to keep the site fast.");
  }

  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs text-zinc-500 dark:text-zinc-400">{text}</p>
      <div aria-live="polite" className="space-y-1">
        {warnings.map((w) => (
          <p key={w} className="text-xs text-amber-700 dark:text-amber-400">
            {w}
          </p>
        ))}
      </div>
    </div>
  );
}
