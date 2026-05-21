"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ExternalLink, Save, X } from "lucide-react";
import {
  AI_WORKFLOW_STATUS_LABEL,
  LEAD_CONTACT_TYPE_LABEL,
  LEAD_STATUS_LABEL,
  PAYMENT_STATUS_LABEL,
  WEBSITE_BUILD_STATUS_LABEL,
  type AiWorkflowStatus,
  type LeadContactType,
  type LeadStatus,
  type PaymentStatus,
  type WebsiteBuildStatus,
} from "@/lib/leadEnums";
import type { Lead } from "./types";
import { ReviewsList } from "./ReviewsList";
import { AnimatedSelect } from "@/components/dashboard/AnimatedSelect";
import { EditingSectionProvider } from "./context/EditingSectionContext";
import { LocationSection } from "./sections/LocationSection";
import { ContactSection } from "./sections/ContactSection";
import { DesignPromptSection } from "./sections/DesignPromptSection";
import { OpeningHoursSection } from "./sections/OpeningHoursSection";
import { AboutSection } from "./sections/AboutSection";

interface Props {
  lead: Lead | null;
  onClose: () => void;
  onPatched: (updated: Lead) => void;
}

const DRAWER_VARIANTS = {
  hidden: { x: "100%" },
  visible: { x: 0 },
};

const BACKDROP_VARIANTS = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
};

