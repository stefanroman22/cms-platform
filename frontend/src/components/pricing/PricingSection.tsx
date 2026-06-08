"use client";

import * as React from "react";
import { createPortal } from "react-dom";
import {
  LazyMotion,
  domMax,
  m,
  AnimatePresence,
  MotionConfig,
  useReducedMotion,
} from "motion/react";
import { Check, Star } from "lucide-react";
import { HeroButton } from "@/components/ui/HeroButton";
import { SegmentedToggle } from "@/components/ui/SegmentedToggle";
import { Reveal } from "@/components/motion/Reveal";
import { cn } from "@/lib/utils";

const EXPO = [0.16, 1, 0.3, 1] as const;

type Category = "project" | "subscription";
type Frequency = "monthly" | "yearly";

interface Feature {
  text: string;
  /** Optional plain-language explanation shown on hover / focus / tap. */
  tooltip?: string;
}

interface ProjectPlan {
  name: string;
  info: string;
  /** Starting price in EUR — every quote is adjusted to complexity. */
  priceFrom: number;
  /** Secondary "starting from" note, e.g. complex-backend pricing. */
  priceNote?: string;
  /** Differentiators only — shared items live in the "includes" strip. */
  features: Feature[];
  highlighted?: boolean;
  badge?: string;
  cta: { text: string; href: string };
}

interface SubscriptionPlan {
  name: string;
  info: string;
  price: { monthly: number; yearly: number };
  features: Feature[];
  highlighted?: boolean;
  badge?: string;
  cta: { text: string; href: string };
}

/** Core services bundled into every project plan — listed inside each card. */
const PROJECT_BUNDLE: Feature[] = [
  {
    text: "Managed hosting and security",
    tooltip: "Hosted, secured and monitored by us — no separate hosting bill.",
  },
  {
    text: "SEO & GEO optimization",
    tooltip: "Optimized for search engines and AI answer engines so you get found.",
  },
  {
    text: "Personal human review",
    tooltip: "Every major release is reviewed by a human, not just shipped by a machine.",
  },
  {
    text: "CMS connector & agentic issue solver",
    tooltip:
      "Change content across your app anytime, and an AI agent auto-detects and fixes issues.",
  },
];

const PROJECT_PLANS: ProjectPlan[] = [
  {
    name: "Presentation website",
    info: "Marketing & presentation sites that launch fast.",
    priceFrom: 250,
    priceNote: "from €400 with complex backend integration",
    features: [{ text: "Custom, responsive design" }],
    cta: { text: "Get a free preview", href: "/contact" },
  },
  {
    name: "Software application",
    info: "Mobile and / or desktop apps, built to scale.",
    priceFrom: 500,
    highlighted: true,
    badge: "Most popular",
    features: [
      {
        text: "Priority development meetings",
        tooltip: "Higher priority for human meetings with the development team.",
      },
    ],
    cta: { text: "Start your app", href: "/contact" },
  },
  {
    name: "AI automation software",
    info: "Custom AI workflows that run your busywork.",
    priceFrom: 200,
    features: [
      {
        text: "24/7 maintenance",
        tooltip: "We keep your automations running around the clock.",
      },
    ],
    cta: { text: "Automate something", href: "/contact" },
  },
];

// PLACEHOLDER subscription tiers — prices and included services are drafts.
// Stefan will finalise the names, prices and feature lists later.
const SUBSCRIPTION_PLANS: SubscriptionPlan[] = [
  {
    name: "Care",
    info: "Keep an existing site healthy.",
    price: { monthly: 49, yearly: 490 },
    features: [
      { text: "Managed hosting & monitoring" },
      { text: "Monthly content updates" },
      { text: "Email support" },
    ],
    cta: { text: "Choose Care", href: "/contact" },
  },
  {
    name: "Growth",
    info: "Ongoing improvements & support.",
    price: { monthly: 99, yearly: 990 },
    highlighted: true,
    badge: "Most popular",
    features: [
      { text: "Everything in Care" },
      { text: "Agentic issue solver" },
      { text: "Priority support" },
      { text: "Quarterly strategy meeting" },
    ],
    cta: { text: "Choose Growth", href: "/contact" },
  },
  {
    name: "Scale",
    info: "A dedicated partner for fast-moving teams.",
    price: { monthly: 199, yearly: 1990 },
    features: [
      { text: "Everything in Growth" },
      { text: "Dedicated developer hours" },
      { text: "24/7 support agent" },
      { text: "Monthly roadmap reviews" },
    ],
    cta: { text: "Choose Scale", href: "/contact" },
  },
];

