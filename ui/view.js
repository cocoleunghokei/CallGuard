// Draws `state` (see app.js) into ui/index.html. No state of its own except
// what the DOM holds. Never logs, never stores.

const $ = (id) => document.getElementById(id);

// Level: colour + icon + one word (colour is never alone).
const LEVELS = {
  idle: { icon: "#i-idle", word: "Not on a call", sub: "Callguard starts when a call does." },
  low: { icon: "#i-low", word: "Low", sub: "No clear signs" },
  watch: { icon: "#i-watch", word: "Watch", sub: "Some signs" },
  danger: { icon: "#i-danger", word: "Danger", sub: "Strong signs" },
};

export function level(state) {
  if (!state.inCall) return "idle";
  const r = state.check && state.check.risk;
  return LEVELS[r] ? r : "low";
}

/** One-time wiring for controls that only change local UI state. */
export function bindView(state, rerender) {
  $("consent-x").addEventListener("click", () => {
    state.consentDismissed = true;
    rerender();
  });
}

export function render(state) {
  renderHeader(state);
  renderBanners(state);
  renderHero(state);
  renderTail(state);
  renderPrivacy(state);
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

function renderHero(state) {
  const lv = level(state);
  const L = LEVELS[lv];
  const hero = $("hero");
  hero.className = `hero lv-${lv}`;
  $("hero-icon").setAttribute("href", L.icon);
  $("hero-word").textContent = L.word;
  $("hero-sub").textContent = L.sub;
}

// ---------------------------------------------------------------- E latest lines

function renderTail(state) {
  const list = $("tail");
  list.replaceChildren(
    ...state.tail.map((t) => {
      const li = document.createElement("li");
      const who = document.createElement("span");
      who.className = "who";
      who.textContent = t.speaker === "you" ? "You" : "Caller";
      const text = document.createElement("span");
      text.textContent = t.text;
      li.append(who, text);
      return li;
    }),
  );
  $("latest").hidden = !state.inCall || state.tail.length === 0;
}

// ---------------------------------------------------------------- F privacy line

// An entry "left" the device only if a request actually went out. Offline and
// refused lookups are recorded too, but nothing was sent.
const SENT = new Set(["ok", "error"]);

function renderPrivacy(state) {
  const n = state.egress.filter((e) => SENT.has(e.status)).length;
  const skipped = state.egress.length - n;
  $("priv-ic").classList.toggle("ok", n === 0);
  $("priv-icon").setAttribute("href", n === 0 ? "#i-low" : "#i-up");
  $("priv-text").textContent = n === 0 ? "Nothing has left this device" : `${n} ${n === 1 ? "item" : "items"} left this device`;
  $("priv-skipped").textContent = skipped ? `${skipped} skipped` : "";
}
