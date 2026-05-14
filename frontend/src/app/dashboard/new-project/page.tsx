"use client";

import { useEffect, useRef, useState } from "react";
import { Send, ChevronUp } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { PageHeader } from "@/components/dashboard/PageHeader";
import { FormFeedback } from "@/components/dashboard/FormFeedback";
import { SubmitOverlay } from "@/components/dashboard/SubmitOverlay";
import { dashboardPrimaryBtnCn, dashboardInputLgCn, dashboardFieldLabelCn } from "@/lib/styles";

type SubmitPhase = "idle" | "sending" | "sent";

// Hold the green "sent" overlay long enough for the user to read the
// confirmation message before the overlay fades and the form resets
// to a fresh empty state. Tuned by feel — short enough to feel snappy,
// long enough that the confirmation isn't missed.
const SENT_DWELL_MS = 1800;

const PROJECT_TYPES = [
  { value: "website", label: "Website" },
  { value: "web_app", label: "Web Application" },
  { value: "mobile_app", label: "Mobile App" },
  { value: "combined", label: "Combined solution (e.g. website + mobile app)" },
  { value: "other", label: "Other" },
];

/**
 * Custom-styled select for the Project type field. Uses a button +
 * absolutely positioned listbox so the option list can animate in/out
 * with framer-motion. Closed-state arrow points up; opening rotates
 * it 180° so it points down — per design call.
 */