/** Subtle brass dot that travels around the card border — the hero's gold glow,
 *  dialled right down so it reads as elegance, not flash. */
function BorderTrail({ size = 80 }: { size?: number }) {
  return (
    <div className="pointer-events-none absolute inset-0 rounded-[inherit] border border-transparent [mask-clip:padding-box,border-box] [mask-composite:intersect] [mask-image:linear-gradient(transparent,transparent),linear-gradient(#000,#000)]">
      <m.div
        className="absolute aspect-square rounded-full bg-accent"
        style={{
          width: size,
          offsetPath: `rect(0 auto auto 0 round ${size}px)`,
          boxShadow: "0 0 22px 5px rgba(201,169,97,0.35)",
        }}
        animate={{ offsetDistance: ["0%", "100%"] }}
        transition={{ repeat: Infinity, duration: 7, ease: "linear" }}
      />
    </div>
  );
}

/** Tooltip max width + the minimum gap it must keep from any viewport edge.
 *  These drive the edge-clamping math so the bubble stays fully on-screen with
 *  breathing room, no matter how long the text or how narrow the screen. */
const TOOLTIP_MAX_WIDTH = 260; // px
const TOOLTIP_EDGE_PADDING = 12; // px

/** Lightweight tooltip — opens on hover, focus and tap, so it works on touch
 *  too (no Radix dependency). The trigger is a real button for keyboard a11y.
 *  The bubble is portaled to <body> and positioned with `fixed` coordinates so
 *  it escapes each card's `overflow-hidden` (and any other clipping ancestor),
 *  then its centre is clamped within the padded viewport — it stays fully
 *  visible for every feature on any screen, whatever the tooltip text. */
function FeatureLabel({ feature }: { feature: Feature }) {
  const [open, setOpen] = React.useState(false);
  const triggerRef = React.useRef<HTMLButtonElement>(null);
  // `left` = clamped horizontal centre; `bottom` = distance from viewport bottom
  // up to 8px above the trigger (so the bubble sits just above the label).
  const [pos, setPos] = React.useState<{ left: number; bottom: number } | null>(null);

  const place = React.useCallback(() => {
    const el = triggerRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const width = Math.min(TOOLTIP_MAX_WIDTH, window.innerWidth - TOOLTIP_EDGE_PADDING * 2);
    const half = width / 2;
    const center = r.left + r.width / 2;
    const left = Math.min(
      Math.max(center, TOOLTIP_EDGE_PADDING + half),
      window.innerWidth - TOOLTIP_EDGE_PADDING - half
    );
    setPos({ left, bottom: window.innerHeight - r.top + 8 });
  }, []);

  // Compute on open, then keep it pinned to the trigger on scroll/resize.
  React.useEffect(() => {
    if (!open) return;
    place();
    window.addEventListener("scroll", place, true);
    window.addEventListener("resize", place);
    return () => {
      window.removeEventListener("scroll", place, true);
      window.removeEventListener("resize", place);
    };
  }, [open, place]);

  if (!feature.tooltip) {
    return <span>{feature.text}</span>;
  }

  return (
    <span className="inline-flex">
      <button
        ref={triggerRef}
        type="button"
        className="cursor-help border-b border-dashed border-text-tertiary/60 text-left outline-none transition-colors hover:border-accent/60 focus-visible:border-accent"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {feature.text}
      </button>
      {typeof document !== "undefined" &&
        createPortal(
          <AnimatePresence>
            {open && pos && (
              <m.span
                role="tooltip"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                transition={{ duration: 0.18, ease: EXPO }}
                style={{
                  position: "fixed",
                  left: pos.left,
                  bottom: pos.bottom,
                  x: "-50%",
                  maxWidth: TOOLTIP_MAX_WIDTH,
                }}
                className="pointer-events-none z-50 block w-max rounded-lg border border-border bg-surface px-3 py-2 text-xs leading-snug text-text-secondary shadow-xl shadow-black/40"
              >
                {feature.tooltip}
              </m.span>
            )}
          </AnimatePresence>,
          document.body
        )}
    </span>
  );
}

