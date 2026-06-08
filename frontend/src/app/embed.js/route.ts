import { NextResponse } from "next/server";

/**
 * GET /embed.js
 *
 * Returns a self-contained loader script that third-party sites can drop in
 * with a single <script> tag.  The script:
 *  1. Reads data-tenant from its own <script> element.
 *  2. Creates a sandboxed <iframe> pointing at /w/{tenant} on this origin.
 *  3. Listens for postMessage from the iframe:
 *     - booking_resize  → updates the iframe height (auto-sizing).
 *     - booking_completed → dispatches a CustomEvent on the host document.
 *
 * Written as ES5-compatible JS so it works on any site without a bundler.
 */
export function GET() {
  const js = `(function () {
  var script = document.currentScript;
  if (!script) { return; }
  var tenant = script.getAttribute('data-tenant');
  if (!tenant) { return; }
  var src = script.src || '';
  var origin = '';
  try {
    var url = new URL(src);
    origin = url.origin;
  } catch (e) {
    origin = window.location.origin;
  }
  var iframe = document.createElement('iframe');
  iframe.src = origin + '/w/' + encodeURIComponent(tenant);
  iframe.style.width = '100%';
  iframe.style.border = '0';
  iframe.style.display = 'block';
  iframe.setAttribute('title', 'Booking widget');
  script.parentNode && script.parentNode.insertBefore(iframe, script.nextSibling);
  window.addEventListener('message', function (event) {
    if (event.origin !== origin) { return; }
    var data = event.data;
    if (!data || typeof data !== 'object') { return; }
    if (data.type === 'booking_resize' && typeof data.height === 'number') {
      iframe.style.height = data.height + 'px';
    }
    if (data.type === 'booking_completed') {
      document.dispatchEvent(new CustomEvent('booking_completed', { detail: data }));
    }
  });
})();`;

  return new NextResponse(js, {
    headers: {
      "Content-Type": "application/javascript",
      "Cache-Control": "public, max-age=300",
    },
  });
}
