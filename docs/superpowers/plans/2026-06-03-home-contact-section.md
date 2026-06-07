# Home-page Contact Section — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a contact section (Calendly calendar + real-sending contact form with a reusable gold spinner→checkmark animation) to the marketing home page, before the pricing section.

**Architecture:** A new backend `POST /forms/contact` endpoint sends the form via the existing Resend setup to `stefanromanpers@gmail.com`. The frontend reaches it through the existing same-origin `/api/*` proxy. A reusable `SubmitFeedback` component drives the loading→success animation; the existing `ContactForm` (used on the Contact page) is upgraded to async-send and reused on the home page alongside a new reusable `CalendlyCalendar`. A global CSS rule enforces `cursor: pointer` on buttons.

**Tech Stack:** Next.js 16 (App Router), TypeScript, Tailwind v4, `motion/react`, `react-calendly`, FastAPI, Resend, pytest.

**Conventions:**
- Use `motion/react` imports — never `framer-motion`.
- Per project preference, **do not auto-commit per task**. Implement all tasks, then commit once when Stefan says so (see "Commit" at the end). The per-task work is still split into bite-sized steps for review.
- No `npm run build` after every change; build once at the verification milestone.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/auth_service/routers/forms.py` | Modify | Add `ContactRequest` model + `POST /contact` endpoint (Resend send to Stefan). |
| `backend/auth_service/tests/test_contact_form.py` | Create | Unit tests for the new endpoint (mocked Resend). |
| `frontend/package.json` | Modify | Add `react-calendly` dependency. |
| `frontend/src/app/globals.css` | Modify | Global `cursor: pointer` base rule. |
| `frontend/src/components/ui/SubmitFeedback.tsx` | Create | Reusable spinner→checkmark confirmation animation. |
| `frontend/src/components/contact/ContactForm.tsx` | Modify | Async real send + route states through `SubmitFeedback`. |
| `frontend/src/components/contact/CalendlyCalendar.tsx` | Create | Reusable themed Calendly inline widget. |
| `frontend/src/components/contact/ContactSection.tsx` | Create | Home-page section composing calendar + form with scroll-in reveals. |
| `frontend/src/app/(marketing)/page.tsx` | Modify | Mount `<ContactSection />` before `<PricingSection />`. |
| memory `feedback_cursor_pointer_buttons.md` | Create | Standing rule: buttons get `cursor: pointer`. |

---

## Task 1: Backend — `POST /forms/contact` endpoint (TDD)

**Files:**
- Modify: `backend/auth_service/routers/forms.py`
- Test: `backend/auth_service/tests/test_contact_form.py`

- [ ] **Step 1: Write the failing test**

Create `backend/auth_service/tests/test_contact_form.py`:

```python
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
from auth_service.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_contact_happy_path(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test_key")
    with patch("resend.Emails.send") as mock_send:
        mock_send.return_value = {"id": "resend_x"}
        r = client.post(
            "/forms/contact",
            json={
                "name": "Jane Doe",
                "email": "jane@acme.com",
                "company": "Acme",
                "message": "I would like a website please.",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True
        mock_send.assert_called_once()
        params = mock_send.call_args.args[0]
        assert params["to"] == ["stefanromanpers@gmail.com"]
        assert params["reply_to"] == "jane@acme.com"


def test_contact_honeypot_silently_accepted(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test_key")
    with patch("resend.Emails.send") as mock_send:
        r = client.post(
            "/forms/contact",
            json={
                "name": "Bot",
                "email": "bot@spam.com",
                "message": "spam spam spam",
                "website": "http://spam.com",
            },
        )
        assert r.status_code == 200
        assert r.json()["success"] is True
        mock_send.assert_not_called()


def test_contact_422_on_empty_body(client):
    r = client.post("/forms/contact", json={})
    assert r.status_code == 422


def test_contact_422_on_bad_email(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test_key")
    r = client.post(
        "/forms/contact",
        json={"name": "Jane", "email": "not-an-email", "message": "hello there friend"},
    )
    assert r.status_code == 422


def test_contact_502_on_resend_failure(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test_key")
    with patch("resend.Emails.send", side_effect=RuntimeError("Resend down")):
        r = client.post(
            "/forms/contact",
            json={"name": "Jane", "email": "jane@acme.com", "message": "hello there friend"},
        )
        assert r.status_code == 502
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`, venv active):
```bash
python -m pytest auth_service/tests/test_contact_form.py -v
```
Expected: FAIL — `404 Not Found` for `/forms/contact` (endpoint doesn't exist yet).

- [ ] **Step 3: Add imports to `forms.py`**

At the top of `backend/auth_service/routers/forms.py`, add `re` and `pydantic.BaseModel` alongside the existing imports:

```python
import re
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..core.config import settings
from ..core.limiter import client_ip, limiter
from ..services.supabase_client import get_supabase_admin
```

- [ ] **Step 4: Add the model + endpoint**

Append to `backend/auth_service/routers/forms.py` (after the existing `submit_form` function):

```python
# ── First-party marketing-site contact form ──────────────────────────────────
# Distinct from the multi-tenant /{project_slug}/{form_key} endpoint above: this
# is Roman Technologies' own contact form. It is reached through the frontend's
# same-origin /api proxy (which does not forward Origin), so abuse protection is
# rate-limit + honeypot + payload validation rather than origin allow-listing.

MARKETING_CONTACT_RECIPIENT = "stefanromanpers@gmail.com"
_CONTACT_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ContactRequest(BaseModel):
    name: str
    email: str
    message: str
    company: str = ""
    website: str = ""  # honeypot — real users never fill this


@router.post("/contact")
@limiter.limit("5/10minutes")
async def submit_contact(request: Request, body: ContactRequest) -> JSONResponse:
    # Honeypot — silently accept bots so they don't learn they were filtered.
    if body.website.strip():
        return JSONResponse(content={"success": True})

    name = body.name.strip()
    email = body.email.strip()
    message = body.message.strip()
    company = body.company.strip()

    if not name or not message or not _CONTACT_EMAIL_RE.match(email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid contact submission",
        )

    fields = {
        "Name": name,
        "Email": email,
        **({"Company": company} if company else {}),
        "Message": message,
    }

    # TEST-002 — skip the Resend hop on E2E bodies in preview.
    from ..services.e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(name, email, company, message):
        short_circuit_response("forms:contact")
        return JSONResponse(content={"success": True, "e2e_short_circuit": True})

    if not settings.RESEND_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured (RESEND_API_KEY missing)",
        )

    import resend  # local import so a missing key never breaks startup

    resend.api_key = settings.RESEND_API_KEY
    submitted_at = datetime.now(UTC).strftime("%d %b %Y at %H:%M UTC")
    html = _build_email_html("Roman Technologies", "contact", fields, submitted_at)

    params: resend.Emails.SendParams = {
        "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": [MARKETING_CONTACT_RECIPIENT],
        "subject": f"New enquiry from {name} — roman-technologies.dev",
        "html": html,
        "reply_to": email,
    }

    try:
        resend.Emails.send(params)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email delivery failed: {exc}",
        ) from exc

    return JSONResponse(content={"success": True})
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
python -m pytest auth_service/tests/test_contact_form.py -v
```
Expected: 5 passed.

---

## Task 2: Add `react-calendly` dependency

**Files:**
- Modify: `frontend/package.json` (+ lockfile)

- [ ] **Step 1: Install**

Run (from `frontend/`):
```bash
npm install react-calendly
```
Expected: `react-calendly` added to `dependencies`, lockfile updated, no errors.

- [ ] **Step 2: Verify it resolves**

Run:
```bash
node -e "require.resolve('react-calendly'); console.log('ok')"
```
Expected: `ok`.

---

## Task 3: Global `cursor: pointer` rule

**Files:**
- Modify: `frontend/src/app/globals.css`

- [ ] **Step 1: Add the base layer rule**

In `frontend/src/app/globals.css`, immediately after the `body { … }` block, add:

```css
/* Buttons are interactive — always show the pointer cursor (Tailwind v4
   preflight resets <button> to cursor:default). Project rule: every button
   and role=button gets a pointer unless disabled. */
@layer base {
  button:not(:disabled),
  [role="button"]:not([aria-disabled="true"]) {
    cursor: pointer;
  }
}
```

- [ ] **Step 2: Sanity-check the CSS parses**

Run (from `frontend/`):
```bash
npx --yes prettier --check src/app/globals.css || true
```
Expected: no parse error reported (formatting warnings are fine).

---

## Task 4: `SubmitFeedback` — reusable confirmation animation

**Files:**
- Create: `frontend/src/components/ui/SubmitFeedback.tsx`

> Note: this component renders `motion/react` `m.*` elements and must be used inside an ancestor `<LazyMotion>` (both consumers — the two `ContactForm` instances — already provide one).

- [ ] **Step 1: Create the component**

Create `frontend/src/components/ui/SubmitFeedback.tsx`:

```tsx
"use client";

import type { ReactNode } from "react";
import { AnimatePresence, m } from "motion/react";
import { cn } from "@/lib/utils";

const EXPO = [0.16, 1, 0.3, 1] as const;

export type SubmitStatus = "loading" | "success" | "error";

/** Gold comet spinner that morphs into a checkmark (or an X on error). Pure visual. */
function SpinnerCheck({ status, size = 56 }: { status: SubmitStatus; size?: number }) {
  return (
    <div className="relative" style={{ width: size, height: size }}>
      {/* Dim static track ring — constant backdrop behind both states. */}
      <svg
        viewBox="0 0 56 56"
        width={size}
        height={size}
        className="absolute inset-0"
        aria-hidden="true"
      >
        <circle
          cx="28"
          cy="28"
          r="25"
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.12}
          strokeWidth={3}
          className="text-text-secondary"
        />
      </svg>

      <AnimatePresence mode="wait" initial={false}>
        {status === "loading" ? (
          <m.svg
            key="spinner"
            viewBox="0 0 56 56"
            width={size}
            height={size}
            className="absolute inset-0 animate-spin text-accent"
            style={{ animationDuration: "1.1s" }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25, ease: EXPO }}
            aria-hidden="true"
          >
            <circle
              cx="28"
              cy="28"
              r="25"
              fill="none"
              stroke="currentColor"
              strokeOpacity={0.92}
              strokeWidth={3}
              strokeLinecap="round"
              strokeDasharray="47 110"
            />
          </m.svg>
        ) : (
          <m.svg
            key="done"
            viewBox="0 0 56 56"
            width={size}
            height={size}
            className={cn("absolute inset-0", status === "error" ? "text-red-400" : "text-accent")}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.3, ease: EXPO }}
            aria-hidden="true"
          >
            {/* Arc settles into a full ring. */}
            <m.circle
              cx="28"
              cy="28"
              r="25"
              fill="none"
              stroke="currentColor"
              strokeOpacity={0.92}
              strokeWidth={3}
              strokeLinecap="round"
              initial={{ pathLength: 0.3 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.5, ease: EXPO }}
            />
            {status === "success" ? (
              <m.path
                d="M16.5 29 L24.5 37 L40 20"
                fill="none"
                stroke="currentColor"
                strokeWidth={3.2}
                strokeLinecap="round"
                strokeLinejoin="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.4, ease: EXPO, delay: 0.35 }}
              />
            ) : (
              <m.path
                d="M20 20 L36 36 M36 20 L20 36"
                fill="none"
                stroke="currentColor"
                strokeWidth={3.2}
                strokeLinecap="round"
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.4, ease: EXPO, delay: 0.25 }}
              />
            )}
          </m.svg>
        )}
      </AnimatePresence>
    </div>
  );
}

