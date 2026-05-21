"use client";

import { useEffect, useState } from "react";
import { Facebook, Globe, Instagram, Mail, Menu, Phone } from "lucide-react";
import type { Lead } from "../types";
import { EditableSectionShell } from "./EditableSectionShell";
import { useLeadPatch, type LeadUpdatePayload } from "../hooks/useLeadPatch";

interface Props {
  lead: Lead;
  onPatched: (lead: Lead) => void;
}

const EMAIL_RE = /^\S+@\S+\.\S+$/;

function normalizeUrl(v: string): string {
  const t = v.trim();
  if (t === "") return "";
  if (/^https?:\/\//i.test(t)) return t;
  return `https://${t}`;
}

export function ContactSection({ lead, onPatched }: Props) {
  const { patch, saving, error, clearError } = useLeadPatch(lead.id, onPatched);

  const [phone, setPhone] = useState(lead.phone ?? "");
  const [email, setEmail] = useState(lead.email ?? "");
  const [website, setWebsite] = useState(lead.website_url ?? "");
  const [facebook, setFacebook] = useState(lead.facebook_url ?? "");
  const [instagram, setInstagram] = useState(lead.instagram_url ?? "");
  const [menu, setMenu] = useState(lead.menu_url ?? "");

  useEffect(() => {
    setPhone(lead.phone ?? "");
    setEmail(lead.email ?? "");
    setWebsite(lead.website_url ?? "");
    setFacebook(lead.facebook_url ?? "");
    setInstagram(lead.instagram_url ?? "");
    setMenu(lead.menu_url ?? "");
    clearError();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    lead.id,
    lead.phone,
    lead.email,
    lead.website_url,
    lead.facebook_url,
    lead.instagram_url,
    lead.menu_url,
  ]);

  const emailError =
    email.trim() === "" || EMAIL_RE.test(email.trim())
      ? null
      : "Enter a valid email or leave empty.";
  const urlError = [website, facebook, instagram, menu].some((u) => /\s/.test(u.trim()))
    ? "URLs cannot contain spaces."
    : null;

  function buildDiff(): LeadUpdatePayload {
    const out: LeadUpdatePayload = {};
    const norm = (v: string) => (v.trim() === "" ? null : v.trim());
    const normU = (v: string) => (v.trim() === "" ? null : normalizeUrl(v));
    if (norm(phone) !== (lead.phone ?? null)) out.phone = norm(phone);
    if (norm(email) !== (lead.email ?? null)) out.email = norm(email);
    if (normU(website) !== (lead.website_url ?? null)) out.website_url = normU(website);
    if (normU(facebook) !== (lead.facebook_url ?? null)) out.facebook_url = normU(facebook);
    if (normU(instagram) !== (lead.instagram_url ?? null)) out.instagram_url = normU(instagram);
    if (normU(menu) !== (lead.menu_url ?? null)) out.menu_url = normU(menu);
    return out;
  }

  async function handleSave() {
    const diff = buildDiff();
    if (Object.keys(diff).length === 0) return;
    await patch(diff);
  }

  function handleCancel() {
    setPhone(lead.phone ?? "");
    setEmail(lead.email ?? "");
    setWebsite(lead.website_url ?? "");
    setFacebook(lead.facebook_url ?? "");
    setInstagram(lead.instagram_url ?? "");
    setMenu(lead.menu_url ?? "");
    clearError();
  }

  function handleUrlBlur(setter: (s: string) => void, value: string) {
    if (value.trim() === "") return;
    setter(normalizeUrl(value));
  }

  const readView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-1.5">
      <Row label="Phone" value={lead.phone} />
      <Row label="Email" value={lead.email} />
      <Row label="Website" value={lead.website_url} isLink />
      <Row label="Facebook" value={lead.facebook_url} isLink />
      <Row label="Instagram" value={lead.instagram_url} isLink />
      <Row label="Menu" value={lead.menu_url} isLink />
    </div>
  );

  const editView = (
    <div className="rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-900 p-3 space-y-2">
      <IconInput
        icon={<Phone className="h-3.5 w-3.5" />}
        label="Phone"
        value={phone}
        onChange={setPhone}
      />
      <IconInput
        icon={<Mail className="h-3.5 w-3.5" />}
        label="Email"
        value={email}
        onChange={setEmail}
        error={emailError}
      />
      <IconInput
        icon={<Globe className="h-3.5 w-3.5" />}
        label="Website URL"
        value={website}
        onChange={setWebsite}
        onBlur={() => handleUrlBlur(setWebsite, website)}
      />
      <IconInput
        icon={<Facebook className="h-3.5 w-3.5" />}
        label="Facebook URL"
        value={facebook}
        onChange={setFacebook}
        onBlur={() => handleUrlBlur(setFacebook, facebook)}
      />
      <IconInput
        icon={<Instagram className="h-3.5 w-3.5" />}
        label="Instagram URL"
        value={instagram}
        onChange={setInstagram}
        onBlur={() => handleUrlBlur(setInstagram, instagram)}
      />
      <IconInput
        icon={<Menu className="h-3.5 w-3.5" />}
        label="Menu URL"
        value={menu}
        onChange={setMenu}
        onBlur={() => handleUrlBlur(setMenu, menu)}
      />
      {urlError && <p className="text-xs text-red-600 dark:text-red-400">{urlError}</p>}
    </div>
  );

  return (
    <EditableSectionShell
      id="contact"
      title="Contact"
      readView={readView}
      editView={editView}
      onSave={handleSave}
      onCancel={handleCancel}
      saving={saving}
      error={error}
      canSave={emailError === null && urlError === null}
    />
  );
}

function IconInput({
  icon,
  label,
  value,
  onChange,
  onBlur,
  error,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  onChange: (s: string) => void;
  onBlur?: () => void;
  error?: string | null;
}) {
  return (
    <div>
      <div className="flex items-center gap-2">
        <span className="text-zinc-500 dark:text-zinc-400 shrink-0">{icon}</span>
        <input
          type="text"
          aria-label={label}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          placeholder={label}
          className="flex-1 rounded-md border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2.5 py-1.5 text-sm text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-zinc-400 dark:focus:ring-zinc-600"
        />
      </div>
      {error && <p className="mt-1 ml-6 text-xs text-red-600 dark:text-red-400">{error}</p>}
    </div>
  );
}

function Row({
  label,
  value,
  isLink,
}: {
  label: string;
  value: string | null | undefined;
  isLink?: boolean;
}) {
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
