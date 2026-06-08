import type { Metadata } from "next";
import { contact } from "@/content/contact";
import { ContactInfo } from "@/components/contact/ContactInfo";
import { ContactChannel } from "@/components/contact/ContactChannel";

export const metadata: Metadata = {
  title: "Contact — Roman Technologies",
  description: contact.hero.lead,
};

/**
 * Contact page. Copy + the contact details live in `src/content/contact.json`.
 * The hero is static HTML (instant paint, CSS fade); the info list and the
 * message form are client islands.
 */
export default function ContactPage() {
  const { hero, details } = contact;

  return (
    <div className="bg-black">
      {/* Hero */}
      <section className="relative overflow-hidden px-6 pb-12 pt-14 sm:pb-16 sm:pt-24">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute left-1/2 top-0 h-[400px] w-[660px] -translate-x-1/2 rounded-full opacity-50 blur-3xl"
          style={{
            background: "radial-gradient(circle, rgba(201,169,97,0.12), rgba(201,169,97,0) 70%)",
          }}
        />
        <div className="animate-fade-down relative z-10 mx-auto max-w-2xl text-center">
          <p className="mb-5 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
            {hero.eyebrow}
          </p>
          <h1 className="text-balance font-display text-[clamp(2.25rem,6vw,4rem)] font-bold leading-[1.04] tracking-[-0.02em] text-text-primary">
            {hero.title}
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-[1.0625rem] leading-relaxed text-text-secondary sm:text-[1.15rem]">
            {hero.lead}
          </p>
        </div>
      </section>

      {/* Direct details + message form */}
      <section className="px-6 pb-24 sm:pb-32">
        <div className="mx-auto grid max-w-5xl grid-cols-1 gap-10 lg:grid-cols-5 lg:gap-14">
          <div className="lg:col-span-2">
            <ContactInfo details={details} />
          </div>
          <div className="lg:col-span-3">
            <ContactChannel recipient={details.email} />
          </div>
        </div>
      </section>
    </div>
  );
}
