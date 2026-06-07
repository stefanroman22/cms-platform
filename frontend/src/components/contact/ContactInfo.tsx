"use client";

import { type ComponentType } from "react";
import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { Mail, Phone, MapPin, Clock } from "lucide-react";
import { Reveal } from "@/components/motion/Reveal";
import type { ContactDetails } from "@/content/contact";

function Row({
  icon: Icon,
  label,
  value,
  sub,
  href,
  delay,
}: {
  icon: ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  label: string;
  value: string;
  sub?: string;
  href?: string;
  delay: number;
}) {
  const inner = (
    <>
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-border bg-surface/50 text-accent transition-colors group-hover:border-accent/40">
        <Icon className="h-5 w-5" aria-hidden={true} />
      </span>
      <span className="min-w-0">
        <span className="block text-xs font-medium uppercase tracking-wider text-text-tertiary">
          {label}
        </span>
        <span className="mt-1 block break-words text-[0.95rem] text-text-primary transition-colors group-hover:text-accent">
          {value}
        </span>
        {sub ? <span className="mt-0.5 block text-sm text-text-secondary">{sub}</span> : null}
      </span>
    </>
  );

  return (
    <Reveal as="li" inView amount={0.4} delay={delay}>
      {href ? (
        <a
          href={href}
          className="group flex items-start gap-4 rounded-lg outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
        >
          {inner}
        </a>
      ) : (
        <div className="group flex items-start gap-4">{inner}</div>
      )}
    </Reveal>
  );
}

export function ContactInfo({ details }: { details: ContactDetails }) {
  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <div>
          <Reveal inView amount={0.4}>
            <h2 className="font-display text-xl font-semibold text-text-primary">
              Reach us directly
            </h2>
          </Reveal>
          <Reveal inView amount={0.4} delay={0.05}>
            <p className="mt-2 text-sm leading-relaxed text-text-secondary">
              Prefer email or a quick call? Here is where to find us.
            </p>
          </Reveal>

          <ul className="mt-8 space-y-6">
            <Row
              icon={Mail}
              label="Email"
              value={details.email}
              href={`mailto:${details.email}`}
              delay={0.05}
            />
            <Row
              icon={Phone}
              label="Phone"
              value={details.phone}
              href={`tel:${details.phoneHref}`}
              delay={0.1}
            />
            <Row
              icon={MapPin}
              label="Location"
              value={details.location}
              sub={details.address || undefined}
              delay={0.15}
            />
            <Row icon={Clock} label="Hours" value={details.hours} delay={0.2} />
          </ul>
        </div>
      </MotionConfig>
    </LazyMotion>
  );
}
