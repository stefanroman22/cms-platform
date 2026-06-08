"use client";

import { m } from "motion/react";
import { SubmitFeedback, type SubmitStatus } from "@/components/ui/SubmitFeedback";
import { tw } from "@/components/booking/i18n";

const EXPO = [0.16, 1, 0.3, 1] as const;

interface Props {
  status: SubmitStatus;
  slotLabel: string;
  /** Optional contact email shown in the error state. Pass null to omit. */
  contactEmail: string | null;
  onReset: () => void;
  locale?: string;
}

export function BookingConfirmation({
  status,
  slotLabel,
  contactEmail,
  onReset,
  locale = "en",
}: Props) {
  return (
    <div>
      <SubmitFeedback
        status={status}
        loadingText={tw(locale, "bookingLoading")}
        successText={tw(locale, "bookingSuccess")}
        errorText={
          contactEmail ? (
            <>
              {tw(locale, "bookingErrorContact")}{" "}
              <a
                href={`mailto:${contactEmail}`}
                className="text-accent underline-offset-2 hover:underline"
              >
                {contactEmail}
              </a>
              .
            </>
          ) : (
            <>{tw(locale, "bookingErrorNoContact")}</>
          )
        }
      />
      {status === "success" && (
        <m.p
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: EXPO, delay: 0.2 }}
          className="text-center text-sm text-text-secondary"
        >
          {slotLabel}
        </m.p>
      )}
      {status !== "loading" && (
        <div className="mt-4 text-center">
          <button
            type="button"
            onClick={onReset}
            className="text-sm font-medium text-text-secondary underline-offset-4 outline-none transition-colors hover:text-accent focus-visible:underline"
          >
            {status === "success" ? tw(locale, "bookAnother") : tw(locale, "tryAgain")}
          </button>
        </div>
      )}
    </div>
  );
}
