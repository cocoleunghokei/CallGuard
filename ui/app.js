// Callguard UI entry point.
//
// Every Server message goes through ONE function: onMessage({type, data}).
// Handlers update `state`; view.js draws it. Messages come from the real
// Server, or from the replay harness via ?ws=fake (ui/dev/replay.html).
//
// Privacy: transcript text lives only in memory: state.tail (last 3 lines),
// state.transcript (this call, for "View full transcript") and the current
// check's evidence quotes. All are deleted on `call ended`; never stored or sent.

import { connect } from "./ws.js";
import { render, bindView, VERIFY_WAIT_MS } from "./view.js";
import { loadContacts } from "./contacts.js";

const TAIL_LINES = 3;
const TRANSCRIPT_MAX = 600; // ~30 min of 3 s chunks

export const state = {
  connected: false,
  consentDismissed: false, // memory only, for this session
  status: null, // {listening, online, model?, gate?}
  rules: [],
  rulesSource: null, // "default" | "custom" | null
  // Firm rules that came up this call: id -> times it newly appeared in check.rules_broken.
  // Call metadata only (no transcript); reset on call start and end.
  ruleHits: {},
  brokenNow: [], // rules_broken of the latest check, to count only new appearances
  // After-call summary (T11). During a call: peak level, tactics seen, last way out.
  // Tactic ids and counts only, never transcript or quotes. Becomes `summary` on call end.
  callLog: { peak: "low", tactics: [], outcome: null },
  // History tab: one summary per flagged call this session, newest first.
  // {id, ended: "HH:MM", peak, tactics, outcome, rules: [rule text]}; memory only, removed one by one.
  history: [],
  historyUnseen: false, // dot on the History tab until it is opened
  inCall: false,
  tail: [], // last TAIL_LINES TranscriptChunks, current call only
  // Whole call, for "View full transcript" (Coco, Sat). Memory only, capped, deleted on call end.
  transcript: [],
  check: null, // latest ScamCheck
  verify: null,
  gate: null, // {state, reason, release_in, until} while not "off"; `until` = local ms when the countdown ends
  markedSafe: false, // user took the "it's safe" exit; cleared by the next check (the Server decides after that)
  // Verify line: when we started waiting for the claimed org's number. The
  // Server never looks up some identities (an internal team, a partner), so
  // the "Checking…" line hides after VERIFY_WAIT_MS with no answer.
  verifyWait: null, // {org, since}
  egress: [], // EgressEntry[] + {seq, call}, newest first, kept for the session (org names only)
  // Danger overlay (T6). Sticky: opens on danger, closes only on call end, mark
  // safe, or a release (T7).
  // `seen` = tactics already warned about this call; a closed overlay reopens
  // only for a new one (same no re-nagging rule as the gate, prd 7.5).
  // mode: always "warning" (the "Hang up and call back" exit was removed, Coco Sat).
  overlay: { open: false, opens: 0, seen: [], mode: "warning" },
  calls: 0, // calls started this session; tags egress entries "This call" vs "Earlier today"
  ui: { expanded: null, view: "panel", egressOpen: false, egressEntry: null }, // open pill, view, egress panel, open entry seq
  // Sidebar: which tab is shown. Not reset by calls.
  tab: "call", // "call" | "rules" | "history" | "contacts"
  contacts: loadContacts(), // [{id, role, name, phone}], set on this laptop, never sent
  editContact: null, // id of the contact being edited
  contactsNote: null, // {ok, text} after a save, from `contacts_saved`
};

