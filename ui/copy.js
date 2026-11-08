// All fixed UI wording for tactics. Coco signs off on changes here.
// tests/ui/test_copy.py checks PLAIN against the design brief and the SAY
// lines against prd.md 18.3.

/** The brief's plain words for each tactic (accessible name, tooltips, details). */
export const PLAIN = {
  authority: "Claims to be an official or someone senior",
  secrecy: "Asks you to keep it secret",
  urgency: "Rushing you",
  threat: "Threatens you or the firm",
  credential_request: "Asks for a code or password",
  bank_change: "Wants to change bank details",
  bypass_approval: "Wants you to skip the usual approval",
  payment_request: "Asks you to send money",
  remote_access: "Asks you to install software or give screen access",
  personal_data_request: "Asks for client or personal data",
  inside_knowledge: "Uses real details to sound legitimate",
};

/** Short pill labels (prototype v3, signed off by Coco). */
export const SHORT = {
  authority: "Claims authority",
  secrecy: "Keep it secret",
  urgency: "Rushing you",
  threat: "Threatens you",
  credential_request: "Asks for a code",
  bank_change: "Bank change",
  bypass_approval: "Skip approval",
  payment_request: "Send money",
  remote_access: "Screen access",
  personal_data_request: "Asks for data",
  inside_knowledge: "Knows details",
};

/** Unknown tactic ids: the id with underscores replaced by spaces. */
export function plainWords(tactic) {
  return PLAIN[tactic] || String(tactic).replace(/_/g, " ");
}

export function shortWords(tactic) {
  return SHORT[tactic] || String(tactic).replace(/_/g, " ");
}

/** "Say this" lines (prd.md 18.3, UI-15). */
export const SAY = {
  credential_request: "I don't share codes on calls. I'll contact IT myself.",
  bank_change: "I'll call you back on the number we have on file.",
  payment_request: "I can't send money from a call. I'll call you back on a number I already have.",
  bypass_approval: "Every payment needs two approvals. I'll get the second one.",
  remote_access: "I can't install anything a caller asks for. I'll check with IT.",
  personal_data_request: "Please send that request in writing through the usual channel.",
  secrecy: "I need to check this with a colleague before I do anything.",
  threat: "I'll call your office back on its public number.",
  urgency: "I can't do this right now. What's your callback number?",
  authority: "Thanks. I'll call back on your organization's public number to confirm.",
};

/** Ask tactics first, then the rest (prd.md 18.3). "authority (alone)" falls out
 *  of the order: any other listed tactic is picked before it. */
const SAY_ORDER = [
  "credential_request",
  "bank_change",
  "payment_request",
  "bypass_approval",
  "remote_access",
  "personal_data_request",
  "secrecy",
  "threat",
  "urgency",
  "authority",
];

/** The sentence to say for a set of tactics, or null. */
export function sayThis(tactics) {
  const has = new Set(tactics || []);
  for (const t of SAY_ORDER) {
    if (!has.has(t)) continue;
    if (t === "threat" && !has.has("authority")) continue; // "threat (with authority)"
    return SAY[t];
  }
  return null;
}

/** Signs words from the 10-segment bar (never a percentage). */
export function signsWords(segments) {
  if (segments >= 8) return "Strong signs";
  if (segments >= 4) return "Some signs";
  return "No clear signs";
}

/** What the pause is about, when the Server's gate.reason is missing. */
export const ASK = {
  credential_request: "for a code or password",
  bank_change: "you to change bank details",
  payment_request: "you to send money",
  bypass_approval: "you to skip the usual approval",
  remote_access: "you to install software or share your screen",
  personal_data_request: "for client or personal data",
};

/** The pause line (prd 7.6). Prefers the Server's fixed gate.reason. It never
 *  says typing is blocked: the pause never blocks typing (AGENTS.md 3). */
export function askLine(gate, tactics) {
  if (gate && gate.reason) return gate.reason;
  const ask = SAY_ORDER.find((t) => ASK[t] && (tactics || []).includes(t));
  return ask ? `This call is asking ${ASK[ask]}. Verify before you act.` : "Verify before you act on anything from this call.";
}

/** "1:54" from seconds. */
export function mmss(sec) {
  const s = Math.max(0, Math.ceil(sec));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** "Check with a colleague" heads-up (Coco, Sat): goes to the firm's IT team and
 *  the user's line manager, fixed wording only, never anything from the call.
 *  The hackathon build shows it here and sends nothing, so it says so: the
 *  "What left this device" log must stay true. */
export const HEADS_UP = {
  title: "Heads-up for IT and your manager",
  message: "Callguard heads-up: a call on this laptop looks suspicious. Please check in.",
  note: "Demo: not sent. In the full version this goes to your IT team and your manager. Stay on the line or hang up, your choice.",
};

/** After-call summary (T11 / UI-10). What the call looked like, from tactics
 *  only: no names, no numbers, no caller words. First match wins. */
const CALL_KINDS = [
  [["credential_request"], "Someone asking for a login code"],
  [["bank_change"], "Someone asking to change bank details"],
  [["payment_request"], "Someone pushing for a payment"],
  [["remote_access"], "Someone asking for screen access"],
  [["authority", "threat"], "Someone posing as an official"],
  [["personal_data_request"], "Someone asking for client or personal data"],
  [["secrecy"], "Someone asking you to keep a call secret"],
];

export function callKind(tactics) {
  const has = new Set(tactics || []);
  for (const [need, words] of CALL_KINDS) if (need.every((t) => has.has(t))) return words;
  return "A call with pressure signs";
}

export const OUTCOME = {
  hang_up: "you hung up to call back",
  colleague: "you checked with a colleague",
  mark_safe: "you marked it safe",
  timed_out: "the pause ran out",
};
