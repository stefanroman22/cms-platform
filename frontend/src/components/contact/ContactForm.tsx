"use client";

import { useState } from "react";
import { LazyMotion, domAnimation, MotionConfig, AnimatePresence, m } from "motion/react";
import { Send } from "lucide-react";
import { HeroButton } from "@/components/ui/HeroButton";
import { SubmitFeedback } from "@/components/ui/SubmitFeedback";
import { cn } from "@/lib/utils";
import { fieldBase, fieldOk, fieldErr } from "@/components/ui/fieldStyles";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const EXPO = [0.16, 1, 0.3, 1] as const;
/** Keep the spinner visible long enough to read on a fast send. */
const MIN_SPINNER_MS = 700;

type Field = "name" | "email" | "company" | "message";
type Phase = "idle" | "sending" | "sent" | "error";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function ContactForm({ recipient }: { recipient: string }) {
  const [values, setValues] = useState<Record<Field, string>>({
    name: "",
    email: "",
    company: "",
    message: "",
  });
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [phase, setPhase] = useState<Phase>("idle");

  const update = (key: Field) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setValues((v) => ({ ...v, [key]: e.target.value }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  function validate(): Partial<Record<Field, string>> {
    const e: Partial<Record<Field, string>> = {};
    if (!values.name.trim()) e.name = "Please add your name.";
    if (!values.email.trim()) e.email = "Please add your email.";
    else if (!EMAIL_RE.test(values.email.trim())) e.email = "That email does not look right.";
    if (values.message.trim().length < 10)
      e.message = "Tell us a little more (at least 10 characters).";
    return e;
  }

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = validate();
    setErrors(next);
    if (Object.keys(next).length > 0) {
      const first = (["name", "email", "message"] as Field[]).find((k) => next[k]);
      if (first) document.getElementById(`contact-${first}`)?.focus();
      return;
    }

    setPhase("sending");
    try {
      const [res] = await Promise.all([
        fetch("/api/forms/contact", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: values.name.trim(),
            email: values.email.trim(),
            company: values.company.trim(),
            message: values.message.trim(),
          }),
        }),
        sleep(MIN_SPINNER_MS),
      ]);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { success?: boolean };
      if (!data?.success) throw new Error("send failed");
      setPhase("sent");
    } catch {
      setPhase("error");
    }
  }

  function reset(clearValues: boolean) {
    if (clearValues) setValues({ name: "", email: "", company: "", message: "" });
    setErrors({});
    setPhase("idle");
  }

  const showFeedback = phase !== "idle";

  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <div className="rounded-2xl border border-border bg-surface/30 p-6 backdrop-blur-sm sm:p-8">
          <AnimatePresence mode="wait" initial={false}>
            {showFeedback ? (
              <m.div
                key="feedback"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3, ease: EXPO }}
              >
                <SubmitFeedback
                  status={phase === "sending" ? "loading" : phase === "sent" ? "success" : "error"}
                  successText="Message sent — talk soon!"
                  errorText={
                    <>
                      Something went wrong. Email me directly at{" "}
                      <a
                        href={`mailto:${recipient}`}
                        className="text-accent underline-offset-2 hover:underline"
                      >
                        {recipient}
                      </a>
                      .
                    </>
                  }
                />
                {phase !== "sending" && (
                  <div className="text-center">
                    <button
                      type="button"
                      onClick={() => reset(phase === "sent")}
                      className="text-sm font-medium text-text-secondary underline-offset-4 outline-none transition-colors hover:text-accent focus-visible:underline"
                    >
                      {phase === "sent" ? "Send another message" : "Try again"}
                    </button>
                  </div>
                )}
              </m.div>
            ) : (
              <m.form
                key="form"
                noValidate
                onSubmit={handleSubmit}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3, ease: EXPO }}
                className="space-y-5"
              >
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                  <div>
                    <label
                      htmlFor="contact-name"
                      className="mb-1.5 block text-sm font-medium text-text-secondary"
                    >
                      Name <span className="text-accent">*</span>
                    </label>
                    <input
                      id="contact-name"
                      name="name"
                      type="text"
                      autoComplete="name"
                      value={values.name}
                      onChange={update("name")}
                      aria-invalid={!!errors.name}
                      aria-describedby={errors.name ? "contact-name-error" : undefined}
                      className={cn(fieldBase, errors.name ? fieldErr : fieldOk)}
                      placeholder="Jane Doe"
                    />
                    {errors.name && (
                      <p
                        id="contact-name-error"
                        role="alert"
                        className="mt-1.5 text-xs text-red-400"
                      >
                        {errors.name}
                      </p>
                    )}
                  </div>

                  <div>
                    <label
                      htmlFor="contact-email"
                      className="mb-1.5 block text-sm font-medium text-text-secondary"
                    >
                      Email <span className="text-accent">*</span>
                    </label>
                    <input
                      id="contact-email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      value={values.email}
                      onChange={update("email")}
                      aria-invalid={!!errors.email}
                      aria-describedby={errors.email ? "contact-email-error" : undefined}
                      className={cn(fieldBase, errors.email ? fieldErr : fieldOk)}
                      placeholder="jane@company.com"
                    />
                    {errors.email && (
                      <p
                        id="contact-email-error"
                        role="alert"
                        className="mt-1.5 text-xs text-red-400"
                      >
                        {errors.email}
                      </p>
                    )}
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="contact-company"
                    className="mb-1.5 block text-sm font-medium text-text-secondary"
                  >
                    Company <span className="text-text-tertiary">(optional)</span>
                  </label>
                  <input
                    id="contact-company"
                    name="company"
                    type="text"
                    autoComplete="organization"
                    value={values.company}
                    onChange={update("company")}
                    className={cn(fieldBase, fieldOk)}
                    placeholder="Acme Inc."
                  />
                </div>

                <div>
                  <label
                    htmlFor="contact-message"
                    className="mb-1.5 block text-sm font-medium text-text-secondary"
                  >
                    Message <span className="text-accent">*</span>
                  </label>
                  <textarea
                    id="contact-message"
                    name="message"
                    rows={5}
                    value={values.message}
                    onChange={update("message")}
                    aria-invalid={!!errors.message}
                    aria-describedby={errors.message ? "contact-message-error" : undefined}
                    className={cn(fieldBase, "resize-y", errors.message ? fieldErr : fieldOk)}
                    placeholder="A few lines about your project, timeline and budget."
                  />
                  {errors.message && (
                    <p
                      id="contact-message-error"
                      role="alert"
                      className="mt-1.5 text-xs text-red-400"
                    >
                      {errors.message}
                    </p>
                  )}
                </div>

                <HeroButton type="submit" variant="primary" className="w-full">
                  <Send className="h-4 w-4" aria-hidden={true} />
                  Send message
                </HeroButton>

                <p className="text-center text-xs text-text-tertiary">
                  Or email us directly at{" "}
                  <a
                    href={`mailto:${recipient}`}
                    className="text-text-secondary underline-offset-2 hover:text-accent hover:underline"
                  >
                    {recipient}
                  </a>
                  .
                </p>
              </m.form>
            )}
          </AnimatePresence>
        </div>
      </MotionConfig>
    </LazyMotion>
  );
}