export interface SubmitFeedbackProps {
  status: SubmitStatus;
  loadingText?: string;
  successText?: string;
  errorText?: ReactNode;
  className?: string;
}

/**
 * Reusable submit confirmation: a gold spinner fades in with a line of text
 * below it; on success the spinner morphs into a checkmark and the text
 * smoothly recolours + changes content. Drive it with the `status` prop —
 * the parent owns the async work.
 */
export function SubmitFeedback({
  status,
  loadingText = "Sending your message…",
  successText = "Message sent — talk soon!",
  errorText = "Something went wrong. Please try again.",
  className,
}: SubmitFeedbackProps) {
  const text: ReactNode =
    status === "loading" ? loadingText : status === "success" ? successText : errorText;
  const tone =
    status === "success"
      ? "text-accent"
      : status === "error"
        ? "text-red-400"
        : "text-text-secondary";

  return (
    <m.div
      role="status"
      aria-live="polite"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EXPO }}
      className={cn("flex flex-col items-center py-10 text-center", className)}
    >
      <SpinnerCheck status={status} />
      <div className="mt-5 min-h-[1.5rem]">
        <AnimatePresence mode="wait" initial={false}>
          <m.p
            key={status}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.35, ease: EXPO }}
            className={cn("text-sm font-medium leading-relaxed transition-colors", tone)}
          >
            {text}
          </m.p>
        </AnimatePresence>
      </div>
    </m.div>
  );
}
```

- [ ] **Step 2: Typecheck the new file**

Run (from `frontend/`):
```bash
npx tsc --noEmit
```
Expected: no errors referencing `SubmitFeedback.tsx`. (Pre-existing unrelated errors, if any, are out of scope.)

---

## Task 5: Upgrade `ContactForm` — async send + `SubmitFeedback`

**Files:**
- Modify: `frontend/src/components/contact/ContactForm.tsx`

- [ ] **Step 1: Replace the file with the async-send version**

Replace the entire contents of `frontend/src/components/contact/ContactForm.tsx` with:

```tsx
"use client";