const handlers = {
  status(data) {
    state.status = data || null;
  },
  contacts(data) {
    if (Array.isArray(data)) state.contacts = data;
  },
  contacts_saved(data) {
    const ok = !!(data && data.ok);
    const errors = (data && Array.isArray(data.errors) && data.errors) || [];
    state.contactsNote = { ok, text: ok ? "Saved on this laptop." : errors.join(" ") || "Couldn't save." };
    if (ok) {
      const shown = state.contactsNote;
      setTimeout(() => {
        if (state.contactsNote === shown) state.contactsNote = null;
        render(state);
      }, 2500);
    }
  },
  rules(data, msg) {
    state.rules = Array.isArray(data) ? data : [];
    state.rulesSource = (msg && msg.source) || null;
  },
  call(data) {
    const s = data && data.state;
    if (s !== "started" && s !== "ended") return;
    const sum = s === "ended" && state.inCall ? summarize() : null;
    if (sum) {
      state.history.unshift(sum);
      if (state.tab !== "history") state.historyUnseen = true;
    }
    wipeCall();
    state.inCall = s === "started";
    if (state.inCall) state.calls += 1;
  },
  transcript(data) {
    if (!data || typeof data.text !== "string") return;
    state.tail.push(data);
    state.transcript.push(data);
    if (state.transcript.length > TRANSCRIPT_MAX) state.transcript.splice(0, state.transcript.length - TRANSCRIPT_MAX);
    if (state.tail.length > TAIL_LINES) state.tail.splice(0, state.tail.length - TAIL_LINES);
  },
  check(data) {
    state.check = data || null;
    state.markedSafe = false;
    const broken = (data && data.rules_broken) || [];
    for (const id of broken) if (!state.brokenNow.includes(id)) state.ruleHits[id] = (state.ruleHits[id] || 0) + 1;
    state.brokenNow = [...broken];
    if (state.inCall && data) {
      const log = state.callLog;
      if (RANK[data.risk] > RANK[log.peak]) log.peak = data.risk;
      if (data.risk === "watch" || data.risk === "danger")
        for (const t of data.tactics || []) if (!log.tactics.includes(t)) log.tactics.push(t);
    }
    const org = data && data.claimed_identity;
    const shown = data && (data.risk === "watch" || data.risk === "danger"); // the verify line is on screen
    if (org && shown && (!state.verifyWait || state.verifyWait.org !== org)) {
      state.verifyWait = { org, since: Date.now() };
      setTimeout(() => render(state), VERIFY_WAIT_MS + 50);
    }
    if (state.inCall && data && data.risk === "danger") openOverlayFor(data.tactics || []);
  },
  verify(data) {
    state.verify = data || null;
  },
  gate(data) {
    const wasLocked = !!(state.gate && state.gate.state === "locked");
    if (data && data.state && data.state !== "off") {
      const sec = Number(data.release_in);
      state.gate = { ...data, until: Number.isFinite(sec) && sec > 0 ? Date.now() + sec * 1000 : null };
      return;
    }
    state.gate = null;
    // Auto-release with no exit taken: step back to the red side panel (prd 7.5).
    // "Show the warning" reopens it; danger stays on the panel.
    if (wasLocked && state.overlay.open && state.overlay.mode === "warning") {
      state.overlay.open = false;
      if (!state.callLog.outcome) state.callLog.outcome = "timed_out";
    }
  },
  egress(data) {
    if (!data) return;
    state.egress.unshift({ ...data, seq: state.egress.length + 1, call: state.inCall ? state.calls : 0 });
  },
};

/** The single dispatch point for Server -> UI messages. */
export function onMessage({ type, data, source }) {
  const handle = handlers[type];
  if (handle) handle(data, { source });
  render(state);
}

function openOverlayFor(tactics) {
  const o = state.overlay;
  const fresh = tactics.filter((t) => !o.seen.includes(t));
  o.seen.push(...fresh);
  if (o.open) return; // update in place
  if (o.opens === 0 || fresh.length) {
    state.tab = "call"; // the warning belongs to the call, whatever tab was open
    o.open = true;
    o.mode = "warning";
    o.opens += 1; // the view plays the tone once per open
  }
}

const RANK = { low: 0, watch: 1, danger: 2 };

/** The card for the call that just ended, or null for a calm call. */
function summarize() {
  const log = state.callLog;
  if (log.peak !== "watch" && log.peak !== "danger") return null;
  const hit = new Set(Object.keys(state.ruleHits));
  const now = new Date();
  return {
    id: `${now.getTime()}-${state.calls}`,
    ended: `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`,
    peak: log.peak,
    tactics: [...log.tactics],
    outcome: log.outcome,
    rules: state.rules.filter((r) => hit.has(r.id)).map((r) => r.text || String(r.id).replace(/_/g, " ")),
  };
}

function wipeCall() {
  state.tail.length = 0;
  state.check = null;
  state.transcript.length = 0;
  state.verify = null;
  state.verifyWait = null;
  state.gate = null;
  state.ui.expanded = null;
  state.ui.view = "panel";
  state.ui.ovFull = false;
  state.overlay = { open: false, opens: 0, seen: [], mode: "warning" };
  state.markedSafe = false;
  state.ruleHits = {};
  state.brokenNow = [];
  state.callLog = { peak: "low", tactics: [], outcome: null };
}

// The pause countdown ticks here, re-synced by every `gate` message. At 0:00
// it releases locally too, in case the Server's `gate off` is late.
let shownSec = null;
setInterval(() => {
  const g = state.gate;
  if (!g || g.state !== "locked" || !g.until) return;
  const left = Math.ceil((g.until - Date.now()) / 1000);
  if (left <= 0) handlers.gate({ state: "off" });
  else if (left === shownSec) return; // only redraw when the shown time changes
  shownSec = left;
  render(state);
}, 250);

bindView(state, () => render(state));
render(state);
connect(onMessage, (open) => {
  state.connected = open;
  render(state);
});
