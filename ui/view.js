// Draws `state` (see app.js) into ui/index.html. Never logs, never stores.
// The UI follows `check` exactly as sent: no smoothing of its own (Server C10).

import { plainWords, shortWords, sayThis, signsWords } from "./copy.js";
import { send } from "./ws.js";

/** How long the verify line says "Checking…" before it gives up and hides. */
export const VERIFY_WAIT_MS = 5000;

const $ = (id) => document.getElementById(id);

// Level: colour + icon + one word (colour is never alone).
const LEVELS = {
  idle: { icon: "#i-idle", word: "Not on a call" },
  low: { icon: "#i-low", word: "Low" },
  watch: { icon: "#i-watch", word: "Watch" },
  danger: { icon: "#i-danger", word: "Danger" },
};
const DEFAULT_SIGNS = { low: "No clear signs", watch: "Some signs", danger: "Strong signs" };

let rerender = () => {};

export function level(state) {
  if (!state.inCall) return "idle";
  const r = state.check && state.check.risk;
  return LEVELS[r] ? r : "low";
}

/** Small element helper. Text always goes in as textContent, never HTML. */
function h(tag, props = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v;
    else if (k === "text") el.textContent = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? "" : v);
  }
  el.append(...kids.filter((k) => k != null && k !== false));
  return el;
}

/** One-time wiring for controls that only change local UI state. */
export function bindView(state, redraw) {
  rerender = redraw;
  $("consent-x").addEventListener("click", () => {
    state.consentDismissed = true;
    rerender();
  });
  $("open-said").addEventListener("click", () => {
    state.ui.view = "said";
    rerender();
    $("close-said").focus();
  });
  $("close-said").addEventListener("click", () => {
    state.ui.view = "panel";
    rerender();
    $("open-said").focus();
  });
  $("end-call").addEventListener("click", () => send("end_call"));
  $("ov-hangup").addEventListener("click", () => {
    // T6 placeholder: closes the overlay here only. T7 sends gate_release.
    state.overlay.open = false;
    rerender();
    $("show-warning").focus();
  });
  $("show-warning").addEventListener("click", () => {
    state.overlay.open = true; // not a new open: no tone
    rerender();
    $("ov-hangup").focus();
  });
  $("overlay").addEventListener("keydown", (e) => overlayKeys(e));
  $("priv-btn").addEventListener("click", () => {
    state.ui.egressOpen = !state.ui.egressOpen;
    rerender();
  });
  $("copy").addEventListener("click", async () => {
    const phone = state.verify && state.verify.phone;
    if (!phone) return;
    try {
      await navigator.clipboard.writeText(phone);
      $("copy").textContent = "Copied";
    } catch {
      $("copy").textContent = "Copy failed";
    }
    setTimeout(() => ($("copy").textContent = "Copy"), 1500);
  });
}

export function render(state) {
  // Keep keyboard focus on the same control across re-renders.
  const active = document.activeElement;
  const focusKey = active && active.dataset ? active.dataset.key : null;

  const lv = level(state);
  $("main").className = `body lv-ctx-${lv}`;
  if (!state.inCall || !state.check) clearCallDom();
  renderHeader(state);
  renderBanners(state);
  renderHero(state, lv);
  renderWhy(state, lv);
  renderTodo(state, lv);
  renderSaid(state);
  renderTail(state, lv);
  renderPrivacy(state);
  renderOverlay(state, lv);

  if (focusKey) {
    const el = document.querySelector(`[data-key="${CSS.escape(focusKey)}"]`);
    if (el && el !== document.activeElement) el.focus();
  }
}

// ---------------------------------------------------------------- A header

function renderHeader(state) {
  const s = state.status;
  const listening = !!(s && s.listening);
  $("badge").classList.toggle("off", !listening);
  $("badge-text").textContent = listening ? "Listening locally · nothing stored" : "Not listening · nothing stored";

  const online = !s || s.online !== false; // unknown counts as online until told
  $("net").classList.toggle("off", !online);
  $("net-text").textContent = online ? "Online" : "Offline";
  $("pause").hidden = !(s && s.gate === "on");

  $("consent").hidden = state.consentDismissed;
}

// ---------------------------------------------------------------- B banners

