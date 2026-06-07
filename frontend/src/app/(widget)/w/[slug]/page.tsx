"use client";

import { use, useEffect } from "react";
import { BookingCalendar } from "@/components/booking/BookingCalendar";

/**
 * Full-bleed booking widget page — rendered inside an iframe by embed.js.
 * Communicates height changes back to the parent via postMessage so the
 * iframe can auto-size without scroll bars.
 */
export default function WidgetPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = use(params);

  useEffect(() => {
    if (typeof window === "undefined") return;

    function postHeight() {
      const height = document.body.scrollHeight;
      window.parent.postMessage({ type: "booking_resize", height }, "*");
    }

    postHeight();

    const ro = new ResizeObserver(postHeight);
    ro.observe(document.body);
    return () => ro.disconnect();
  }, []);

  return (
    <div className="min-h-screen bg-transparent px-4 py-8">
      <div className="mx-auto max-w-lg">
        <BookingCalendar slug={slug} embedded />
      </div>
    </div>
  );
}
