"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { Loader2, Plus, Trash2, X } from "lucide-react";
import {
  LEAD_TYPE_LABEL,
  WEB_PRESENCE_LABEL,
  type LeadType,
  type WebPresence,
} from "@/lib/leadEnums";
import { dashAccent } from "@/lib/dashboardTheme";
import { AnimatedSelect } from "@/components/dashboard/AnimatedSelect";
import type { LeadCreateInput, LeadReviewInput } from "./types";

interface Props {
  open: boolean;
  onClose: () => void;
  onCreate: (payload: LeadCreateInput) => Promise<void>;
}

const DRAWER_VARIANTS = {
  hidden: { x: "100%" },
  visible: { x: 0 },
};

const BACKDROP_VARIANTS = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

const EMPTY_REVIEW: LeadReviewInput = { author: "", rating: null, text: "", date: "" };

export function AddLeadDrawer({ open, onClose, onCreate }: Props) {
  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            key="backdrop"
            variants={BACKDROP_VARIANTS}
            initial="hidden"
            animate="visible"
            exit="hidden"
            transition={{ duration: 0.18, ease: "easeOut" }}
            onClick={onClose}
            className="fixed inset-0 z-40 bg-black/40"
          />
          <motion.aside
            key="drawer"
            variants={DRAWER_VARIANTS}
            initial="hidden"
            animate="visible"
            exit="hidden"
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="lead-drawer no-scrollbar fixed right-0 top-0 z-50 h-full w-full md:w-[40rem] overflow-y-auto bg-white dark:bg-zinc-950 shadow-2xl"
          >
            <DrawerBody onClose={onClose} onCreate={onCreate} />
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function DrawerBody({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (payload: LeadCreateInput) => Promise<void>;
}) {
  const prefersReduced = useReducedMotion();
  const press = prefersReduced ? {} : { whileTap: { scale: 0.97 } };

  // Identity
  const [businessName, setBusinessName] = useState("");
  const [category, setCategory] = useState("");
  const [description, setDescription] = useState("");
  const [about, setAbout] = useState("");

  // Location
  const [country, setCountry] = useState("");
  const [region, setRegion] = useState("");
  const [city, setCity] = useState("");
  const [address, setAddress] = useState("");
  const [postalCode, setPostalCode] = useState("");

  // Contact & links
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [facebookUrl, setFacebookUrl] = useState("");
  const [instagramUrl, setInstagramUrl] = useState("");

  // Presence & Product
  const [webPresence, setWebPresence] = useState<WebPresence>("unknown");
  const [leadType, setLeadType] = useState<LeadType>("website");

  // Ratings & Reviews
  const [rating, setRating] = useState("");
  const [reviewCount, setReviewCount] = useState("");
  const [reviews, setReviews] = useState<LeadReviewInput[]>([]);

  // Opening hours (free-form, one "Day: hours" per line)
  const [openingHours, setOpeningHours] = useState("");

  // Notes
  const [notes, setNotes] = useState("");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateReview(i: number, patch: Partial<LeadReviewInput>) {
    setReviews((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  function removeReview(i: number) {
    setReviews((prev) => prev.filter((_, idx) => idx !== i));
  }

  function parseOpeningHours(): Record<string, string> | null {
    const map: Record<string, string> = {};
    for (const line of openingHours.split("\n")) {
      const idx = line.indexOf(":");
      if (idx === -1) continue;
      const day = line.slice(0, idx).trim();
      const hours = line.slice(idx + 1).trim();
      if (day) map[day] = hours;
    }
    return Object.keys(map).length ? map : null;
  }

  function buildPayload(): LeadCreateInput | null {
    const name = businessName.trim();
    if (!name) {
      setError("Business name is required.");
      return null;
    }

    const ratingNum = rating.trim() === "" ? null : Number(rating);
    if (ratingNum != null && (Number.isNaN(ratingNum) || ratingNum < 0)) {
      setError("Rating must be a non-negative number.");
      return null;
    }
    const reviewCountNum = reviewCount.trim() === "" ? null : Number(reviewCount);
    if (reviewCountNum != null && (Number.isNaN(reviewCountNum) || reviewCountNum < 0)) {
      setError("Review count must be a non-negative number.");
      return null;
    }

    const trim = (v: string) => {
      const t = v.trim();
      return t === "" ? null : t;
    };

    return {
      business_name: name,
      lead_type: leadType,
      web_presence: webPresence,
      category: trim(category),
      description: trim(description),
      about: trim(about),
      country: trim(country),
      region: trim(region),
      city: trim(city),
      address: trim(address),
      postal_code: trim(postalCode),
      phone: trim(phone),
      email: trim(email),
      website_url: trim(websiteUrl),
      facebook_url: trim(facebookUrl),
      instagram_url: trim(instagramUrl),
      rating: ratingNum,
      review_count: reviewCountNum,
      reviews,
      opening_hours: parseOpeningHours(),
      notes: trim(notes),
    };
  }

  async function handleSubmit() {
    setError(null);
    const payload = buildPayload();
    if (!payload) return;
    setSaving(true);
    try {
      await onCreate(payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create lead");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="p-5">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
            New lead
          </div>
          <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100">Add lead</h2>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => {
              handleSubmit().catch(() => {});
            }}
            disabled={saving}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md cursor-pointer disabled:cursor-not-allowed ${dashAccent.ctaPrimary}`}
          >
            {saving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Plus className="h-3.5 w-3.5" />
            )}
            Add lead
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close add lead"
            className="h-8 w-8 inline-flex items-center justify-center rounded-md text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-100 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-3 rounded-md bg-red-50 dark:bg-red-950 px-3 py-2 text-xs text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {/* Identity */}
      <FormSection title="Identity">
        <Field label="Business name" required>
          <Input value={businessName} onChange={setBusinessName} ariaLabel="Business name" />
        </Field>
        <Field label="Category">
          <Input value={category} onChange={setCategory} ariaLabel="Category" />
        </Field>
        <Field label="Description">
          <Textarea value={description} onChange={setDescription} ariaLabel="Description" />
        </Field>
        <Field label="About">
          <Textarea value={about} onChange={setAbout} ariaLabel="About" />
        </Field>
      </FormSection>

      {/* Location */}
      <FormSection title="Location">
        <Field label="Country">
          <Input value={country} onChange={setCountry} ariaLabel="Country" />
        </Field>
        <Field label="Region">
          <Input value={region} onChange={setRegion} ariaLabel="Region" />
        </Field>
        <Field label="City">
          <Input value={city} onChange={setCity} ariaLabel="City" />
        </Field>
        <Field label="Address">
          <Input value={address} onChange={setAddress} ariaLabel="Address" />
        </Field>
        <Field label="Postal code">
          <Input value={postalCode} onChange={setPostalCode} ariaLabel="Postal code" />
        </Field>
      </FormSection>

      {/* Contact & links */}
      <FormSection title="Contact & links">
        <Field label="Phone">
          <Input value={phone} onChange={setPhone} ariaLabel="Phone" type="tel" />
        </Field>
        <Field label="Email">
          <Input value={email} onChange={setEmail} ariaLabel="Email" type="email" />
        </Field>
        <Field label="Website URL">
          <Input value={websiteUrl} onChange={setWebsiteUrl} ariaLabel="Website URL" />
        </Field>
        <Field label="Facebook URL">
          <Input value={facebookUrl} onChange={setFacebookUrl} ariaLabel="Facebook URL" />
        </Field>
        <Field label="Instagram URL">
          <Input value={instagramUrl} onChange={setInstagramUrl} ariaLabel="Instagram URL" />
        </Field>
      </FormSection>

      {/* Presence & Product */}
      <FormSection title="Presence & Product">
        <Field label="Web presence">
          <AnimatedSelect
            value={webPresence}
            onChange={(v) => setWebPresence(v as WebPresence)}
            ariaLabel="Web presence"
            options={(Object.keys(WEB_PRESENCE_LABEL) as WebPresence[]).map((k) => ({
              value: k,
              label: WEB_PRESENCE_LABEL[k],
            }))}
          />
        </Field>
        <Field label="Product">
          <AnimatedSelect
            value={leadType}
            onChange={(v) => setLeadType(v as LeadType)}
            ariaLabel="Product"
            options={(Object.keys(LEAD_TYPE_LABEL) as LeadType[]).map((k) => ({
              value: k,
              label: LEAD_TYPE_LABEL[k],
            }))}
          />
        </Field>
      </FormSection>

      {/* Ratings & Reviews */}
      <FormSection title="Ratings & Reviews">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Rating">
            <Input
              value={rating}
              onChange={setRating}
              ariaLabel="Rating"
              type="number"
              placeholder="0.0"
            />
          </Field>
          <Field label="Review count">
            <Input
              value={reviewCount}
              onChange={setReviewCount}
              ariaLabel="Review count"
              type="number"
              placeholder="0"
            />
          </Field>
        </div>

        <div className="space-y-2">
          <AnimatePresence initial={false}>
            {reviews.map((r, i) => (
              <motion.div
                key={i}
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: prefersReduced ? 0 : 0.2, ease: "easeOut" }}
                className="overflow-hidden"
              >
                <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium text-zinc-500 dark:text-zinc-400">
                      Review {i + 1}
                    </span>
                    <button
                      type="button"
                      onClick={() => removeReview(i)}
                      aria-label={`Remove review ${i + 1}`}
                      className="inline-flex h-6 w-6 items-center justify-center rounded-md text-zinc-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 cursor-pointer"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Input
                      value={r.author}
                      onChange={(v) => updateReview(i, { author: v })}
                      ariaLabel={`Review ${i + 1} author`}
                      placeholder="Author"
                    />
                    <Input
                      value={r.rating != null ? String(r.rating) : ""}
                      onChange={(v) =>
                        updateReview(i, { rating: v.trim() === "" ? null : Number(v) })
                      }
                      ariaLabel={`Review ${i + 1} rating`}
                      type="number"
                      placeholder="Rating"
                    />
                  </div>
                  <Textarea
                    value={r.text}
                    onChange={(v) => updateReview(i, { text: v })}
                    ariaLabel={`Review ${i + 1} text`}
                    placeholder="Review text"
                  />
                  <Input
                    value={r.date}
                    onChange={(v) => updateReview(i, { date: v })}
                    ariaLabel={`Review ${i + 1} date`}
                    placeholder="Date (e.g. 2 weeks ago)"
                  />
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
          <motion.button
            {...press}
            type="button"
            onClick={() => setReviews((prev) => [...prev, { ...EMPTY_REVIEW }])}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 cursor-pointer transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            Add review
          </motion.button>
        </div>
      </FormSection>

      {/* Opening hours */}
      <FormSection title="Opening hours">
        <Field label="One day per line, e.g. “Monday: 9–17”">
          <Textarea
            value={openingHours}
            onChange={setOpeningHours}
            ariaLabel="Opening hours"
            rows={4}
            placeholder={"Monday: 9–17\nTuesday: Closed"}
          />
        </Field>
      </FormSection>

      {/* Notes */}
      <FormSection title="Notes">
        <Field label="Notes">
          <Textarea value={notes} onChange={setNotes} ariaLabel="Notes" />
        </Field>
      </FormSection>
    </div>
  );
}

function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-5 space-y-3">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1">
        {label}
        {required && <span className="text-accent"> *</span>}
      </label>
      {children}
    </div>
  );
}

function Input({
  value,
  onChange,
  ariaLabel,
  type = "text",
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  ariaLabel: string;
  type?: string;
  placeholder?: string;
}) {
  return (
    <input
      type={type}
      aria-label={ariaLabel}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`w-full rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 ${dashAccent.focusRing}`}
    />
  );
}

function Textarea({
  value,
  onChange,
  ariaLabel,
  rows = 3,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  ariaLabel: string;
  rows?: number;
  placeholder?: string;
}) {
  return (
    <textarea
      rows={rows}
      aria-label={ariaLabel}
      placeholder={placeholder}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`w-full rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 resize-none ${dashAccent.focusRing}`}
    />
  );
}