import { useState } from "react";
import { LazyMotion, domAnimation, MotionConfig, AnimatePresence, m } from "motion/react";
import { Send } from "lucide-react";
import { HeroButton } from "@/components/ui/HeroButton";
import { SubmitFeedback } from "@/components/ui/SubmitFeedback";
import { cn } from "@/lib/utils";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const EXPO = [0.16, 1, 0.3, 1] as const;
/** Keep the spinner visible long enough to read on a fast send. */
const MIN_SPINNER_MS = 700;

const fieldBase =
  "w-full rounded-[10px] border bg-surface/40 px-4 py-3 text-sm text-text-primary outline-none transition-colors placeholder:text-text-tertiary focus:bg-surface";
const fieldOk = "border-border focus:border-accent/60";
const fieldErr = "border-red-500/70 focus:border-red-500";

type Field = "name" | "email" | "company" | "message";
type Phase = "idle" | "sending" | "sent" | "error";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function ContactForm({ recipient }: { recipient: string }) {
  const [values, setValues] = useState<Record<Field, string>>({
    name: "",
    email: "",
    company: "",
    message: "",
  });
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [phase, setPhase] = useState<Phase>("idle");

  const update = (key: Field) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setValues((v) => ({ ...v, [key]: e.target.value }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: undefined }));
  };

  function validate(): Partial<Record<Field, string>> {
    const e: Partial<Record<Field, string>> = {};
    if (!values.name.trim()) e.name = "Please add your name.";
    if (!values.email.trim()) e.email = "Please add your email.";
    else if (!EMAIL_RE.test(values.email.trim())) e.email = "That email does not look right.";
    if (values.message.trim().length < 10)
      e.message = "Tell us a little more (at least 10 characters).";
    return e;
  }

  async function handleSubmit(ev: React.FormEvent) {
    ev.preventDefault();
    const next = validate();
    setErrors(next);
    if (Object.keys(next).length > 0) {
      const first = (["name", "email", "message"] as Field[]).find((k) => next[k]);
      if (first) document.getElementById(`contact-${first}`)?.focus();
      return;
    }

    setPhase("sending");
    try {
      const [res] = await Promise.all([
        fetch("/api/forms/contact", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: values.name.trim(),
            email: values.email.trim(),
            company: values.company.trim(),
            message: values.message.trim(),
          }),
        }),
        sleep(MIN_SPINNER_MS),
      ]);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { success?: boolean };
      if (!data?.success) throw new Error("send failed");
      setPhase("sent");
    } catch {
      setPhase("error");
    }
  }

  function reset(clearValues: boolean) {
    if (clearValues) setValues({ name: "", email: "", company: "", message: "" });
    setErrors({});
    setPhase("idle");
  }

  const showFeedback = phase !== "idle";

  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <div className="rounded-2xl border border-border bg-surface/30 p-6 backdrop-blur-sm sm:p-8">
          <AnimatePresence mode="wait" initial={false}>
            {showFeedback ? (
              <m.div
                key="feedback"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3, ease: EXPO }}
              >
                <SubmitFeedback
                  status={phase === "sending" ? "loading" : phase === "sent" ? "success" : "error"}
                  successText="Message sent — talk soon!"
                  errorText={
                    <>
                      Something went wrong. Email me directly at{" "}
                      <a
                        href={`mailto:${recipient}`}
                        className="text-accent underline-offset-2 hover:underline"
                      >
                        {recipient}
                      </a>
                      .
                    </>
                  }
                />
                {phase !== "sending" && (
                  <div className="text-center">
                    <button
                      type="button"
                      onClick={() => reset(phase === "sent")}
                      className="text-sm font-medium text-text-secondary underline-offset-4 outline-none transition-colors hover:text-accent focus-visible:underline"
                    >
                      {phase === "sent" ? "Send another message" : "Try again"}
                    </button>
                  </div>
                )}
              </m.div>
            ) : (
              <m.form
                key="form"
                noValidate
                onSubmit={handleSubmit}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3, ease: EXPO }}
                className="space-y-5"
              >
                <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
                  <div>
                    <label
                      htmlFor="contact-name"
                      className="mb-1.5 block text-sm font-medium text-text-secondary"
                    >
                      Name <span className="text-accent">*</span>
                    </label>
                    <input
                      id="contact-name"
                      name="name"
                      type="text"
                      autoComplete="name"
                      value={values.name}
                      onChange={update("name")}
                      aria-invalid={!!errors.name}
                      aria-describedby={errors.name ? "contact-name-error" : undefined}
                      className={cn(fieldBase, errors.name ? fieldErr : fieldOk)}
                      placeholder="Jane Doe"
                    />
                    {errors.name && (
                      <p id="contact-name-error" role="alert" className="mt-1.5 text-xs text-red-400">
                        {errors.name}
                      </p>
                    )}
                  </div>

                  <div>
                    <label
                      htmlFor="contact-email"
                      className="mb-1.5 block text-sm font-medium text-text-secondary"
                    >
                      Email <span className="text-accent">*</span>
                    </label>
                    <input
                      id="contact-email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      value={values.email}
                      onChange={update("email")}
                      aria-invalid={!!errors.email}
                      aria-describedby={errors.email ? "contact-email-error" : undefined}
                      className={cn(fieldBase, errors.email ? fieldErr : fieldOk)}
                      placeholder="jane@company.com"
                    />
                    {errors.email && (
                      <p
                        id="contact-email-error"
                        role="alert"
                        className="mt-1.5 text-xs text-red-400"
                      >
                        {errors.email}
                      </p>
                    )}
                  </div>
                </div>

                <div>
                  <label
                    htmlFor="contact-company"
                    className="mb-1.5 block text-sm font-medium text-text-secondary"
                  >
                    Company <span className="text-text-tertiary">(optional)</span>
                  </label>
                  <input
                    id="contact-company"
                    name="company"
                    type="text"
                    autoComplete="organization"
                    value={values.company}
                    onChange={update("company")}
                    className={cn(fieldBase, fieldOk)}
                    placeholder="Acme Inc."
                  />
                </div>

                <div>
                  <label
                    htmlFor="contact-message"
                    className="mb-1.5 block text-sm font-medium text-text-secondary"
                  >
                    Message <span className="text-accent">*</span>
                  </label>
                  <textarea
                    id="contact-message"
                    name="message"
                    rows={5}
                    value={values.message}
                    onChange={update("message")}
                    aria-invalid={!!errors.message}
                    aria-describedby={errors.message ? "contact-message-error" : undefined}
                    className={cn(fieldBase, "resize-y", errors.message ? fieldErr : fieldOk)}
                    placeholder="A few lines about your project, timeline and budget."
                  />
                  {errors.message && (
                    <p
                      id="contact-message-error"
                      role="alert"
                      className="mt-1.5 text-xs text-red-400"
                    >
                      {errors.message}
                    </p>
                  )}
                </div>

                <HeroButton type="submit" variant="primary" className="w-full">
                  <Send className="h-4 w-4" aria-hidden={true} />
                  Send message
                </HeroButton>

                <p className="text-center text-xs text-text-tertiary">
                  Or email us directly at{" "}
                  <a
                    href={`mailto:${recipient}`}
                    className="text-text-secondary underline-offset-2 hover:text-accent hover:underline"
                  >
                    {recipient}
                  </a>
                  .
                </p>
              </m.form>
            )}
          </AnimatePresence>
        </div>
      </MotionConfig>
    </LazyMotion>
  );
}
```

Key changes vs. the original: `sent: boolean` → `phase` state machine; `mailto` flow → async `fetch("/api/forms/contact")` with a `MIN_SPINNER_MS` floor; the old static "ready to send" success block → `<SubmitFeedback>`. The `CheckCircle2` import is dropped (no longer used). Field markup is unchanged.

- [ ] **Step 2: Typecheck**

Run (from `frontend/`):
```bash
npx tsc --noEmit
```
Expected: no new errors in `ContactForm.tsx`.

---

## Task 6: `CalendlyCalendar` — reusable themed widget

**Files:**
- Create: `frontend/src/components/contact/CalendlyCalendar.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/contact/CalendlyCalendar.tsx`:

```tsx
"use client";

