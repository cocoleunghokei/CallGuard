// Draws `state` (see app.js) into ui/index.html. Never logs, never stores.
// The UI follows `check` exactly as sent: no smoothing of its own (Server C10).

import { plainWords, shortWords, sayThis, signsWords, HEADS_UP, callKind, OUTCOME } from "./copy.js";
import { send } from "./ws.js";

/** How long the verify line says "Checking…" before it gives up and hides. */
export const VERIFY_WAIT_MS = 5000;

const NEXT_STEP_FALLBACK = "Verify first: hang up and call back on a number you already have.";

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
  if (state.markedSafe) return "low";
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
  bindExits(state);
  bindSideButtons(state);
  bindTabs(state);
  $("ov-full").addEventListener("click", () => {
    state.ui.ovFull = !state.ui.ovFull;
    rerender();
  });
  bindSummary(state);
  $("show-warning").addEventListener("click", () => {
    state.overlay.open = true; // not a new open: no tone
    rerender();
    $("ov-colleague").focus();
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
  renderTail(state);
  renderPrivacy(state);
  renderOverlay(state, lv);
  renderActions(state, lv);
  renderFirmRules(state);
  renderSummary(state);
  renderTabs(state, lv);
  renderContacts(state);

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
  $("badge-text").textContent = listening ? "Listening" : "Not listening";

  // Online is the normal case, so only "Offline" is shown (search is skipped then).
  const online = !s || s.online !== false; // unknown counts as online until told
  $("net").classList.toggle("off", !online);
  $("net").hidden = online;

  $("consent").hidden = state.consentDismissed;
}

// ---------------------------------------------------------------- B banners

function renderBanners(state) {
  $("b-conn").hidden = state.connected;
  // No banner for a degraded model (Coco, Sat): the check's own reason says "Basic checks only".
  // Live mode: the Server says when the mic or BlackHole input isn't working (AUD-9).
  const audioBad = !!(state.connected && state.status && state.status.audio_ok === false);
  $("b-audio").hidden = !audioBad;
  $("b-audio").textContent = audioBad ? state.status.audio_message || "CallGuard can't hear the call. Check the audio inputs." : "";
}

// ---------------------------------------------------------------- C status hero

function renderHero(state, lv) {
  const L = LEVELS[lv];
  $("hero").className = `hero lv-${lv}`;
  $("hero").hidden = state.ui.view === "said";
  $("hero-icon").setAttribute("href", L.icon);
  $("hero-word").textContent = L.word;

  // Words only, no signs bar (Coco, Sat).
  const c = state.check && typeof state.check.confidence === "number" ? state.check.confidence : null;
  if (lv === "idle") $("hero-words").textContent = "";
  else if (state.markedSafe) $("hero-words").textContent = "Marked safe";
  else if (c == null) $("hero-words").textContent = DEFAULT_SIGNS[lv];
  else $("hero-words").textContent = signsWords(Math.max(0, Math.min(10, Math.round(c * 10))));
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
  $("why").hidden = !(state.inCall && state.ui.view === "panel");
  const show = !!c && (lv === "watch" || lv === "danger" || fallback);
  $("why-none").hidden = show;
  for (const id of ["reason", "pills", "quote", "rules-broken"]) if (!show) $(id).hidden = true;
  if (!show) {
    $("pills").replaceChildren();
    $("rules-broken").replaceChildren();
    return;
  }
  $("pills").hidden = false;
  $("rules-broken").hidden = false;

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
}

// ---------------------------------------------------------------- what to do

function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "Callers posing as … · ftc.gov, Oct 2026" from verify.report, or "". */
function reportLine(state) {
  const c = state.check;
  const v = state.verify;
  const r = v && v.report;
  if (!r || !r.summary || !c || v.org !== c.claimed_identity || v.status === "offline") return "";
  const host = hostOf(r.source_url || v.source_url);
  const m = /^(\d{4})-(\d{2})/.exec(String(r.date || ""));
  const when = m && MONTHS[Number(m[2]) - 1] ? `${MONTHS[Number(m[2]) - 1]} ${m[1]}` : "";
  const tail = [host, when].filter(Boolean).join(", ");
  return String(r.summary).slice(0, 140) + (tail ? ` · ${tail}` : "");
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
  $("todo").hidden = !(state.inCall && state.ui.view === "panel");
  const show = !!c && (lv === "watch" || lv === "danger");

  const say = show ? sayThis(c.tactics) : "";
  $("say-text").hidden = !say;
  $("say-text").textContent = say || "";
  $("say-none").hidden = !!say;
  if (!show) {
    $("num").hidden = true;
    $("verify-note").hidden = true;
    $("next-step").textContent = ""; // nothing to do yet: empty, its space stays reserved
    return;
  }

  const vi = verifyInfo(state);
  $("num").hidden = !vi.phone;
  $("num-phone").textContent = vi.phone;
  $("num-src").textContent = `Public number${vi.host ? " · " + vi.host : ""}`;
  $("verify-note").hidden = !vi.note;
  $("verify-note").textContent = vi.note;

  // Every warning ends with a concrete next step (prd 9.3), even if the model sent none.
  $("next-step").textContent = c.next_step || NEXT_STEP_FALLBACK;
}

// ---------------------------------------------------------------- flagged lines ("See what they said")

function markedLine(text, quotes) {
  const q = quotes.find((x) => text.includes(x));
  if (!q) return h("span", { class: "line", text });
  const at = text.indexOf(q);
  return h("span", { class: "line" }, text.slice(0, at), h("mark", { text: q }), text.slice(at + q.length));
}

function renderSaid(state) {
  const c = state.check;
  if (state.ui.view === "said" && !state.inCall) state.ui.view = "panel";
  const show = state.ui.view === "said";
  $("said-view").hidden = !show;
  if (!show) return;

  // Flagged: one row per distinct caller quote, in evidence order.
  const byQuote = new Map();
  for (const e of c ? callerQuotes(c) : []) {
    if (!byQuote.has(e.quote)) byQuote.set(e.quote, []);
    byQuote.get(e.quote).push(e.tactic);
  }
  const broken = new Set((c && c.rules_broken) || []);
  const rows = [...byQuote].map(([quote, tactics]) => {
    const line = state.transcript.find((t) => t.speaker === "caller" && t.text.includes(quote));
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
  $("flagged-h").hidden = rows.length === 0;
  $("flagged").replaceChildren(...rows);

  // Everything said this call, oldest first, caller quotes marked.
  const quotes = [...byQuote.keys()];
  $("said-latest").replaceChildren(
    ...state.transcript.map((t) => {
      const you = t.speaker === "you";
      return h("li", {}, h("span", { class: you ? "who you" : "who", text: you ? "You" : "Caller" }), you ? h("span", { class: "line", text: t.text }) : markedLine(t.text, quotes));
    }),
  );
}

// ---------------------------------------------------------------- E latest lines

function tailItems(state) {
  return state.tail.map((t) => {
    const you = t.speaker === "you";
    return h("li", {}, h("span", { class: you ? "who you" : "who", text: you ? "You" : "Caller" }), h("span", { class: "line", text: t.text }));
  });
}

function renderTail(state) {
  $("tail").replaceChildren(...tailItems(state));
  $("tail-empty").hidden = state.tail.length > 0;
  $("latest").hidden = !state.inCall || state.ui.view !== "panel";
  $("open-said").hidden = state.transcript.length === 0;
}

/** Call content leaves the DOM, not just the screen (UI-7, F9). */
function clearCallDom() {
  for (const id of ["ov-toast", "ov-report"]) $(id).textContent = "";
  $("safe-input").value = "";
  for (const id of ["pills", "quote", "rules-broken", "flagged", "said-latest", "tail", "ov-tactics", "ov-rules", "ov-tail"]) $(id).replaceChildren();
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
  if (sent.length === 0) return "Nothing sent online";
  if (sent.length === 1) return `1 search sent: “${sent[0].sent}”`;
  return `${sent.length} searches sent`;
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

/** Cover the panel below its header, not the sidebar or the "Listening" line. */
function placeOverlay() {
  const panel = $("panel").getBoundingClientRect();
  const top = document.querySelector(".top").getBoundingClientRect().bottom;
  const ov = $("overlay");
  ov.style.left = `${Math.max(0, panel.left)}px`;
  ov.style.width = `${panel.width}px`;
  ov.style.top = `${Math.max(0, top)}px`;
}
window.addEventListener("resize", () => {
  if (!$("overlay").hidden) placeOverlay();
});

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
  // Shown on the Call tab only; the sidebar and the header stay usable around it.
  const open = !!(o && o.open && state.inCall && state.check && lv === "danger" && state.tab === "call");
  const wasOpen = !$("overlay").hidden;
  $("overlay").hidden = !open;
  $("main").inert = open;
  $("priv").inert = open;
  $("show-warning").hidden = !(lv === "danger" && !open && state.inCall);
  if (open) placeOverlay();
  if (!o || o.opens < lastOpens) lastOpens = 0; // new call
  if (!open) return;

  const c = state.check;
  $("ov-h").textContent = "Scam detected";

  $("safe-hold").disabled = !isSafe();

  const vi = verifyInfo(state);
  // Latest lines: the same 3 as the call screen, or the whole call when expanded.
  const full = !!state.ui.ovFull;
  $("ov-full").setAttribute("aria-expanded", String(full));
  $("ov-full").textContent = full ? "Show less ‹" : "View full transcript ›";
  $("ov-full").hidden = state.transcript.length <= state.tail.length;
  $("ov-tail-box").classList.toggle("full", full);
  $("ov-tail").replaceChildren(
    ...(full ? state.transcript : state.tail).map((t) => {
      const you = t.speaker === "you";
      return h("li", {}, h("span", { class: you ? "who you" : "who", text: you ? "You" : "Caller" }), h("span", { class: "line", text: t.text }));
    }),
  );

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

  const verify = vi.phone ? `Real public number: ${vi.phone}${vi.host ? " · source: " + vi.host : ""}` : vi.note;
  $("ov-verify").hidden = !verify;
  $("ov-verify").textContent = verify;
  $("ov-verify").classList.toggle("has-num", !!vi.phone);

  // UI-16: a recent public report about people posing as this organization (verify.report, C17).
  // Hidden when absent, offline, or not about the org the caller claims now.
  const rep = reportLine(state);
  $("ov-report").hidden = !rep;
  $("ov-report").replaceChildren(...(rep ? [h("b", { text: "Reported: " }), rep] : []));

  const say = sayThis(c.tactics);
  $("ov-say").hidden = !say;
  $("ov-say-text").textContent = say || "";
  $("ov-next").textContent = c.next_step || NEXT_STEP_FALLBACK;

  // One-line egress summary at the foot (T5 item 5): the privacy proof stays visible.
  $("ov-egress").replaceChildren(privIcon(sentCount(state) === 0), egressSummary(state));

  const primary = $("ov-colleague");
  if (o.opens > lastOpens) {
    lastOpens = o.opens;
    tone();
    primary.focus({ preventScroll: true }); // keep the banner on screen
    $("overlay").scrollTop = 0;
  } else if (!wasOpen) {
    primary.focus({ preventScroll: true });
    $("overlay").scrollTop = 0;
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

// ---------------------------------------------------------------- exits (T7 / UI-5)

const HOLD_MS = 3000;
let hold = null; // {t0, raf}

function isSafe() {
  return $("safe-input").value.trim().toLowerCase() === "safe";
}

function toast(...lines) {
  showToast("ov-toast", lines);
}

const toastTimers = {};
function showToast(id, lines) {
  $(id).replaceChildren(...lines);
  $(id).hidden = false;
  clearTimeout(toastTimers[id]);
  toastTimers[id] = setTimeout(() => {
    $(id).hidden = true;
    $(id).replaceChildren();
  }, 12000);
}

function headsUpLines(copied) {
  return [
    h("b", { text: HEADS_UP.title }),
    h("q", { text: HEADS_UP.message }),
    h("small", { text: copied ? HEADS_UP.copied : HEADS_UP.notCopied }),
  ];
}

/** Copy fixed text to the clipboard; true when it worked. Falls back to
 *  execCommand for webviews without navigator.clipboard. Local only. */
async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const had = document.activeElement;
    const ta = h("textarea", { text });
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;opacity:0;pointer-events:none";
    document.body.append(ta);
    ta.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    ta.remove();
    had?.focus?.();
    return ok;
  }
}

function setHold(p) {
  $("safe-hold").style.setProperty("--p", String(p));
  $("safe-hold-text").textContent = p > 0 ? "Keep holding…" : "Hold 3 s";
}

function startHold(state) {
  if (hold || !isSafe()) return;
  const t0 = performance.now();
  hold = { t0, raf: 0 };
  const frame = (now) => {
    if (!hold) return;
    const p = Math.min(1, (now - t0) / HOLD_MS);
    setHold(p);
    if (now - t0 >= HOLD_MS) return finishHold(state);
    hold.raf = requestAnimationFrame(frame);
  };
  hold.raf = requestAnimationFrame(frame);
}

function stopHold() {
  if (!hold) return;
  cancelAnimationFrame(hold.raf);
  hold = null;
  setHold(0);
}

function finishHold(state) {
  hold = null;
  setHold(0);
  $("safe-input").value = "";
  send("mark_safe");
  send("gate_release", { how: "mark_safe" });
  state.callLog.outcome = "mark_safe";
  state.markedSafe = true;
  state.overlay.open = false;
  rerender();
}

function bindExits(state) {
  $("ov-colleague").addEventListener("click", async () => {
    const copying = copyText(HEADS_UP.message); // start inside the click, before any await
    send("colleague");
    send("gate_release", { how: "colleague" });
    state.callLog.outcome = "colleague";
    rerender();
    toast(...headsUpLines(await copying));
  });

  // "I've verified, it's safe": type SAFE, then hold 3 s. No single click or key does it.
  $("safe-input").addEventListener("input", () => {
    stopHold();
    $("safe-hold").disabled = !isSafe();
  });
  const btn = $("safe-hold");
  btn.addEventListener("pointerdown", (e) => {
    if (e.button !== 0) return;
    btn.setPointerCapture?.(e.pointerId);
    startHold(state);
  });
  for (const ev of ["pointerup", "pointercancel", "lostpointercapture", "blur"]) btn.addEventListener(ev, stopHold);
  btn.addEventListener("keydown", (e) => {
    if (e.key !== " ") return;
    e.preventDefault();
    if (!e.repeat) startHold(state);
  });
  btn.addEventListener("keyup", (e) => {
    if (e.key === " ") {
      e.preventDefault();
      stopHold();
    }
  });
}

// ---------------------------------------------------------------- side buttons at Watch (T10 / UI-9)

function bindSideButtons(state) {
  $("side-colleague").addEventListener("click", async () => {
    const copying = copyText(HEADS_UP.message);
    send("colleague"); // no pause outside danger, so no gate_release
    state.callLog.outcome = "colleague";
    showToast("panel-toast", headsUpLines(await copying));
  });
  $("side-safe").addEventListener("click", () => {
    // One click is enough here: there is no pause to get past (F10).
    send("mark_safe");
    state.callLog.outcome = "mark_safe";
    state.markedSafe = true;
    $("panel-toast").hidden = true;
    rerender();
    $("hero-word").scrollIntoView?.({ block: "nearest" });
  });
}

function renderActions(state, lv) {
  // Always on screen during a call, so the buttons never move; "Mark as safe" only means something at Watch.
  $("side-safe").disabled = !(state.inCall && (lv === "watch" || lv === "danger") && !state.markedSafe);
  if (!state.inCall) {
    $("panel-toast").hidden = true;
    $("panel-toast").replaceChildren();
  }
}

// ---------------------------------------------------------------- firm rules (T10 / UI-13)

function renderFirmRules(state) {
  const rules = state.rules || [];
  $("firm-rules-empty").hidden = rules.length > 0;
  $("firm-rules-h").textContent = `Your firm's rules (${rules.length})`;
  const hits = Object.values(state.ruleHits).filter(Boolean).length;
  $("firm-rules-hits").textContent = hits ? `${hits} came up this call` : "";
  $("firm-rules-list").replaceChildren(
    ...rules.map((r) => {
      const n = state.ruleHits[r.id] || 0;
      const off = r.enabled === false;
      return h(
        "li",
        { class: [n ? "hit" : "", off ? "off" : ""].filter(Boolean).join(" ") || null },
        h("span", { text: r.text || String(r.id).replace(/_/g, " ") }),
        n ? h("span", { class: "rule-badge", text: `came up ${n}×` }) : null,
        off ? h("span", { class: "rule-badge muted", text: "Off" }) : null,
      );
    }),
  );
  const src = state.rulesSource === "custom" ? "Set by your firm." : state.rulesSource === "default" ? "CallGuard's default rules." : "";
  $("firm-rules-src").textContent = src ? `${src} Kept on this laptop, never sent.` : "Kept on this laptop, never sent.";
}

// ---------------------------------------------------------------- sidebar tabs

const TABS = { call: "main", rules: "firm-rules", history: "history", contacts: "contacts" };

function renderTabs(state, lv) {
  for (const [tab, panel] of Object.entries(TABS)) {
    const on = state.tab === tab;
    const btn = $(`tab-${tab}`);
    btn.setAttribute("aria-selected", String(on));
    btn.tabIndex = on ? 0 : -1;
    $(panel).hidden = !on;
  }
  // Away from the call tab, a dot on it says the call needs a look.
  const dot = $("tab-call-dot");
  const alert = state.tab !== "call" && (lv === "watch" || lv === "danger");
  dot.hidden = !alert;
  dot.className = `tab-dot lv-dot-${lv}`;
  $("tab-call").setAttribute("aria-label", alert ? `Call, ${lv === "danger" ? "Scam detected" : "worth a second look"}` : "Call");
  const hits = Object.values(state.ruleHits).filter(Boolean).length;
  $("tab-rules-dot").hidden = !(hits && state.tab !== "rules");
}

function bindTabs(state) {
  const order = Object.keys(TABS);
  const pick = (tab) => {
    state.tab = tab;
    rerender();
  };
  for (const tab of order) {
    const btn = $(`tab-${tab}`);
    btn.addEventListener("click", () => pick(tab));
    btn.addEventListener("keydown", (e) => {
      const step = e.key === "ArrowDown" ? 1 : e.key === "ArrowUp" ? -1 : 0;
      if (!step) return;
      e.preventDefault();
      const next = order[(order.indexOf(tab) + step + order.length) % order.length];
      pick(next);
      $(`tab-${next}`).focus();
    });
  }
  $("contacts-list").addEventListener("click", (e) => contactAction(state, e));
  $("contacts-list").addEventListener("submit", (e) => {
    e.preventDefault();
    saveContactForm(state, e.target);
  });
}

// ---------------------------------------------------------------- emergency contacts

let contactsDrawn = null; // redraw only on change, so typing in the edit form survives other messages

function renderContacts(state) {
  const note = state.contactsNote;
  $("contacts-msg").hidden = !note;
  $("contacts-msg").textContent = note ? note.text : "";
  $("contacts-msg").classList.toggle("err", !!(note && !note.ok));
  const sig = JSON.stringify([state.contacts, state.editContact]);
  if (sig === contactsDrawn) return;
  contactsDrawn = sig;
  $("contacts-list").replaceChildren(
    ...state.contacts.map((c) => {
      if (state.editContact === c.id) {
        return h(
          "li",
          { class: "contact editing" },
          h(
            "form",
            { "data-id": c.id },
            h("small", { class: "role", text: c.role }),
            h("label", {}, h("span", { text: "Name" }), h("input", { name: "name", type: "text", value: c.name, autocomplete: "off", maxlength: "60" })),
            h("label", {}, h("span", { text: "Phone" }), h("input", { name: "phone", type: "tel", value: c.phone, autocomplete: "off", maxlength: "30" })),
            h(
              "div",
              { class: "c-btns" },
              h("button", { class: "pill-btn", type: "submit", text: "Save" }),
              h("button", { class: "pill-btn", type: "button", "data-act": "cancel", text: "Cancel" }),
            ),
          ),
        );
      }
      return h(
        "li",
        { class: "contact" },
        h(
          "div",
          { class: "c-main" },
          h("small", { class: "role", text: c.role }),
          h("b", { class: c.name ? null : "unset", text: c.name || "Not set yet" }),
          c.phone ? h("span", { class: "c-phone", text: c.phone }) : h("span", { class: "c-phone unset", text: "No number" }),
        ),
        h(
          "div",
          { class: "c-btns" },
          c.phone ? h("button", { class: "pill-btn", type: "button", "data-act": "copy", "data-id": c.id, text: "Copy" }) : null,
          h("button", { class: "pill-btn", type: "button", "data-act": "edit", "data-id": c.id, "aria-label": `Edit ${c.role}`, text: "Edit" }),
        ),
      );
    }),
  );
  if (state.editContact) {
    const first = $("contacts-list").querySelector("input");
    if (first) first.focus();
  }
}

async function contactAction(state, e) {
  const btn = e.target.closest("button[data-act]");
  if (!btn) return;
  const act = btn.dataset.act;
  if (act === "edit") {
    state.editContact = btn.dataset.id;
  } else if (act === "cancel") {
    state.editContact = null;
  } else if (act === "copy") {
    const c = state.contacts.find((x) => x.id === btn.dataset.id);
    try {
      await navigator.clipboard.writeText(c.phone);
      btn.textContent = "Copied";
    } catch {
      btn.textContent = "Copy failed";
    }
    setTimeout(() => (btn.textContent = "Copy"), 1500);
    return;
  }
  rerender();
}

function saveContactForm(state, form) {
  const id = form.dataset.id;
  const name = form.elements.name.value.trim();
  const phone = form.elements.phone.value.trim();
  state.contacts = state.contacts.map((c) => (c.id === id ? { ...c, name, phone } : c));
  state.editContact = null;
  // The Server checks and saves them to one local file, then answers `contacts_saved`.
  state.contactsNote = send("save_contacts", { data: state.contacts })
    ? null
    : { ok: false, text: "Not connected, so not saved. Your change lasts until you close CallGuard." };
  rerender();
  const edit = $("contacts-list").querySelector(`button[data-act="edit"][data-id="${CSS.escape(id)}"]`);
  if (edit) edit.focus();
}

// ---------------------------------------------------------------- after-call summary (T11 / UI-10)

function signsCount(n) {
  return `${n} warning sign${n === 1 ? "" : "s"}`;
}

/** Plain text for "Copy summary". Same content as the card: no names, numbers or quotes. */
export function summaryText(sum) {
  const parts = [`CallGuard call summary: ${callKind(sum.tactics)}.`, `Reached ${sum.peak === "danger" ? "Danger" : "Watch"}, ${signsCount(sum.tactics.length)}: ${sum.tactics.map(plainWords).join("; ")}.`];
  if (sum.outcome) parts.push(`Then ${OUTCOME[sum.outcome]}.`);
  if (sum.rules.length) parts.push(`Firm rules that came up: ${sum.rules.join(" ")}`);
  parts.push("Nothing the caller said was kept.");
  return parts.join(" ");
}

function bindSummary(state) {
  $("history-list").addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-act]");
    if (!btn) return;
    const id = btn.dataset.id;
    const sum = state.history.find((x) => x.id === id);
    if (!sum) return;
    if (btn.dataset.act === "remove") {
      state.history = state.history.filter((x) => x.id !== id); // gone from memory, not just hidden
      rerender();
      return;
    }
    try {
      await navigator.clipboard.writeText(summaryText(sum));
      btn.textContent = "Copied";
    } catch {
      btn.textContent = "Copy failed";
    }
    setTimeout(() => (btn.textContent = "Copy summary"), 1500);
  });
}

