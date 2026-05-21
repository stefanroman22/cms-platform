"use client";

import { useCallback, useState } from "react";
import type { Lead } from "../types";

export interface LeadUpdatePayload {
  // pipeline
  lead_status?: string;
  website_build_status?: string;
  ai_workflow_status?: string;
  lead_contact_type?: string;
  payment_status?: string;
  notes?: string | null;
  closed_amount?: number | null;
  // location
  address?: string | null;
  city?: string | null;
  country?: string | null;
  postal_code?: string | null;
  lat?: number | null;
  lng?: number | null;
  // contact
  phone?: string | null;
  email?: string | null;
  website_url?: string | null;
  facebook_url?: string | null;
  instagram_url?: string | null;
  menu_url?: string | null;
  // design prompt
  design_prompt?: string | null;
  // opening hours — full replacement of the day -> string map
  opening_hours?: Record<string, string> | null;
  // about — virtual field; backend merges into extra.attributes
  about_attributes?: Record<string, Record<string, boolean>> | null;
}

export interface UseLeadPatchResult {
  patch: (body: LeadUpdatePayload) => Promise<Lead>;
  saving: boolean;
  error: string | null;
  clearError: () => void;
}

export function useLeadPatch(leadId: string, onPatched: (lead: Lead) => void): UseLeadPatchResult {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const patch = useCallback(
    async (body: LeadUpdatePayload): Promise<Lead> => {
      setSaving(true);
      setError(null);
      try {
        const res = await fetch(`/api/admin/leads/${leadId}`, {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const detail = (await res.json().catch(() => ({}))) as { detail?: string };
          throw new Error(detail.detail ?? `Update failed (${res.status})`);
        }
        const updated = (await res.json()) as Lead;
        onPatched(updated);
        return updated;
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Update failed";
        setError(msg);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [leadId, onPatched]
  );

  return { patch, saving, error, clearError: () => setError(null) };
}
