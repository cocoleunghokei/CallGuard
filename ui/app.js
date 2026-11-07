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
  gate: null, // {state, reason, release_in} while not "off"
  // Verify line: when we started waiting for the claimed org's number. The
  // Server never looks up some identities (an internal team, a partner), so
  // the "Checking…" line hides after VERIFY_WAIT_MS with no answer.
  verifyWait: null, // {org, since}
  egress: [], // EgressEntry[] + {seq, call}, newest first, kept for the session (org names only)
  // Danger overlay (T6). Sticky: opens on danger, closes only on call end, mark
  // safe, a release (T7), or the local "Hang up and call back" button.
  // `seen` = tactics already warned about this call; a closed overlay reopens
  // only for a new one (same no re-nagging rule as the gate, prd 7.5).
  overlay: { open: false, opens: 0, seen: [] },
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
    state.gate = data && data.state && data.state !== "off" ? data : null;
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
  state.overlay = { open: false, opens: 0, seen: [] };
}

bindView(state, () => render(state));
render(state);
connect(onMessage, (open) => {
  state.connected = open;
  render(state);
});