function CardBadge({ label }: { label: string }) {
  return (
    <span className="absolute right-4 top-4 z-10 inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-1 text-xs font-medium text-bg">
      <Star className="h-3 w-3 fill-current" aria-hidden="true" />
      {label}
    </span>
  );
}

function CardShell({
  highlighted,
  showTrail,
  children,
}: {
  highlighted?: boolean;
  showTrail: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "relative flex h-full flex-col overflow-hidden rounded-2xl border bg-surface/30 backdrop-blur-sm transition-colors",
        highlighted ? "border-accent/40 shadow-2xl shadow-accent-glow" : "border-border"
      )}
    >
      {highlighted && showTrail && <BorderTrail />}
      {children}
    </div>
  );
}

function FeatureList({ features }: { features: Feature[] }) {
  return (
    <ul className="space-y-2 text-sm text-text-secondary">
      {features.map((f) => (
        <li key={f.text} className="flex items-start gap-2.5">
          <Check
            className="mt-0.5 h-4 w-4 shrink-0 text-accent"
            strokeWidth={2.5}
            aria-hidden="true"
          />
          <FeatureLabel feature={f} />
        </li>
      ))}
    </ul>
  );
}

function ProjectCard({ plan, showTrail }: { plan: ProjectPlan; showTrail: boolean }) {
  return (
    <CardShell highlighted={plan.highlighted} showTrail={showTrail}>
      {plan.badge && <CardBadge label={plan.badge} />}
      <div className="border-b border-border p-5">
        <h3 className="font-display text-lg font-semibold text-text-primary">{plan.name}</h3>
        <p className="mt-1 min-h-[2.5rem] text-sm text-text-secondary">{plan.info}</p>
        <div className="mt-3 flex items-baseline gap-1.5">
          <span className="text-sm text-text-tertiary">from</span>
          <span className="font-display text-4xl font-bold tabular-nums text-text-primary">
            €{plan.priceFrom}
          </span>
        </div>
        <p className="mt-1 min-h-[1rem] text-xs text-text-tertiary">{plan.priceNote ?? ""}</p>
      </div>

      <div className="flex-1 px-5 py-4">
        <FeatureList features={[...plan.features, ...PROJECT_BUNDLE]} />
      </div>

      <div className="border-t border-border p-4">
        <HeroButton
          href={plan.cta.href}
          variant={plan.highlighted ? "primary" : "secondary"}
          className="w-full"
        >
          {plan.cta.text}
        </HeroButton>
      </div>
    </CardShell>
  );
}

function SubscriptionCard({
  plan,
  frequency,
  showTrail,
}: {
  plan: SubscriptionPlan;
  frequency: Frequency;
  showTrail: boolean;
}) {
  const price = plan.price[frequency];
  const yearlyDiscount =
    plan.price.monthly > 0
      ? Math.round(
          ((plan.price.monthly * 12 - plan.price.yearly) / (plan.price.monthly * 12)) * 100
        )
      : 0;

  return (
    <CardShell highlighted={plan.highlighted} showTrail={showTrail}>
      <div className="absolute right-4 top-4 z-10 flex items-center gap-2">
        {frequency === "yearly" && yearlyDiscount > 0 && (
          <span className="rounded-full border border-accent/40 bg-accent/10 px-2.5 py-1 text-xs font-medium text-accent">
            Save {yearlyDiscount}%
          </span>
        )}
        {plan.badge && (
          <span className="inline-flex items-center gap-1 rounded-full bg-accent px-2.5 py-1 text-xs font-medium text-bg">
            <Star className="h-3 w-3 fill-current" aria-hidden="true" />
            {plan.badge}
          </span>
        )}
      </div>

      <div className="border-b border-border p-5">
        <h3 className="font-display text-lg font-semibold text-text-primary">{plan.name}</h3>
        <p className="mt-1 min-h-[2.5rem] text-sm text-text-secondary">{plan.info}</p>
        <div className="mt-3 flex items-baseline gap-1">
          <span className="font-display text-4xl font-bold tabular-nums text-text-primary">
            €{price}
          </span>
          <span className="text-sm text-text-tertiary">
            /{frequency === "monthly" ? "month" : "year"}
          </span>
        </div>
      </div>

      <div className="flex-1 px-5 py-4">
        <FeatureList features={plan.features} />
      </div>

      <div className="border-t border-border p-4">
        <HeroButton
          href={plan.cta.href}
          variant={plan.highlighted ? "primary" : "secondary"}
          className="w-full"
        >
          {plan.cta.text}
        </HeroButton>
      </div>
    </CardShell>
  );
}

