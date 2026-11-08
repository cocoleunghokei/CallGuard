// Emergency contacts: who the user calls when a call feels wrong.
//
// The Server owns them (callguard/server/contacts.py): it sends `contacts` on
// connect and saves `save_contacts` to one local file. These defaults (same as
// the Server's) only show before it connects, or in the replay harness.
// The UI itself keeps nothing on disk (no browser storage, test_privacy.py).
// They are the user's own colleagues, never call content, and never sent.

export const DEFAULT_CONTACTS = [
  { id: "oit", role: "IT security (OIT)", name: "OIT help desk", phone: "" },
  { id: "manager", role: "Line manager", name: "", phone: "" },
];

export function loadContacts() {
  return DEFAULT_CONTACTS.map((c) => ({ ...c }));
}
