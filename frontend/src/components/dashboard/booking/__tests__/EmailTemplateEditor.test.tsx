/**
 * Tests for the Booking Email Template Editor (B4).
 *
 * 1. Debounce: multiple rapid draft changes trigger previewEmail only once
 *    (after the 300 ms timer fires).
 * 2. email_copy field logic: pure helper verifies set/delete semantics that
 *    the editor uses for its draft state.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act } from "@testing-library/react";
import { EmailPreviewFrame } from "../EmailPreviewFrame";

// ── Shared mock data ──────────────────────────────────────────────────────────

const PREVIEW_RESPONSE = { html: "<html><body>Preview</body></html>" };

function makePreviewFetch() {
  return vi.fn().mockResolvedValue({
    ok: true,
    json: () => Promise.resolve(PREVIEW_RESPONSE),
  });
}

// ── Test 1: debounce ──────────────────────────────────────────────────────────

describe("EmailPreviewFrame debounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("calls previewEmail exactly once after rapid draft changes", async () => {
    const fetchMock = makePreviewFetch();
    global.fetch = fetchMock;

    const draft = { accent_color: "#18181b", email_copy: {} };

    const { rerender } = render(
      <EmailPreviewFrame slug="test-slug" caseKey="confirmation" draft={draft} />
    );

    // Advance just under the debounce threshold (150 ms) — no call yet
    await act(async () => {
      vi.advanceTimersByTime(150);
    });
    expect(fetchMock).not.toHaveBeenCalled();

    // Change draft twice more before the timer fires — each rerender resets the timer
    rerender(
      <EmailPreviewFrame
        slug="test-slug"
        caseKey="confirmation"
        draft={{ ...draft, email_copy: { confirm_subject: "Draft 2" } }}
      />
    );
    rerender(
      <EmailPreviewFrame
        slug="test-slug"
        caseKey="confirmation"
        draft={{ ...draft, email_copy: { confirm_subject: "Draft 3" } }}
      />
    );

    // Fire the debounce timer and flush the resulting fetch promise
    await act(async () => {
      vi.runAllTimers();
      await Promise.resolve();
      await Promise.resolve();
    });

    // Exactly one preview fetch should have fired
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    // Should use the last draft state
    expect(body.case).toBe("confirmation");
    expect(body.draft.email_copy?.confirm_subject).toBe("Draft 3");
  });
});

// ── Test 2: email_copy set/delete semantics (pure logic) ─────────────────────

describe("email_copy draft logic", () => {
  /**
   * Mirrors the setCopyKey logic used inside EmailTemplateEditor:
   * - Setting a non-empty value stores it.
   * - Setting an empty value deletes the key (→ falls back to server default).
   */
  function applyCopyKey(
    copy: Record<string, string>,
    key: string,
    value: string
  ): Record<string, string> {
    const next = { ...copy };
    if (value === "") {
      delete next[key];
    } else {
      next[key] = value;
    }
    return next;
  }

  it("stores a non-empty override", () => {
    const copy = applyCopyKey({}, "confirm_subject", "Custom subject");
    expect(copy).toEqual({ confirm_subject: "Custom subject" });
  });

  it("removes the key when value is cleared (→ falls back to default)", () => {
    const copy = applyCopyKey({ confirm_subject: "Custom subject" }, "confirm_subject", "");
    expect(copy).not.toHaveProperty("confirm_subject");
  });

  it("seeds email_copy from field values that are non-empty", () => {
    const fields = [
      { key: "join_cta", value: "Join now" },
      { key: "confirm_subject", value: "" }, // empty → not seeded
    ];
    const emailCopy: Record<string, string> = {};
    for (const f of fields) {
      if (f.value) emailCopy[f.key] = f.value;
    }
    expect(emailCopy).toEqual({ join_cta: "Join now" });
    expect(emailCopy).not.toHaveProperty("confirm_subject");
  });
});