function renderBanners(state) {
  $("b-conn").hidden = state.connected;
  const model = state.status && state.status.model;
  $("b-model").hidden = !(state.connected && (model === "degraded" || model === "offline"));
}

// ---------------------------------------------------------------- C status hero

function renderHero(state, lv) {
  const L = LEVELS[lv];
  $("hero").className = `hero lv-${lv}`;
  $("hero").hidden = state.ui.view === "said";
  $("hero-icon").setAttribute("href", L.icon);
  $("hero-word").textContent = L.word;

  const bar = $("hero-bar");
  const c = state.check && typeof state.check.confidence === "number" ? state.check.confidence : null;
  if (lv === "idle") {
    $("hero-words").textContent = "Callguard starts when a call does.";
    bar.replaceChildren();
  } else if (c == null) {
    // No confidence: no bar. The default words still name the level.
    $("hero-words").textContent = DEFAULT_SIGNS[lv];
    bar.replaceChildren();
  } else {
    const segs = Math.max(0, Math.min(10, Math.round(c * 10)));
    $("hero-words").textContent = signsWords(segs);
    bar.replaceChildren(...Array.from({ length: 10 }, (_, i) => h("i", { class: i < segs ? "on" : null })));
  }
}

// ---------------------------------------------------------------- D why

function callerQuotes(check) {
  return (check.evidence || []).filter((e) => e && e.quote && e.speaker !== "you");
}

function ruleText(state, id) {
  const r = state.rules.find((x) => x.id === id);
  return r && r.text ? r.text : String(id).replace(/_/g, " ");
}

function renderWhy(state, lv) {
  const c = state.check;
  const fallback = !!(c && c.source === "fallback");
  const show = state.ui.view === "panel" && !!c && (lv === "watch" || lv === "danger" || fallback);
  $("why").hidden = !show;
  if (!show) return;

  const reason = $("reason");
  reason.textContent = c.reason || "";
  reason.title = c.reason || "";
  reason.hidden = !c.reason;
  reason.classList.toggle("grey", fallback);

  // Pills: one per tactic; a pill opens the caller's words when there are any.
  const quotes = callerQuotes(c);
  const tactics = (c.tactics || []).filter((t, i, a) => a.indexOf(t) === i);
  if (state.ui.expanded && !tactics.includes(state.ui.expanded)) state.ui.expanded = null;
  $("pills").replaceChildren(
    ...tactics.map((t) => {
      if (!quotes.some((e) => e.tactic === t)) return h("span", { class: "pill", title: plainWords(t), text: shortWords(t) });
      const open = state.ui.expanded === t;
      return h("button", {
        class: "pill",
        type: "button",
        "data-key": `pill:${t}`,
        "aria-expanded": String(open),
        "aria-controls": "quote",
        "aria-label": plainWords(t),
        title: plainWords(t),
        text: shortWords(t),
        onclick: () => {
          state.ui.expanded = open ? null : t;
          rerender();
        },
      });
    }),
  );

  const qs = state.ui.expanded ? quotes.filter((e) => e.tactic === state.ui.expanded) : [];
  $("quote").hidden = qs.length === 0;
  $("quote").replaceChildren(
    ...(qs.length ? [h("small", { text: `${plainWords(state.ui.expanded)}. The caller said:` })] : []),
    ...qs.slice(0, 2).map((e) => h("div", {}, h("q", { text: String(e.quote).slice(0, 80) }))),
  );

  $("rules-broken").replaceChildren(
    ...(c.rules_broken || []).map((id) => h("li", {}, h("b", { text: "Firm rule: " }), ruleText(state, id))),
  );

  $("open-said").hidden = quotes.length === 0;
}

// ---------------------------------------------------------------- what to do

function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

/** Verify line (C12): only when the caller claims an organization. */
function verifyInfo(state) {
  const c = state.check;
  const org = c && c.claimed_identity;
  const v = org && state.verify && state.verify.org === org ? state.verify : null;
  const status = v ? v.status || (v.phone ? "ok" : "error") : null;
  let note = "";
  let phone = "";
  const w = state.verifyWait;
  const waited = !w || w.org !== org || Date.now() - w.since >= VERIFY_WAIT_MS;
  if (org && !v && !waited) note = `Checking ${org}'s public number…`;
  else if (v && status === "ok" && v.phone) phone = v.phone;
  else if (v && status === "offline") note = "Offline, search skipped. Use the number on file.";
  else if (v) note = "Couldn't find a public number, use the one on file.";
  return { phone, note, host: v ? hostOf(v.source_url) : "" };
}

