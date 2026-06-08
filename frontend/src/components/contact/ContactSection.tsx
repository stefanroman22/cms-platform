"use client";

import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { Reveal } from "@/components/motion/Reveal";
import { BookingCalendar } from "@/components/booking/BookingCalendar";
import { ContactForm } from "@/components/contact/ContactForm";
import { contact } from "@/content/contact";

/**
 * Home-page contact section: a custom booking calendar and the shared
 * ContactForm, side by side on desktop and stacked on mobile. Each block fades
 * in on scroll.
 */
export function ContactSection() {
  return (
    <section id="contact" className="relative overflow-hidden bg-black px-6 py-16 lg:py-24">
      {/* Subtle gold ambient glow, echoing the hero + pricing sections. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-16 h-[440px] w-[720px] -translate-x-1/2 rounded-full opacity-60 blur-3xl"
        style={{
          background: "radial-gradient(circle, rgba(201,169,97,0.10), rgba(201,169,97,0) 70%)",
        }}
      />

      <LazyMotion features={domAnimation}>
        <MotionConfig reducedMotion="user">
          <div className="relative z-10 mx-auto max-w-5xl">
            <Reveal inView amount={0.4} className="mx-auto max-w-2xl text-center">
              <p className="mb-4 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
                Let&apos;s talk
              </p>
              <h2 className="font-display text-[clamp(2rem,5vw,3.25rem)] font-bold leading-[1.05] tracking-[-0.02em] text-text-primary">
                Book a call or send a message
              </h2>
              <p className="mx-auto mt-5 max-w-xl text-[1.0625rem] leading-relaxed text-text-secondary">
                Grab a 45-minute slot with me, Stefan — or leave your details below and I&apos;ll
                reply within one business day.
              </p>
            </Reveal>

            <div className="mt-12 grid grid-cols-1 items-start gap-6 lg:grid-cols-2 lg:gap-8">
              <Reveal inView amount={0.15} direction="up" distance={28}>
                <BookingCalendar
                  slug="roman-technologies-website"
                  heading="Book a call with Stefan"
                  subheading="45-minute call"
                  avatarUrl="/team/stefan-roman-call-picture.jpeg"
                />
              </Reveal>
              <Reveal inView amount={0.15} direction="up" distance={28} delay={0.1}>
                <ContactForm recipient={contact.details.email} />
              </Reveal>
            </div>
          </div>
        </MotionConfig>
      </LazyMotion>
    </section>
  );
}
