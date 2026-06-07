"use client";

import { useState } from "react";
import { m } from "motion/react";
import { Mail, Linkedin } from "lucide-react";
import { Reveal, REVEAL_EASE } from "@/components/motion/Reveal";
import type { TeamMember } from "@/content/about";

const iconBtn =
  "inline-flex h-9 w-9 items-center justify-center rounded-lg border border-border text-text-secondary outline-none transition-colors hover:border-accent/50 hover:text-accent focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg";

export function TeamMemberCard({ member, index }: { member: TeamMember; index: number }) {
  // Pointer devices reveal the overlay on hover; touch devices toggle it on tap.
  const [active, setActive] = useState(false);
  const [canHover] = useState(() =>
    typeof window === "undefined" ? true : (window.matchMedia?.("(hover: hover)").matches ?? true)
  );

  return (
    <Reveal inView amount={0.2} delay={index * 0.08}>
      <article className="flex flex-col">
        <m.div
          className="relative cursor-pointer overflow-hidden rounded-2xl border border-border bg-surface"
          onHoverStart={() => canHover && setActive(true)}
          onHoverEnd={() => canHover && setActive(false)}
          onTap={() => !canHover && setActive((v) => !v)}
        >
          <m.img
            src={member.image}
            alt={member.name}
            width={480}
            height={600}
            loading="lazy"
            className="aspect-[4/5] w-full select-none object-cover"
            animate={{ scale: active ? 1.05 : 1 }}
            transition={{ duration: 0.5, ease: REVEAL_EASE }}
          />

          {/* Darkening + description overlay — fades in on hover/tap. */}
          <m.div
            className="absolute inset-0 flex items-end p-5"
            style={{
              background:
                "linear-gradient(to top, rgba(8,8,10,0.94) 0%, rgba(8,8,10,0.6) 45%, rgba(8,8,10,0) 100%)",
            }}
            initial={false}
            animate={{ opacity: active ? 1 : 0 }}
            transition={{ duration: 0.4, ease: REVEAL_EASE }}
          >
            <m.p
              className="text-sm leading-relaxed text-text-primary"
              animate={{ opacity: active ? 1 : 0, y: active ? 0 : 12 }}
              transition={{ duration: 0.4, ease: REVEAL_EASE }}
            >
              {member.description}
            </m.p>
          </m.div>
        </m.div>

        <div className="mt-4">
          <h3 className="font-display text-lg font-semibold text-text-primary">{member.name}</h3>
          <p className="mt-0.5 text-sm font-medium text-accent">{member.role}</p>

          <div className="mt-3 flex items-center gap-2">
            <a
              href={`mailto:${member.email}`}
              aria-label={`Email ${member.name}`}
              className={iconBtn}
            >
              <Mail className="h-4 w-4" aria-hidden="true" />
            </a>
            <a
              href={member.linkedin}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`${member.name} on LinkedIn`}
              className={iconBtn}
            >
              <Linkedin className="h-4 w-4" aria-hidden="true" />
            </a>
          </div>
        </div>
      </article>
    </Reveal>
  );
}