function renderTodo(state, lv) {
  const c = state.check;
  const show = state.ui.view === "panel" && !!c && (lv === "watch" || lv === "danger");
  $("todo").hidden = !show;
  if (!show) return;

  const say = sayThis(c.tactics);
  $("say").hidden = !say;
  $("say-text").textContent = say || "";

  const vi = verifyInfo(state);
  $("num").hidden = !vi.phone;
  $("num-phone").textContent = vi.phone;
  $("num-src").textContent = `Public number${vi.host ? " · " + vi.host : ""}`;
  $("verify-note").hidden = !vi.note;
  $("verify-note").textContent = vi.note;

  $("next-step").textContent = c.next_step || "";
}

// ---------------------------------------------------------------- flagged lines ("See what they said")

function renderSaid(state) {
  const c = state.check;
  if (state.ui.view === "said" && !(c && state.inCall)) state.ui.view = "panel";
  const show = state.ui.view === "said";
  $("said-view").hidden = !show;
  if (!show) return;

  // One row per distinct quote, in evidence order.
  const byQuote = new Map();
  for (const e of callerQuotes(c)) {
    if (!byQuote.has(e.quote)) byQuote.set(e.quote, []);
    byQuote.get(e.quote).push(e.tactic);
  }
  const broken = new Set(c.rules_broken || []);
  const rows = [...byQuote].map(([quote, tactics]) => {
    // Show the whole line around the quote while it is still in the last 3 lines.
    const line = state.tail.find((t) => t.speaker === "caller" && t.text.includes(quote));
    const text = line ? line.text : quote;
    const at = text.indexOf(quote);
    const p = h("p", {}, text.slice(0, at), h("mark", { text: quote }), text.slice(at + quote.length));
    const rules = state.rules.filter((r) => broken.has(r.id) && (r.tactics || []).some((t) => tactics.includes(t)));
    const tags = h(
      "div",
      { class: "tags" },
      ...tactics.map((t) => h("span", { text: shortWords(t), title: plainWords(t) })),
      ...rules.map((r) => h("span", { class: "r", text: `Breaks: ${r.text}` })),
    );
    return h("li", {}, h("span", { class: "who", text: "Caller" }), h("div", {}, p, tags));
  });
  $("flagged").replaceChildren(...rows);
}

// ---------------------------------------------------------------- E latest lines

function tailItems(state) {
  return state.tail.map((t) => {
    const you = t.speaker === "you";
    return h("li", {}, h("span", { class: you ? "who you" : "who", text: you ? "You" : "Caller" }), h("span", { class: "line", text: t.text }));
  });
}

function renderTail(state, lv) {
  $("tail").replaceChildren(...tailItems(state));
  $("said-latest").replaceChildren(...tailItems(state));
  $("said-latest-h").hidden = state.tail.length === 0;
  // At watch and danger the Why / What to do sections take this space.
  const quiet = lv === "low" || (lv !== "idle" && $("why").hidden);
  $("latest").hidden = !state.inCall || state.tail.length === 0 || state.ui.view !== "panel" || !quiet;
  $("end-call").hidden = !state.inCall;
}

/** Call content leaves the DOM, not just the screen (UI-7, F9). */
function clearCallDom() {
  for (const id of ["pills", "quote", "rules-broken", "flagged", "ov-tactics", "ov-rules"]) $(id).replaceChildren();
  for (const id of ["reason", "say-text", "num-phone", "num-src", "verify-note", "next-step", "ov-claim", "ov-verify", "ov-say-text", "ov-next"]) $(id).textContent = "";
  $("reason").removeAttribute("title");
}

// ---------------------------------------------------------------- F what left this device (T5)

// An entry "left" the device only if a request actually went out. Offline and
// refused lookups are recorded too, but nothing was sent.
const SENT = new Set(["ok", "error"]);

// Status pill: word + colour (colour is never alone).
const EGRESS_STATUS = {
  ok: { word: "Sent", cls: "ok" },
  error: { word: "Sent, no answer", cls: "err" },
  offline: { word: "Offline, not sent", cls: "off" },
  refused: { word: "Blocked", cls: "off" },
};