export function LeadDetailDrawer({ lead, onClose, onPatched }: Props) {
  return (
    <AnimatePresence>
      {lead && (
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
            className="fixed right-0 top-0 z-50 h-full w-full md:w-[40rem] overflow-y-auto bg-white dark:bg-zinc-950 shadow-2xl"
          >
            <DrawerBody lead={lead} onClose={onClose} onPatched={onPatched} />
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}

function DrawerBody({
  lead,
  onClose,
  onPatched,
}: {
  lead: Lead;
  onClose: () => void;
  onPatched: (updated: Lead) => void;
}) {
  // Local copies for every editable field — manual save only. Closing the
  // drawer (X or backdrop) discards any pending edits; only the Save button
  // persists to the server.
  const [leadStatus, setLeadStatus] = useState<LeadStatus>(lead.lead_status);
  const [websiteBuildStatus, setWebsiteBuildStatus] = useState<WebsiteBuildStatus>(
    lead.website_build_status
  );
  const [aiWorkflowStatus, setAiWorkflowStatus] = useState<AiWorkflowStatus>(
    lead.ai_workflow_status
  );
  const [leadContactType, setLeadContactType] = useState<LeadContactType>(lead.lead_contact_type);
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus>(lead.payment_status);
  const [notes, setNotes] = useState(lead.notes ?? "");
  const [closedAmount, setClosedAmount] = useState<string>(
    lead.closed_amount != null ? String(lead.closed_amount) : ""
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset every editor when the drawer is reused for a different lead.
  useEffect(() => {
    setLeadStatus(lead.lead_status);
    setWebsiteBuildStatus(lead.website_build_status);
    setAiWorkflowStatus(lead.ai_workflow_status);
    setLeadContactType(lead.lead_contact_type);
    setPaymentStatus(lead.payment_status);
    setNotes(lead.notes ?? "");
    setClosedAmount(lead.closed_amount != null ? String(lead.closed_amount) : "");
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id]);

  async function handleSave() {
    const body: Record<string, string | number | null> = {};
    if (leadStatus !== lead.lead_status) body.lead_status = leadStatus;
    if (websiteBuildStatus !== lead.website_build_status)
      body.website_build_status = websiteBuildStatus;
    if (aiWorkflowStatus !== lead.ai_workflow_status) body.ai_workflow_status = aiWorkflowStatus;
    if (leadContactType !== lead.lead_contact_type) body.lead_contact_type = leadContactType;
    if (paymentStatus !== lead.payment_status) body.payment_status = paymentStatus;
    if (notes !== (lead.notes ?? "")) body.notes = notes;

    const serverAmount = lead.closed_amount != null ? String(lead.closed_amount) : "";
    if (closedAmount !== serverAmount) {
      const trimmed = closedAmount.trim();
      if (trimmed === "") body.closed_amount = null;
      else {
        const parsed = Number(trimmed);
        if (Number.isNaN(parsed) || parsed < 0) {
          setError("Deal amount must be a non-negative number.");
          return;
        }
        body.closed_amount = parsed;
      }
    }

    if (Object.keys(body).length === 0) {
      setError(null);
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/leads/${lead.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error(detail.detail ?? `Update failed (${res.status})`);
      }
      const updated: Lead = await res.json();
      onPatched(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
    }
  }

  return (
    <EditingSectionProvider>
      <div className="p-5">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              {lead.category ?? "Lead"}
            </div>
            <h2 className="text-xl font-semibold text-zinc-900 dark:text-zinc-100 truncate">
              {lead.business_name}
            </h2>
            {lead.source_url && (
              <a
                href={lead.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 hover:underline"
              >
                View on Google Maps
                <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => {
                handleSave().catch(() => {});
              }}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-zinc-900 text-white hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200 cursor-pointer transition-colors"
            >
              <Save className="h-3.5 w-3.5" />
              Save
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close lead detail"
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
        {saving && <div className="mt-3 text-xs text-zinc-500 dark:text-zinc-400">Saving…</div>}

        {/* Pipeline status editors */}
        <section className="mt-5 space-y-3">
          <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold">
            Pipeline
          </h3>
          <SelectField<LeadStatus>
            label="Lead status"
            value={leadStatus}
            options={LEAD_STATUS_LABEL}
            onChange={setLeadStatus}
          />
          <SelectField<WebsiteBuildStatus>
            label="Website build"
            value={websiteBuildStatus}
            options={WEBSITE_BUILD_STATUS_LABEL}
            onChange={setWebsiteBuildStatus}
          />
          <SelectField<AiWorkflowStatus>
            label="AI workflow"
            value={aiWorkflowStatus}
            options={AI_WORKFLOW_STATUS_LABEL}
            onChange={setAiWorkflowStatus}
          />
          <SelectField<LeadContactType>
            label="Contact type"
            value={leadContactType}
            options={LEAD_CONTACT_TYPE_LABEL}
            onChange={setLeadContactType}
          />
          <SelectField<PaymentStatus>
            label="Payment"
            value={paymentStatus}
            options={PAYMENT_STATUS_LABEL}
            onChange={setPaymentStatus}
          />
          <div>
            <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1">
              Notes
            </label>
            <textarea
              rows={3}
              className="w-full rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600 resize-none"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
          </div>
        </section>

        {/* Gate on local state so the field appears immediately when the user
          switches to Accepted, even before they click Save. */}
        {leadStatus === "accepted" && (
          <section className="mt-5">
            <h3 className="text-xs uppercase tracking-wider text-emerald-600 dark:text-emerald-400 font-semibold mb-2">
              Closed deal
            </h3>
            <div className="rounded-lg border border-emerald-200 dark:border-emerald-900 bg-emerald-50 dark:bg-emerald-950/30 p-3 space-y-2">
              <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300">
                Deal amount (EUR)
              </label>
              <div className="flex items-center gap-2">
                <span className="text-zinc-500 dark:text-zinc-400">€</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-emerald-400"
                  value={closedAmount}
                  placeholder="0.00"
                  onChange={(e) => setClosedAmount(e.target.value)}
                />
              </div>
              {lead.closed_at && (
                <div className="text-xs text-zinc-500 dark:text-zinc-400">
                  First closed on {new Date(lead.closed_at).toLocaleDateString()}
                </div>
              )}
            </div>
          </section>
        )}

        <LocationSection lead={lead} onPatched={onPatched} />

        <ContactSection lead={lead} onPatched={onPatched} />

        {/* AI scoring */}
        <DetailCard title="AI scoring">
          {lead.ai_score == null ? (
            <p className="text-xs text-zinc-500 dark:text-zinc-400 italic">Not scored yet.</p>
          ) : (
            <>
              <Row label="Score" value={`${lead.ai_score} / 100`} />
              <Row label="Scored at" value={lead.ai_scored_at} />
            </>
          )}
        </DetailCard>

        <DesignPromptSection lead={lead} onPatched={onPatched} />

        <OpeningHoursSection lead={lead} onPatched={onPatched} />
        <ReviewsList
          reviews={
            (lead.reviews ?? null) as
              | {
                  author: string | null;
                  text: string | null;
                  relative_date: string | null;
                  rating: number | null;
                }[]
              | null
          }
        />
        <AboutSection lead={lead} onPatched={onPatched} />
        {/* Keep raw extra JSON as a debug aid */}
        <CollapsibleJson title="Raw extra (debug)" data={lead.extra} />
      </div>
    </EditingSectionProvider>
  );
}

function SelectField<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: Record<T, string>;
  onChange: (v: T) => void;
}) {
  return (
    <div>
      <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1">
        {label}
      </label>
      <AnimatedSelect
        value={value}
        onChange={(v) => onChange(v as T)}
        ariaLabel={label}
        initialChevron="up"
        options={(Object.keys(options) as T[]).map((k) => ({ value: k, label: options[k] }))}
      />
    </div>
  );
}

function DetailCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-5">
      <h3 className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold mb-2">
        {title}
      </h3>
      <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-1.5">
        {children}
      </div>
    </section>
  );
}

function Row({ label, value, isLink }: { label: string; value: string | null; isLink?: boolean }) {
  return (
    <div className="flex items-baseline gap-3 text-xs">
      <span className="text-zinc-500 dark:text-zinc-400 w-24 shrink-0">{label}</span>
      {value == null || value === "" ? (
        <span className="text-zinc-400 dark:text-zinc-600">—</span>
      ) : isLink ? (
        <a
          href={value}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 dark:text-blue-400 hover:underline truncate"
        >
          {value}
        </a>
      ) : (
        <span className="text-zinc-900 dark:text-zinc-100 break-words">{value}</span>
      )}
    </div>
  );
}

function CollapsibleJson({ title, data }: { title: string; data: unknown }) {
  const [open, setOpen] = useState(false);
  const empty =
    data == null ||
    (Array.isArray(data) && data.length === 0) ||
    (typeof data === "object" && !Array.isArray(data) && Object.keys(data as object).length === 0);
  return (
    <section className="mt-5">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full text-left text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 font-semibold hover:text-zinc-700 dark:hover:text-zinc-300 cursor-pointer"
      >
        {open ? "▾" : "▸"} {title} {empty && "(empty)"}
      </button>
      <AnimatePresence initial={false}>
        {open && !empty && (
          <motion.pre
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="mt-2 overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 text-xs text-zinc-700 dark:text-zinc-300 font-mono whitespace-pre-wrap"
          >
            {JSON.stringify(data, null, 2)}
          </motion.pre>
        )}
      </AnimatePresence>
    </section>
  );
}