let historyDrawn = null; // redraw only on change, so a "Copied" label isn't wiped by other messages

function renderSummary(state) {
  if (state.tab === "history") state.historyUnseen = false;
  $("tab-history-dot").hidden = !state.historyUnseen;
  $("history-empty").hidden = state.history.length > 0;
  const sig = state.history.map((x) => x.id).join(",");
  if (sig === historyDrawn) return;
  historyDrawn = sig;
  $("history-list").replaceChildren(
    ...state.history.map((sum) => {
      const level = sum.peak === "danger" ? "Reached Danger" : "Reached Watch";
      return h(
        "li",
        { class: `sum-card lv-sum-${sum.peak}` },
        h("p", { class: "sum-time", text: `Call ended ${sum.ended}` }),
        h("p", { class: "sum-kind", text: callKind(sum.tactics) }),
        h("p", { class: "sum-line", text: [level, signsCount(sum.tactics.length), sum.outcome ? OUTCOME[sum.outcome] : null].filter(Boolean).join(" · ") }),
        sum.tactics.length ? h("div", { class: "pills" }, ...sum.tactics.map((t) => h("span", { class: "pill", title: plainWords(t), text: shortWords(t) }))) : null,
        sum.rules.length ? h("ul", { class: "rules" }, ...sum.rules.map((text) => h("li", {}, h("b", { text: "Firm rule: " }), text))) : null,
        h(
          "div",
          { class: "sum-btns" },
          h("button", { class: "pill-btn", type: "button", "data-act": "copy", "data-id": sum.id, text: "Copy summary" }),
          h("button", { class: "pill-btn", type: "button", "data-act": "remove", "data-id": sum.id, text: "Remove" }),
        ),
      );
    }),
  );
}