export function sentCount(state) {
  return state.egress.filter((e) => SENT.has(e.status)).length;
}

/** One line for small spaces (the footer, and T6's overlay foot). */
export function egressSummary(state) {
  const sent = state.egress.filter((e) => SENT.has(e.status));
  if (sent.length === 0) return "Nothing has left this device";
  if (sent.length === 1) return `1 item left: “${sent[0].sent}”`;
  return `${sent.length} items left this device`;
}

/** "19:02:11" from "2026-11-07T19:02:11" (the Server's local time). */
function clock(time) {
  const m = /T(\d{2}:\d{2}:\d{2})/.exec(String(time || ""));
  return m ? m[1] : "";
}

function egressDetail(e) {
  if (e.status === "refused") return "Blocked: lookup skipped to protect your privacy. Nothing was sent.";
  if (e.status === "offline") return `Nothing was sent: this laptop was offline. The lookup would have sent only “${e.sent}”.`;
  return `Only this text was sent: “${e.sent}”. Nothing from the call itself. Your call audio and words never leave this laptop.`;
}

function egressRow(state, e) {
  const st = EGRESS_STATUS[e.status] || { word: String(e.status || "unknown"), cls: "off" };
  const open = state.ui.egressEntry === e.seq;
  const what = e.status === "refused" || !e.sent ? h("span", { class: "what blocked", text: "Blocked: lookup skipped to protect your privacy" }) : h("q", { class: "what", text: e.sent });
  const id = `eg-d-${e.seq}`;
  return h(
    "li",
    {},
    h(
      "button",
      {
        class: "eg-row",
        type: "button",
        "data-key": `eg:${e.seq}`,
        "aria-expanded": String(open),
        "aria-controls": id,
        onclick: () => {
          state.ui.egressEntry = open ? null : e.seq;
          rerender();
        },
      },
      h("span", { class: "meta" }, h("time", { text: clock(e.time) }), h("span", { class: "host", text: e.destination || "" }), h("span", { class: `st ${st.cls}`, text: st.word })),
      what,
    ),
    h("p", { class: "eg-detail", id, hidden: !open, text: egressDetail(e) }),
  );
}

let lastEgress = 0;
let flashTimer = 0;
const reducedMotion = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

function renderPrivacy(state) {
  const n = sentCount(state);
  const skipped = state.egress.length - n;
  $("priv-ic").classList.toggle("ok", n === 0);
  $("priv-icon").setAttribute("href", n === 0 ? "#i-low" : "#i-up");
  $("priv-text").textContent = egressSummary(state);
  $("priv-skipped").textContent = skipped ? `${skipped} skipped` : "";

  const open = state.ui.egressOpen;
  $("priv-btn").setAttribute("aria-expanded", String(open));
  $("egress").hidden = !open;
  $("egress-n").textContent = String(state.egress.length);
  $("egress-empty").hidden = state.egress.length > 0;

  // Newest first; this call's entries, then "Earlier today" (org names only, kept for the session).
  const isNow = (e) => state.inCall && e.call === state.calls;
  const now = state.egress.filter(isNow);
  const earlier = state.egress.filter((e) => !isNow(e));
  const groups = [];
  if (now.length) groups.push(["This call", now]);
  if (earlier.length) groups.push(["Earlier today", earlier]);
  $("egress-list").replaceChildren(
    ...(open ? groups : []).flatMap(([label, list]) => [h("h3", { text: label }), h("ol", { class: "eg-list" }, ...list.map((e) => egressRow(state, e)))]),
  );

  // One flash of the header when an entry arrives (skipped under reduced motion).
  if (state.egress.length > lastEgress && !reducedMotion()) {
    const row = $("priv-row");
    row.classList.remove("flash");
    void row.offsetWidth; // restart the animation
    row.classList.add("flash");
    clearTimeout(flashTimer);
    flashTimer = setTimeout(() => row.classList.remove("flash"), 300);
  }
  lastEgress = state.egress.length;
}

// ---------------------------------------------------------------- danger overlay (T6 / UI-4)

let lastOpens = 0;
let audio = null;

