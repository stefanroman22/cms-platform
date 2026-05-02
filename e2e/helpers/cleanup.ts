/**
 * Restore the e2e-test-project's services to the seed state by
 * calling the backend admin API. Tests call resetSeedState() in
 * afterEach to keep runs deterministic.
 */
const BACKEND =
  process.env.E2E_BASE_URL_BACKEND ?? "https://cms-backend-roman.vercel.app";

const SEED = {
  e2e_text: { title: "E2E Title", body: "E2E Body" },
  e2e_features: {
    _schema: [
      { key: "label", label: "Label", type: "string" },
      { key: "detail", label: "Detail", type: "richtext" },
    ],
    items: [
      { label: "alpha", detail: "first" },
      { label: "beta", detail: "second" },
    ],
  },
  e2e_contact_form: { destination_email: "e2e-user@cms-test.local" },
} as const;

export async function resetSeedState(sid: string): Promise<void> {
  const headers = {
    "Content-Type": "application/json",
    Cookie: `sid=${sid}`,
  };
  for (const [serviceKey, content] of Object.entries(SEED)) {
    const resp = await fetch(
      `${BACKEND}/projects/e2e-test-project/services/${serviceKey}`,
      { method: "PUT", headers, body: JSON.stringify({ content }) },
    );
    if (!resp.ok) {
      throw new Error(
        `reset ${serviceKey} failed: ${resp.status} ${await resp.text()}`,
      );
    }
  }
  await fetch(`${BACKEND}/projects/e2e-test-project/publish`, {
    method: "POST",
    headers,
  });
}

export async function getSidCookie(
  email: string,
  password: string,
): Promise<string> {
  const resp = await fetch(`${BACKEND}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!resp.ok) throw new Error(`login failed: ${resp.status}`);
  const setCookie = resp.headers.get("set-cookie") ?? "";
  const m = setCookie.match(/sid=([^;]+)/);
  if (!m) throw new Error("no sid in Set-Cookie");
  return m[1];
}
