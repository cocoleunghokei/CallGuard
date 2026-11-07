// Callguard UI entry point.
//
// Every Server message goes through ONE function: onMessage({type, data}).
// Handlers update `state`; view.js draws it. Messages come from the real
// Server, or from the replay harness via ?ws=fake (ui/dev/replay.html).
//
// Privacy: transcript text lives only in state.tail (last 3 lines) and in the
// current check's evidence quotes. Both are deleted on `call ended`.

import { connect } from "./ws.js";
import { render, bindView, VERIFY_WAIT_MS } from "./view.js";

const TAIL_LINES = 3;

export const state = {
  connected: false,
  consentDismissed: false, // memory only, for this session
  status: null, // {listening, online, model?, gate?}
  rules: [],
  inCall: false,
  tail: [], // last TAIL_LINES TranscriptChunks, current call only
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
  // safe, a release (T7), or the local "Hang up and call back" button.
  // `seen` = tactics already warned about this call; a closed overlay reopens
  // only for a new one (same no re-nagging rule as the gate, prd 7.5).
  // mode: "warning" | "callback" (after "Hang up and call back").
  overlay: { open: false, opens: 0, seen: [], mode: "warning" },
  calls: 0, // calls started this session; tags egress entries "This call" vs "Earlier today"
  ui: { expanded: null, view: "panel", egressOpen: false, egressEntry: null }, // open pill, view, egress panel, open entry seq
};

const handlers = {
  status(data) {
    state.status = data || null;
  },
  rules(data) {
    state.rules = Array.isArray(data) ? data : [];
  },
  call(data) {
    const s = data && data.state;
    if (s !== "started" && s !== "ended") return;
    wipeCall();
    state.inCall = s === "started";
    if (state.inCall) state.calls += 1;
  },
  transcript(data) {
    if (!data || typeof data.text !== "string") return;
    state.tail.push(data);
    if (state.tail.length > TAIL_LINES) state.tail.splice(0, state.tail.length - TAIL_LINES);
  },
  check(data) {
    state.check = data || null;
    state.markedSafe = false;
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
    if (wasLocked && state.overlay.open && state.overlay.mode === "warning") state.overlay.open = false;
  },
  egress(data) {
    if (!data) return;
    state.egress.unshift({ ...data, seq: state.egress.length + 1, call: state.inCall ? state.calls : 0 });
  },
};

/** The single dispatch point for Server -> UI messages. */
export function onMessage({ type, data }) {
  const handle = handlers[type];
  if (handle) handle(data);
  render(state);
}

function openOverlayFor(tactics) {
  const o = state.overlay;
  const fresh = tactics.filter((t) => !o.seen.includes(t));
  o.seen.push(...fresh);
  if (o.open) return; // update in place
  if (o.opens === 0 || fresh.length) {
    o.open = true;
    o.mode = "warning";
    o.opens += 1; // the view plays the tone once per open
  }
}

function wipeCall() {
  state.tail.length = 0;
  state.check = null;
  state.verify = null;
  state.verifyWait = null;
  state.gate = null;
  state.ui.expanded = null;
  state.ui.view = "panel";
  state.overlay = { open: false, opens: 0, seen: [], mode: "warning" };
  state.markedSafe = false;
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
