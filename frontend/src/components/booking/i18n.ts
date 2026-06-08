/**
 * Widget i18n — English now, pluggable.
 *
 * Add a language by adding a dict keyed by its BCP-47 locale tag.
 * `tw(locale, key)` returns the string for `locale`, falling back to English
 * when the locale is unknown or the key is missing in that locale's dict.
 */

export const STRINGS = {
  en: {
    // ── BookingCalendar ──────────────────────────────────────────────────────
    bookUnavailable: "Booking is currently unavailable.",
    rescheduleHeading: "Reschedule your appointment",
    bookWithName: "Book with {name}",
    bookHeading: "Book an appointment",
    selectService: "Select a service",
    durationSuffix: " min",
    back: "Back",
    moveAppointmentTo: "Move your appointment to",
    confirmNewTime: "Confirm new time",

    // ── MonthGrid ────────────────────────────────────────────────────────────
    loadingAvailability: "Loading availability…",
    prevMonth: "Previous month",
    nextMonth: "Next month",

    // ── TimeSlots ────────────────────────────────────────────────────────────
    timesIn: "Times in",
    loadingTimes: "Loading times…",
    noTimesAvailable: "No times available this day.",

    // ── BookingDetailsForm ───────────────────────────────────────────────────
    fieldName: "Name",
    fieldEmail: "Email",
    fieldNoteLabel: "What would you like to discuss?",
    fieldNoteOptional: "(optional)",
    placeholderName: "Jane Doe",
    placeholderEmail: "jane@company.com",
    placeholderNote: "A sentence or two of context.",
    errorName: "Please add your name.",
    errorEmail: "That email does not look right.",
    schedule: "Schedule",

    // ── BookingConfirmation ──────────────────────────────────────────────────
    bookingLoading: "Booking your appointment…",
    bookingSuccess: "You’re booked — check your email!",
    bookingErrorNoContact: "Could not book that slot. Please try again.",
    bookingErrorContact: "Could not book that slot. Email us directly at",
    bookAnother: "Book another time",
    tryAgain: "Try again",
  },
} as const;

export type Locale = keyof typeof STRINGS;
export type StringKey = keyof (typeof STRINGS)[Locale];

/**
 * Return the widget string for `key` in `locale`.
 * Falls back to English when `locale` is not in STRINGS or the key is absent.
 */
export function tw(locale: string, key: StringKey): string {
  const table: Record<StringKey, string> =
    (STRINGS as Record<string, Record<StringKey, string>>)[locale] ?? STRINGS.en;
  return table[key] ?? STRINGS.en[key];
}
