// Single source for enum → display label / badge color mappings.
// Update when migrations add new enum values.

export const LEAD_TYPE_LABEL = {
  website: "Website",
  automation: "AI Workflow",
  both: "Website + AI Workflow",
} as const;

// Product badge palette — gold accent reserved for the "both" (full) product.
export const LEAD_TYPE_BADGE_CN = {
  website: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  automation: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  both: "bg-accent/15 text-accent dark:bg-accent/15 dark:text-accent",
} as const;

export const WEB_PRESENCE_LABEL = {
  none: "No website",
  social_only: "Social only",
  has_website: "Has website",
  unknown: "Unknown",
} as const;

export const WEB_PRESENCE_BADGE_CN = {
  none: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  social_only: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  has_website: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
  unknown: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
} as const;

export const LEAD_STATUS_LABEL = {
  not_sent: "Not sent",
  sent: "Sent",
  accepted: "Accepted",
  refused: "Refused",
} as const;

export const LEAD_STATUS_BADGE_CN = {
  not_sent: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
  sent: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  accepted: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  refused: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
} as const;

export const PAYMENT_STATUS_LABEL = {
  not_applicable: "—",
  not_paid: "Unpaid",
  paid: "Paid",
} as const;

export const PAYMENT_STATUS_BADGE_CN = {
  not_applicable: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400",
  not_paid: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  paid: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
} as const;

export const WEBSITE_BUILD_STATUS_LABEL = {
  not_started: "Not started",
  building_design: "Designing",
  design_done: "Design done",
  building: "Building",
  finished_cms: "Finished (CMS)",
  refining: "Refining",
  not_applicable: "—",
} as const;

export const AI_WORKFLOW_STATUS_LABEL = {
  not_started: "Not started",
  building: "Building",
  finished: "Finished",
  refining: "Refining",
  not_applicable: "—",
} as const;

export const LEAD_CONTACT_TYPE_LABEL = {
  not_contacted: "Not contacted",
  phone: "Phone",
  mail: "Mail",
  in_person: "In person",
} as const;

export const SCRAPE_JOB_STATUS_BADGE_CN = {
  pending: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
  running: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  done: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  failed: "bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300",
  cancelled: "bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-500",
} as const;

export const SCRAPE_JOB_STATUS_LABEL = {
  pending: "Pending",
  running: "Running",
  done: "Done",
  failed: "Failed",
  cancelled: "Cancelled",
} as const;

// Type aliases derived from the labels — keep in sync with backend Pydantic Literal types.
export type LeadType = keyof typeof LEAD_TYPE_LABEL;
export type WebPresence = keyof typeof WEB_PRESENCE_LABEL;
export type LeadStatus = keyof typeof LEAD_STATUS_LABEL;
export type PaymentStatus = keyof typeof PAYMENT_STATUS_LABEL;
export type WebsiteBuildStatus = keyof typeof WEBSITE_BUILD_STATUS_LABEL;
export type AiWorkflowStatus = keyof typeof AI_WORKFLOW_STATUS_LABEL;
export type LeadContactType = keyof typeof LEAD_CONTACT_TYPE_LABEL;
export type ScrapeJobStatus = keyof typeof SCRAPE_JOB_STATUS_BADGE_CN;
