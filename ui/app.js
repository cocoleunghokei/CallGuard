// Callguard UI entry point.
//
// Every Server message goes through ONE function: onMessage({type, data}).
// Handlers update `state`; view.js draws it. Messages come from the real
// Server, or from the replay harness via ?ws=fake (ui/dev/replay.html).
//
// Privacy: transcript text lives only in state.tail (last 3 lines) and in the
// current check's evidence quotes. Both are deleted on `call ended`.

import { connect } from "./ws.js";
import { render, bindView } from "./view.js";

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
  egress: [], // EgressEntry[], newest first, kept for the session (org names only)
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
  },
  transcript(data) {
    if (!data || typeof data.text !== "string") return;
    state.tail.push(data);
    if (state.tail.length > TAIL_LINES) state.tail.splice(0, state.tail.length - TAIL_LINES);
  },
  check(data) {
    state.check = data || null;
  },
  verify(data) {
    state.verify = data || null;
  },
  gate(data) {
    state.gate = data && data.state && data.state !== "off" ? data : null;
  },
  egress(data) {
    if (data) state.egress.unshift(data);
  },
};

/** The single dispatch point for Server -> UI messages. */
export function onMessage({ type, data }) {
  const handle = handlers[type];
  if (handle) handle(data);
  render(state);
}

function wipeCall() {
  state.tail.length = 0;
  state.check = null;
  state.verify = null;
  state.gate = null;
}

bindView(state, () => render(state));
render(state);
connect(onMessage, (open) => {
  state.connected = open;
  render(state);
});
