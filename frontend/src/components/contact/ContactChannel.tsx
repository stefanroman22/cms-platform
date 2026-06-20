"use client";

import { useState } from "react";
import { LazyMotion, domMax, MotionConfig, AnimatePresence, m } from "motion/react";
import { useTranslations } from "next-intl";
import { SegmentedToggle } from "@/components/ui/SegmentedToggle";
import { ContactForm } from "@/components/contact/ContactForm";
import { BookingCalendar } from "@/components/booking/BookingCalendar";

const EXPO = [0.16, 1, 0.3, 1] as const;

type Channel = "email" | "call";

/**
 * Right column of the contact page: a pill switcher (the same toggle used in
 * pricing) above the chosen channel — the message form ("Email") or the home
 * page's booking calendar ("Book a call"). The switcher sits at the very top so
 * it lines up with the "Reach us directly" heading in the left column; the form
 * / calendar drops in below it.
 */
export function ContactChannel({ recipient }: { recipient: string }) {
  const [channel, setChannel] = useState<Channel>("email");
  const tChannel = useTranslations("contactChannel");
  const tSection = useTranslations("contactSection");

  return (
    <LazyMotion features={domMax}>
      <MotionConfig reducedMotion="user">
        <SegmentedToggle<Channel>
          value={channel}
          onChange={setChannel}
          layoutId="contact-channel"
          options={[
            { value: "email", label: tChannel("email") },
            { value: "call", label: tChannel("bookCall") },
          ]}
        />

        <div className="mt-6">
          <AnimatePresence mode="wait">
            {channel === "email" ? (
              <m.div
                key="email"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.35, ease: EXPO }}
              >
                <ContactForm recipient={recipient} />
              </m.div>
            ) : (
              <m.div
                key="call"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.35, ease: EXPO }}
              >
                <BookingCalendar
                  slug="roman-technologies-website"
                  heading={tSection("bookingHeading")}
                  subheading={tSection("bookingSubheading")}
                  avatarUrl="/team/stefan-roman-call-picture.jpeg"
                />
              </m.div>
            )}
          </AnimatePresence>
        </div>
      </MotionConfig>
    </LazyMotion>
  );
}
