/**
 * Contact-page content. Edit everything in `contact.json`.
 *  - `address` is shown only when it's non-empty: drop your registered street
 *    address in there and it appears under the location automatically.
 *  - `phone` is what people see; `phoneHref` is the dialable form (digits + "+",
 *    no spaces) used by the tap-to-call link.
 *  - `email` is both shown and used as the recipient of the message form.
 */
import data from "./contact.json";

export interface ContactDetails {
  email: string;
  phone: string;
  phoneHref: string;
  location: string;
  address: string;
  hours: string;
}

export interface ContactContent {
  hero: { eyebrow: string; title: string; lead: string };
  details: ContactDetails;
}

export const contact = data as ContactContent;