import { InlineWidget } from "react-calendly";
import { cn } from "@/lib/utils";

const DEFAULT_URL = "https://calendly.com/stefanromanpers/30min";

interface CalendlyCalendarProps {
  /** Calendly scheduling URL. Defaults to Stefan's 30-minute event. */
  url?: string;
  className?: string;
  /** Widget height in px. Default 700. */
  minHeight?: number;
}

/**
 * Reusable Calendly inline calendar, themed to the brass-on-near-black site
 * palette. Drop it anywhere: `<CalendlyCalendar />`.
 */
export function CalendlyCalendar({
  url = DEFAULT_URL,
  className,
  minHeight = 700,
}: CalendlyCalendarProps) {
  return (
    <div
      className={cn(
        "h-full overflow-hidden rounded-2xl border border-border bg-surface/30 backdrop-blur-sm",
        className
      )}
    >
      <InlineWidget
        url={url}
        styles={{ minWidth: "320px", height: `${minHeight}px` }}
        pageSettings={{
          // Calendly hex values omit the leading '#'. Matched to the theme tokens:
          // bg #0a0a0b, text #fafaf7, accent (brass) #c9a961.
          backgroundColor: "0a0a0b",
          textColor: "fafaf7",
          primaryColor: "c9a961",
          hideEventTypeDetails: false,
          hideLandingPageDetails: false,
        }}
      />
    </div>
  );
}
```

> Fallback if hydration warnings appear: wrap the widget with
> `const InlineWidget = dynamic(() => import("react-calendly").then(m => m.InlineWidget), { ssr: false });`
> using `next/dynamic`. Only do this if a hydration error actually surfaces in Task 9.

- [ ] **Step 2: Typecheck**

Run (from `frontend/`):
```bash
npx tsc --noEmit
```
Expected: no errors in `CalendlyCalendar.tsx` (react-calendly ships its own types).

---

## Task 7: `ContactSection` — home-page section

**Files:**
- Create: `frontend/src/components/contact/ContactSection.tsx`

- [ ] **Step 1: Create the section**

Create `frontend/src/components/contact/ContactSection.tsx`:

```tsx
"use client";

