"use client";

import { useState } from "react";
import { ChevronLeft, CalendarCheck } from "lucide-react";
import { HeroButton } from "@/components/ui/HeroButton";
import { fieldBase, fieldOk, fieldErr } from "@/components/ui/fieldStyles";
import { cn } from "@/lib/utils";
import { tw } from "@/components/booking/i18n";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export interface BookingDetails {
  name: string;
  email: string;
  note: string;
  website: string; // honeypot
}

interface Props {
  slotLabel: string;
  onBack: () => void;
  onSubmit: (d: BookingDetails) => void;
  locale?: string;
}

export function BookingDetailsForm({ slotLabel, onBack, onSubmit, locale = "en" }: Props) {
  const [values, setValues] = useState<BookingDetails>({
    name: "",
    email: "",
    note: "",
    website: "",
  });
  const [errors, setErrors] = useState<{ name?: string; email?: string }>({});

  function update<K extends keyof BookingDetails>(key: K) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setValues((v) => ({ ...v, [key]: e.target.value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!values.name.trim()) next.name = tw(locale, "errorName");
    if (!EMAIL_RE.test(values.email.trim())) next.email = tw(locale, "errorEmail");
    setErrors(next);
    if (Object.keys(next).length === 0) onSubmit(values);
  }

  return (
    <form noValidate onSubmit={handleSubmit} className="space-y-4">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1 text-sm text-text-secondary outline-none transition-colors hover:text-accent focus-visible:text-accent"
      >
        <ChevronLeft className="h-4 w-4" /> {tw(locale, "back")}
      </button>
      <p className="font-display text-sm font-semibold text-accent">{slotLabel}</p>

      <div>
        <label
          htmlFor="booking-name"
          className="mb-1.5 block text-sm font-medium text-text-secondary"
        >
          {tw(locale, "fieldName")} <span className="text-accent">*</span>
        </label>
        <input
          id="booking-name"
          type="text"
          autoComplete="name"
          value={values.name}
          onChange={update("name")}
          aria-invalid={!!errors.name}
          aria-describedby={errors.name ? "booking-name-error" : undefined}
          className={cn(fieldBase, errors.name ? fieldErr : fieldOk)}
          placeholder={tw(locale, "placeholderName")}
        />
        {errors.name && (
          <p id="booking-name-error" role="alert" className="mt-1.5 text-xs text-red-400">
            {errors.name}
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="booking-email"
          className="mb-1.5 block text-sm font-medium text-text-secondary"
        >
          {tw(locale, "fieldEmail")} <span className="text-accent">*</span>
        </label>
        <input
          id="booking-email"
          type="email"
          autoComplete="email"
          value={values.email}
          onChange={update("email")}
          aria-invalid={!!errors.email}
          aria-describedby={errors.email ? "booking-email-error" : undefined}
          className={cn(fieldBase, errors.email ? fieldErr : fieldOk)}
          placeholder={tw(locale, "placeholderEmail")}
        />
        {errors.email && (
          <p id="booking-email-error" role="alert" className="mt-1.5 text-xs text-red-400">
            {errors.email}
          </p>
        )}
      </div>

      <div>
        <label
          htmlFor="booking-note"
          className="mb-1.5 block text-sm font-medium text-text-secondary"
        >
          {tw(locale, "fieldNoteLabel")}{" "}
          <span className="text-text-tertiary">{tw(locale, "fieldNoteOptional")}</span>
        </label>
        <textarea
          id="booking-note"
          rows={3}
          value={values.note}
          onChange={update("note")}
          className={cn(fieldBase, "resize-y", fieldOk)}
          placeholder={tw(locale, "placeholderNote")}
        />
      </div>

      <input
        type="text"
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        value={values.website}
        onChange={update("website")}
        className="absolute left-[-9999px] h-0 w-0 opacity-0"
        name="website"
      />

      <HeroButton type="submit" variant="primary" className="w-full">
        <CalendarCheck className="h-4 w-4" aria-hidden={true} /> {tw(locale, "schedule")}
      </HeroButton>
    </form>
  );
}