function AnimatedSelect({
  value,
  onChange,
  options,
  ariaLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  options: readonly { value: string; label: string }[];
  ariaLabel: string;
}) {
  const [open, setOpen] = useState(false);
  // When there isn't enough room below the button for the listbox + a
  // 10px breathing margin, open upward instead. Computed at the moment
  // the user clicks, not on every render — the button rect is stable
  // until layout changes, and we don't want a resize observer here.
  const [openUp, setOpenUp] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  function toggle() {
    if (!open && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      // Approx listbox height: 40px per option + a little padding for the
      // border / rounded corners. Good enough for the flip heuristic; an
      // exact measurement would need a layout-effect double-render.
      const approxListboxHeight = options.length * 40 + 16;
      setOpenUp(approxListboxHeight + 10 > spaceBelow);
    }
    setOpen((o) => !o);
  }

  // Close on click outside.
  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onEsc(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onEsc);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onEsc);
    };
  }, [open]);

  const current = options.find((o) => o.value === value) ?? options[0];

  return (
    <div ref={wrapRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={toggle}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        className={`${dashboardInputLgCn} flex cursor-pointer items-center justify-between text-left`}
      >
        <span className="truncate">{current.label}</span>
        <ChevronUp
          className={`ml-2 h-4 w-4 shrink-0 text-zinc-400 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
          aria-hidden="true"
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.ul
            role="listbox"
            initial={{ opacity: 0, y: openUp ? 6 : -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: openUp ? 6 : -6 }}
            transition={{ duration: 0.18, ease: "easeOut" }}
            className={`absolute left-0 right-0 z-20 overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-lg dark:border-zinc-700 dark:bg-zinc-800 ${
              openUp ? "bottom-full mb-2" : "top-full mt-2"
            }`}
          >
            {options.map((opt, i) => {
              const isSelected = opt.value === value;
              return (
                <motion.li
                  key={opt.value}
                  role="option"
                  aria-selected={isSelected}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.18, ease: "easeOut", delay: i * 0.03 }}
                  onClick={() => {
                    onChange(opt.value);
                    setOpen(false);
                  }}
                  className={`cursor-pointer px-3 py-2.5 text-sm transition-colors ${
                    isSelected
                      ? "bg-zinc-100 text-zinc-900 dark:bg-zinc-700 dark:text-zinc-100"
                      : "text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-700"
                  }`}
                >
                  {opt.label}
                </motion.li>
              );
            })}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}

const BUDGET_OPTIONS = [
  { value: "", label: "Prefer not to say" },
  { value: "under_1k", label: "Under €1,000" },
  { value: "1k_5k", label: "€1,000 – €5,000" },
  { value: "5k_20k", label: "€5,000 – €20,000" },
  { value: "20k_plus", label: "€20,000+" },
];

const TIMELINE_OPTIONS = [
  { value: "", label: "No preference" },
  { value: "asap", label: "As soon as possible" },
  { value: "1_month", label: "Within 1 month" },
  { value: "3_months", label: "Within 3 months" },
  { value: "6_months", label: "Within 6 months" },
  { value: "flexible", label: "Flexible" },
];

export default function CreateNewProjectPage() {
  const [name, setName] = useState("");
  const [type, setType] = useState("website");
  const [description, setDescription] = useState("");
  const [budget, setBudget] = useState("");
  const [timeline, setTimeline] = useState("");
  const [phase, setPhase] = useState<SubmitPhase>("idle");
  const [error, setError] = useState("");

  const isValid = name.trim() !== "" && description.trim() !== "";
  const loading = phase !== "idle";

  function resetForm() {
    setName("");
    setType("website");
    setDescription("");
    setBudget("");
    setTimeline("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!isValid) return;

    setPhase("sending");
    setError("");

    try {
      const res = await fetch("/api/project-requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          name: name.trim(),
          type,
          description: description.trim(),
          budget_range: budget || null,
          timeline: timeline || null,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data?.detail ?? "Failed to submit. Please try again.");
        setPhase("idle");
        return;
      }
      // Hold on the green "sent" overlay so the user reads the
      // confirmation, then drop the overlay and reset the form to a
      // fresh empty state — no intermediate success card.
      setPhase("sent");
      await new Promise((resolve) => setTimeout(resolve, SENT_DWELL_MS));
      resetForm();
      setPhase("idle");
    } catch {
      setError("An unexpected error occurred.");
      setPhase("idle");
    }
  }

  return (
    <div className="relative min-h-full">
      {/* SubmitOverlay covers this whole content area while the
          submission is in flight + during the brief green-confirm
          dwell. Sidebar stays interactive because the overlay sits
          inside the page wrapper, not at the dashboard root. */}
      <SubmitOverlay
        phase={phase}
        messages={{
          sending: "Sending your request…",
          sent: "Request sent — we'll be in touch soon.",
        }}
      />
      <div className="p-4 md:p-8">
        <div className="max-w-xl">
          <PageHeader
            title="Create New Project"
            description="Tell us about your idea and we'll get back to you with a proposal."
          />

          <form onSubmit={handleSubmit} className="space-y-5">
            <FormFeedback error={error || undefined} />

            <div>
              <label className={dashboardFieldLabelCn}>
                Project name <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Company website redesign"
                className={dashboardInputLgCn}
              />
            </div>

            <div>
              <label className={dashboardFieldLabelCn}>
                Project type <span className="text-red-400">*</span>
              </label>
              <AnimatedSelect
                value={type}
                onChange={setType}
                options={PROJECT_TYPES}
                ariaLabel="Project type"
              />
            </div>

            <div>
              <label className={dashboardFieldLabelCn}>
                Description <span className="text-red-400">*</span>
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what you'd like to build, its goals, and any specific requirements…"
                rows={5}
                className={`${dashboardInputLgCn} resize-none`}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={dashboardFieldLabelCn}>Budget range</label>
                <AnimatedSelect
                  value={budget}
                  onChange={setBudget}
                  options={BUDGET_OPTIONS}
                  ariaLabel="Budget range"
                />
              </div>
              <div>
                <label className={dashboardFieldLabelCn}>Timeline</label>
                <AnimatedSelect
                  value={timeline}
                  onChange={setTimeline}
                  options={TIMELINE_OPTIONS}
                  ariaLabel="Timeline"
                />
              </div>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={!isValid || loading}
                className={`${dashboardPrimaryBtnCn} px-5 py-2.5`}
              >
                <Send className="h-4 w-4" />
                {loading ? "Submitting…" : "Submit request"}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