/** One short tone, generated here (no audio files). Once per overlay open. */
function tone() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
    if (!Ctx) return;
    audio = audio || new Ctx();
    if (audio.state === "suspended") audio.resume();
    const t = audio.currentTime;
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(880, t);
    osc.frequency.setValueAtTime(660, t + 0.16);
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.18, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.38);
    osc.connect(gain).connect(audio.destination);
    osc.start(t);
    osc.stop(t + 0.4);
  } catch {
    // No sound is fine: the overlay and the red panel still show.
  }
}

function focusables() {
  return [...$("overlay").querySelectorAll("button, [href], input, [tabindex]:not([tabindex='-1'])")].filter((el) => !el.disabled && el.offsetParent !== null);
}

/** Esc never closes; Enter never takes an exit (only click or Space); Tab stays inside. */
function overlayKeys(e) {
  if (e.key === "Escape") {
    e.preventDefault();
    return;
  }
  if (e.key === "Enter" && (e.target === $("overlay") || e.target.closest("[data-exit]") || !e.target.closest("button, input, [href]"))) {
    e.preventDefault();
    return;
  }
  if (e.key !== "Tab") return;
  const els = focusables();
  if (!els.length) return e.preventDefault();
  const first = els[0];
  const last = els[els.length - 1];
  if (e.shiftKey && (document.activeElement === first || document.activeElement === $("overlay"))) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
}

function renderOverlay(state, lv) {
  const o = state.overlay;
  const open = !!(o && o.open && state.inCall && state.check && lv === "danger");
  const wasOpen = !$("overlay").hidden;
  $("overlay").hidden = !open;
  $("panel").inert = open;
  $("actions").hidden = !(lv === "danger" && !open && state.inCall);
  $("show-warning").hidden = $("actions").hidden;
  if (!o || o.opens < lastOpens) lastOpens = 0; // new call
  if (!open) return;

  const c = state.check;
  const conf = typeof c.confidence === "number" ? c.confidence : null;
  const segs = conf == null ? null : Math.max(0, Math.min(10, Math.round(conf * 10)));
  $("ov-words").textContent = segs == null ? "Strong signs" : signsWords(segs);
  $("ov-bar").replaceChildren(...(segs == null ? [] : Array.from({ length: 10 }, (_, i) => h("i", { class: i < segs ? "on" : null }))));

  $("ov-claim").hidden = !c.claimed_identity;
  $("ov-claim").replaceChildren(...(c.claimed_identity ? ["The caller claims to be: ", h("b", { text: c.claimed_identity })] : []));

  const quotes = callerQuotes(c);
  const tactics = (c.tactics || []).filter((t, i, a) => a.indexOf(t) === i);
  $("ov-tactics").replaceChildren(
    ...tactics.map((t) => {
      const q = quotes.find((e) => e.tactic === t);
      return h("li", {}, h("span", { class: "t", text: plainWords(t) }), q ? h("q", { text: String(q.quote).slice(0, 80) }) : null);
    }),
  );
  $("ov-rules").replaceChildren(...(c.rules_broken || []).map((id) => h("li", {}, h("b", { text: "Firm rule: " }), ruleText(state, id))));

  const vi = verifyInfo(state);
  const verify = vi.phone ? `Real public number: ${vi.phone}${vi.host ? " · source: " + vi.host : ""}` : vi.note;
  $("ov-verify").hidden = !verify;
  $("ov-verify").textContent = verify;
  $("ov-verify").classList.toggle("has-num", !!vi.phone);

  const say = sayThis(c.tactics);
  $("ov-say").hidden = !say;
  $("ov-say-text").textContent = say || "";
  $("ov-next").textContent = c.next_step || "Hang up and call back on a number you already have.";

  // One-line egress summary at the foot (T5 item 5): the privacy proof stays visible.
  $("ov-egress").replaceChildren(privIcon(sentCount(state) === 0), egressSummary(state));

  if (o.opens > lastOpens) {
    lastOpens = o.opens;
    tone();
    $("ov-hangup").focus();
  } else if (!wasOpen) {
    $("ov-hangup").focus();
  }
}

function privIcon(ok) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("width", "14");
  svg.setAttribute("height", "14");
  svg.setAttribute("aria-hidden", "true");
  if (ok) svg.setAttribute("class", "ok");
  const use = document.createElementNS(NS, "use");
  use.setAttribute("href", ok ? "#i-low" : "#i-up");
  svg.append(use);
  return svg;
}
