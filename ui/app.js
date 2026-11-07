// Callguard UI entry point.
//
// Every Server message goes through ONE function: onMessage({type, data}).
// Later tasks (T2+) add renderers to `handlers`; nothing else needs to know
// where messages come from (real Server, or the replay harness via ?ws=fake).
//
// T1 renders a plain placeholder so the harness has something to show. T2
// replaces render() with the real panel (see ui/dev/prototype.html).
//
// Privacy: transcript text lives only in state.tail (last 3 lines) and in the
// current check's evidence quotes. Both are deleted on `call ended`.

import { connect, send } from "./ws.js";

const TAIL_LINES = 3;

const state = {
  connected: false,
  status: null, // {listening, online, model?, gate?}
  rules: [],
  inCall: false,
  tail: [], // last TAIL_LINES TranscriptChunks, current call only
  check: null, // latest ScamCheck
  verify: null,
  gate: null, // {state, reason, release_in}
  egress: [], // EgressEntry[], kept for the session (org names only)
};

const handlers = {
  status(data) {
    state.status = data;
  },
  rules(data) {
    state.rules = Array.isArray(data) ? data : [];
  },
  call(data) {
    if (data && data.state === "started") {
      wipeCall();
      state.inCall = true;
    } else if (data && data.state === "ended") {
      wipeCall();
      state.inCall = false;
    }
  },
  transcript(data) {
    state.tail.push(data);
    if (state.tail.length > TAIL_LINES) state.tail.splice(0, state.tail.length - TAIL_LINES);
  },
  check(data) {
    state.check = data;
  },
  verify(data) {
    state.verify = data;
  },
  gate(data) {
    state.gate = data && data.state !== "off" ? data : null;
  },
  egress(data) {
    state.egress.unshift(data);
  },
};

/** The single dispatch point for Server -> UI messages. */
export function onMessage({ type, data }) {
  const handle = handlers[type];
  if (handle) handle(data);
  render();
}

function wipeCall() {
  state.tail.length = 0;
  state.check = null;
  state.verify = null;
  state.gate = null;
}

// ---------------------------------------------------------------- placeholder render (T1 only)

const $ = (id) => document.getElementById(id);

function render() {
  const s = state.status;
  $("conn").textContent = state.connected ? "" : "Connecting to Callguard…";
  $("hdr").textContent = s
    ? `${s.listening ? "Listening locally · nothing stored" : "Not listening"} · ${s.online ? "Online" : "Offline"}` +
      (s.model && s.model !== "ok" ? " · Basic checks only" : "")
    : "";
  const c = state.check;
  $("level").textContent = !state.inCall ? "Not on a call" : c ? c.risk : "low";
  $("reason").textContent = state.inCall && c ? c.reason || "" : "";
  $("verify").textContent = !state.verify
    ? ""
    : state.verify.phone
      ? `${state.verify.org}: ${state.verify.phone}`
      : `${state.verify.org}: ${state.verify.status || "looking up"}`;
  $("gate").textContent = state.gate ? `Pause: ${state.gate.state}` : "";
  $("tail").replaceChildren(
    ...state.tail.map((t) => {
      const p = document.createElement("p");
      p.textContent = `${t.speaker === "you" ? "You" : "Caller"}: ${t.text}`;
      return p;
    }),
  );
  $("egress").textContent = state.egress.length
    ? `What left this device (${state.egress.length})`
    : "Nothing has left this device";
}

function bindButtons() {
  $("b-colleague").onclick = () => send("colleague");
  $("b-safe").onclick = () => send("mark_safe");
  $("b-hangup").onclick = () => send("gate_release", { how: "hang_up" });
  $("b-end").onclick = () => send("end_call");
}

bindButtons();
render();
connect(onMessage, (open) => {
  state.connected = open;
  render();
});
