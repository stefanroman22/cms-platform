"use client";

import { useEffect, useState } from "react";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { useLeadPatch, type LeadUpdatePayload } from "../hooks/useLeadPatch";

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

export function LocationSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);

  const [address, setAddress] = useState(lead.address ?? "");
  const [city, setCity] = useState(lead.city ?? "");
  const [country, setCountry] = useState(lead.country ?? "");
  const [postal, setPostal] = useState(lead.postal_code ?? "");
  const [lat, setLat] = useState(lead.lat != null ? String(lead.lat) : "");
  const [lng, setLng] = useState(lead.lng != null ? String(lead.lng) : "");

  useEffect(() => {
    setAddress(lead.address ?? "");
    setCity(lead.city ?? "");
    setCountry(lead.country ?? "");
    setPostal(lead.postal_code ?? "");
    setLat(lead.lat != null ? String(lead.lat) : "");
    setLng(lead.lng != null ? String(lead.lng) : "");
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lead.id, lead.address, lead.city, lead.country, lead.postal_code, lead.lat, lead.lng]);

  const latNum = lat.trim() === "" ? null : Number(lat);
  const lngNum = lng.trim() === "" ? null : Number(lng);
  const latValid = latNum === null || (!Number.isNaN(latNum) && latNum >= -90 && latNum <= 90);
  const lngValid = lngNum === null || (!Number.isNaN(lngNum) && lngNum >= -180 && lngNum <= 180);
  const bothOrNeither = (latNum === null) === (lngNum === null);
  const latLngError = !bothOrNeither
    ? "Provide both latitude and longitude, or neither."
    : !latValid
      ? "Latitude must be between -90 and 90."
      : !lngValid
        ? "Longitude must be between -180 and 180."
        : null;

  function buildDiff(): LeadUpdatePayload {
    const out: LeadUpdatePayload = {};
    const a = address.trim() === "" ? null : address.trim();
    if (a !== (lead.address ?? null)) out.address = a;
    const c = city.trim() === "" ? null : city.trim();
    if (c !== (lead.city ?? null)) out.city = c;
    const co = country.trim() === "" ? null : country.trim();
    if (co !== (lead.country ?? null)) out.country = co;
    const p = postal.trim() === "" ? null : postal.trim();
    if (p !== (lead.postal_code ?? null)) out.postal_code = p;
    if (latNum !== (lead.lat ?? null)) out.lat = latNum;
    if (lngNum !== (lead.lng ?? null)) out.lng = lngNum;
    return out;
  }

  async function handleSave() {
    const diff = buildDiff();
    if (Object.keys(diff).length === 0) return;
    await patch(diff);
  }

  function handleCancel() {
    setAddress(lead.address ?? "");
    setCity(lead.city ?? "");
    setCountry(lead.country ?? "");
    setPostal(lead.postal_code ?? "");
    setLat(lead.lat != null ? String(lead.lat) : "");
    setLng(lead.lng != null ? String(lead.lng) : "");
    clearError();
  }

  const readView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-1.5">
      <Row label="Address" value={lead.address} />
      <Row label="City" value={lead.city} />
      <Row label="Country" value={lead.country} />
      <Row label="Postal" value={lead.postal_code} />
      <Row
        label="Lat / Lng"
        value={lead.lat != null && lead.lng != null ? `${lead.lat}, ${lead.lng}` : null}
      />
    </div>
  );

  const editView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Address" colSpan={2}>
          <input
            type="text"
            value={address}
            onChange={(e) => setAddress(e.target.value)}
            className={inputCls}
            aria-label="Address"
          />
        </Field>
        <Field label="City">
          <input
            type="text"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            className={inputCls}
            aria-label="City"
          />
        </Field>
        <Field label="Country">
          <input
            type="text"
            value={country}
            onChange={(e) => setCountry(e.target.value)}
            className={inputCls}
            aria-label="Country"
          />
        </Field>
        <Field label="Postal code">
          <input
            type="text"
            value={postal}
            onChange={(e) => setPostal(e.target.value)}
            className={inputCls}
            aria-label="Postal code"
          />
        </Field>
        <div />
        <Field label="Latitude">
          <input
            type="text"
            inputMode="decimal"
            value={lat}
            onChange={(e) => setLat(e.target.value)}
            className={inputCls}
            aria-label="Latitude"
          />
        </Field>
        <Field label="Longitude">
          <input
            type="text"
            inputMode="decimal"
            value={lng}
            onChange={(e) => setLng(e.target.value)}
            className={inputCls}
            aria-label="Longitude"
          />
        </Field>
      </div>
      {latLngError && <p className="mt-2 text-xs text-red-600 dark:text-red-400">{latLngError}</p>}
    </div>
  );

  return (
    <EditableSectionShell
      id="location"
      title="Location"
      readView={readView}
      editView={editView}
      onSave={handleSave}
      onCancel={handleCancel}
      saving={saving}
      error={error}
      canSave={latLngError === null}
    />
  );
}

const inputCls =
  "w-full rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600";

function Field({
  label,
  colSpan,
  children,
}: {
  label: string;
  colSpan?: 1 | 2;
  children: React.ReactNode;
}) {
  return (
    <div className={colSpan === 2 ? "col-span-2" : undefined}>
      <label className="block text-xs font-medium text-zinc-500 dark:text-zinc-400 mb-1">
        {label}
      </label>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex items-baseline gap-3 text-xs">
      <span className="text-zinc-500 dark:text-zinc-400 w-24 shrink-0">{label}</span>
      {value == null || value === "" ? (
        <span className="text-zinc-400 dark:text-zinc-600">—</span>
      ) : (
        <span className="text-zinc-900 dark:text-zinc-100 break-words">{value}</span>
      )}
    </div>
  );
}
