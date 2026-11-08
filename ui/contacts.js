// Emergency contacts: who the user calls when a call feels wrong.
//
// The firm sets these once, here. Edits made in the window last until it
// closes: the UI keeps nothing on disk (no browser storage, test_privacy.py).
// Saving edits for good needs the Server (a `contacts` message, like `rules`).
// They are the user's own colleagues, never call content, and never sent.

export const DEFAULT_CONTACTS = [
  { id: "oit", role: "IT security (OIT)", name: "OIT help desk", phone: "" },
  { id: "manager", role: "Line manager", name: "", phone: "" },
];

export function loadContacts() {
  return DEFAULT_CONTACTS.map((c) => ({ ...c }));
}