import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { Reveal } from "@/components/motion/Reveal";
import { CalendlyCalendar } from "@/components/contact/CalendlyCalendar";
import { ContactForm } from "@/components/contact/ContactForm";
import { contact } from "@/content/contact";

/**
 * Home-page contact section: a Calendly calendar and the shared ContactForm,
 * side by side on desktop and stacked on mobile. Each block fades in on scroll.
 */
export function ContactSection() {
  const recipient = contact.details.email;

  return (
    <section id="contact" className="relative overflow-hidden bg-black px-6 py-16 lg:py-24">
      {/* Subtle gold ambient glow, echoing the hero + pricing sections. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-16 h-[440px] w-[720px] -translate-x-1/2 rounded-full opacity-60 blur-3xl"
        style={{
          background: "radial-gradient(circle, rgba(201,169,97,0.10), rgba(201,169,97,0) 70%)",
        }}
      />

      <LazyMotion features={domAnimation}>
        <MotionConfig reducedMotion="user">
          <div className="relative z-10 mx-auto max-w-5xl">
            <Reveal inView amount={0.4} className="mx-auto max-w-2xl text-center">
              <p className="mb-4 text-[0.78rem] font-semibold uppercase tracking-[0.34em] text-accent">
                Let&apos;s talk
              </p>
              <h2 className="font-display text-[clamp(2rem,5vw,3.25rem)] font-bold leading-[1.05] tracking-[-0.02em] text-text-primary">
                Book a call or send a message
              </h2>
              <p className="mx-auto mt-5 max-w-xl text-[1.0625rem] leading-relaxed text-text-secondary">
                Grab a 30-minute slot with me, Stefan — or leave your details below and I&apos;ll
                reply within one business day.
              </p>
            </Reveal>

            <div className="mt-12 grid grid-cols-1 gap-6 lg:grid-cols-2 lg:gap-8">
              <Reveal inView amount={0.15} direction="up" distance={28}>
                <CalendlyCalendar />
              </Reveal>
              <Reveal inView amount={0.15} direction="up" distance={28} delay={0.1}>
                <ContactForm recipient={recipient} />
              </Reveal>
            </div>
          </div>
        </MotionConfig>
      </LazyMotion>
    </section>
  );
}
```

- [ ] **Step 2: Typecheck**

Run (from `frontend/`):
```bash
npx tsc --noEmit
```
Expected: no errors in `ContactSection.tsx`.

---

## Task 8: Mount the section on the home page

**Files:**
- Modify: `frontend/src/app/(marketing)/page.tsx`

- [ ] **Step 1: Insert before pricing**

Replace the contents of `frontend/src/app/(marketing)/page.tsx` with:

```tsx
import { LenisProvider } from "@/components/providers/LenisProvider";
import { HeroSection } from "@/components/hero/HeroSection";
import { LaptopShowcase } from "@/components/hero/LaptopShowcase";
import { ContactSection } from "@/components/contact/ContactSection";
import { PricingSection } from "@/components/pricing/PricingSection";

export default function Home() {
  return (
    <LenisProvider>
      <HeroSection />
      <LaptopShowcase />
      <ContactSection />
      <PricingSection />
    </LenisProvider>
  );
}
```

---

## Task 9: Verification milestone

**Files:** none (verification only)

- [ ] **Step 1: Typecheck the whole frontend**

Run (from `frontend/`):
```bash
npx tsc --noEmit
```
Expected: no new errors from the files added/modified in this plan.

- [ ] **Step 2: Production build**

Run (from `frontend/`):
```bash
npm run build
```
Expected: build succeeds; `/` (marketing home) and `/contact` compile.

- [ ] **Step 3: Backend test suite (touched area)**

Run (from `backend/`, venv active):
```bash
python -m pytest auth_service/tests/test_contact_form.py -v
```
Expected: 5 passed.

- [ ] **Step 4: Manual smoke (dev servers running)**

Start backend (`uvicorn auth_service.main:app --reload --port 8001`) and frontend (`npm run dev`), then with the frontend's `FASTAPI_URL` pointing at `http://localhost:8001`:
- Visit `http://localhost:3000/` → the contact section renders **above** pricing; the Calendly calendar loads (gold-on-dark) on the left, form on the right (stacked on a narrow viewport).
- Submit the form with valid values → gold spinner fades in with "Sending your message…", then morphs into a gold checkmark while the text recolours to gold "Message sent — talk soon!". (With a real `RESEND_API_KEY` set on the backend, the email arrives at stefanromanpers@gmail.com; otherwise expect the error state + mailto fallback.)
- Visit `http://localhost:3000/contact` → the same new animation drives that form.
- Hover any button → pointer cursor.

> Optional Playwright check: use the existing Playwright MCP to drive the two pages and assert the spinner→checkmark transition. Stamp `[E2E-TEST]` into the message so the backend short-circuits Resend (no real email) when running against a preview backend.

---

## Task 10: Persist the cursor-pointer rule as a standing preference

**Files:**
- Create: `C:\Users\stefa\.claude\projects\c--Users-stefa--gemini-antigravity-scratch-CMS---websites\memory\feedback_cursor_pointer_buttons.md`
- Modify: the memory `MEMORY.md` index (add one pointer line)

- [ ] **Step 1: Write the memory file**

```markdown
---
name: feedback-cursor-pointer-buttons
description: All interactive buttons must show a pointer cursor
metadata:
  type: feedback
---

Every button (`<button>`, `[role="button"]`, clickable controls) must have
`cursor: pointer` unless disabled.

**Why:** Stefan wants buttons to feel obviously clickable; Tailwind v4 preflight
resets `<button>` to `cursor: default`.

**How to apply:** Enforced globally via a base-layer rule in
`frontend/src/app/globals.css` (`button:not(:disabled), [role="button"]…`).
For any new button outside that scope, add `cursor-pointer`. Apply on every
future task, not just the contact section.
```

- [ ] **Step 2: Add the index pointer to `MEMORY.md`**

Under `## Workflow preferences`, add:
```markdown
- [Buttons get cursor-pointer](feedback_cursor_pointer_buttons.md) — enforced globally in globals.css; apply to all new buttons.
```

---

## Commit (only when Stefan says so)

Per project convention, no auto-commits. When approved:

```bash
git add backend/auth_service/routers/forms.py \
        backend/auth_service/tests/test_contact_form.py \
        frontend/package.json frontend/package-lock.json \
        frontend/src/app/globals.css \
        frontend/src/components/ui/SubmitFeedback.tsx \
        frontend/src/components/contact/ContactForm.tsx \
        frontend/src/components/contact/CalendlyCalendar.tsx \
        frontend/src/components/contact/ContactSection.tsx \
        "frontend/src/app/(marketing)/page.tsx" \
        docs/superpowers/specs/2026-06-03-home-contact-section-design.md \
        docs/superpowers/plans/2026-06-03-home-contact-section.md
git commit -m "feat(marketing): home contact section with Calendly + real-sending form"
```

---

## Self-Review

**Spec coverage:**
- Contact section before pricing → Task 8. ✅
- Reusable themed Calendly → Task 2 + 6. ✅
- Form fields name/email/company(optional)/message, same styling, single shared component → Task 5 (existing component reused on both pages via Task 7). ✅
- Global cursor-pointer + standing rule → Task 3 + 10. ✅
- Spinner fade-in + text + success colour/content change + spinner→gold checkmark, reusable → Task 4; used by the Contact-page form too (same component) → Task 5. ✅
- Real auto-send to stefanromanpers@gmail.com → Task 1. ✅
- Side-by-side desktop / stacked mobile → Task 7. ✅
- Scroll-in fade for the section's pieces → Task 7 (`Reveal inView`). ✅

**Placeholder scan:** No TBD/TODO; every code step shows full content. ✅

**Type consistency:** `SubmitStatus` ("loading"|"success"|"error") and `SubmitFeedbackProps` in Task 4 match the props passed in Task 5; `Phase` maps to `SubmitStatus` explicitly. `CalendlyCalendarProps` matches the call in Task 7. Backend `ContactRequest` fields match the JSON body posted in Task 5. ✅