export function PricingSection() {
  const [category, setCategory] = React.useState<Category>("project");
  const [frequency, setFrequency] = React.useState<Frequency>("monthly");

  // Decorative infinite border-trail is gated on reduced-motion. Resolves
  // post-mount so SSR and first client render agree.
  const rawReduced = useReducedMotion() ?? false;
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => setMounted(true), []);
  const showTrail = mounted && !rawReduced;

  return (
    <section
      id="pricing"
      className="relative overflow-hidden bg-black px-6 py-16 lg:flex lg:min-h-dvh lg:flex-col lg:justify-center lg:pt-24 lg:pb-8"
    >
      {/* Just-a-bit-of-gold ambient glow, echoing the hero. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-16 h-[440px] w-[720px] -translate-x-1/2 rounded-full opacity-60 blur-3xl"
        style={{
          background: "radial-gradient(circle, rgba(201,169,97,0.10), rgba(201,169,97,0) 70%)",
        }}
      />

      <LazyMotion features={domMax}>
        <MotionConfig reducedMotion="user">
          <div className="relative z-10 mx-auto max-w-5xl">
            <Reveal inView amount={0.4} className="mx-auto max-w-2xl text-center">
              <h2 className="font-display text-[clamp(2rem,5vw,3.25rem)] font-bold leading-[1.05] tracking-[-0.02em] text-text-primary">
                Simple, honest pricing
              </h2>
            </Reveal>

            <Reveal
              inView
              amount={0.4}
              delay={0.1}
              direction="none"
              className="mt-6 flex justify-center"
            >
              <SegmentedToggle<Category>
                value={category}
                onChange={setCategory}
                layoutId="pricing-category"
                options={[
                  { value: "project", label: "Project-based" },
                  { value: "subscription", label: "Subscription" },
                ]}
              />
            </Reveal>

            <div className="mt-7">
              <AnimatePresence mode="wait">
                {category === "project" ? (
                  <m.div
                    key="project"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.4, ease: EXPO }}
                  >
                    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                      {PROJECT_PLANS.map((plan) => (
                        <ProjectCard key={plan.name} plan={plan} showTrail={showTrail} />
                      ))}
                    </div>
                    <p className="mt-5 text-center text-sm text-text-tertiary">
                      Prices adjust with complexity — you always get a clear quote before anything
                      starts.
                    </p>
                  </m.div>
                ) : (
                  <m.div
                    key="subscription"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -8 }}
                    transition={{ duration: 0.4, ease: EXPO }}
                  >
                    <div className="flex justify-center">
                      <SegmentedToggle<Frequency>
                        value={frequency}
                        onChange={setFrequency}
                        layoutId="pricing-frequency"
                        options={[
                          { value: "monthly", label: "Monthly" },
                          { value: "yearly", label: "Yearly" },
                        ]}
                      />
                    </div>
                    <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-3">
                      {SUBSCRIPTION_PLANS.map((plan) => (
                        <SubscriptionCard
                          key={plan.name}
                          plan={plan}
                          frequency={frequency}
                          showTrail={showTrail}
                        />
                      ))}
                    </div>
                  </m.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </MotionConfig>
      </LazyMotion>
    </section>
  );
}
