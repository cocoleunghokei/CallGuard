// Replay harness: plays ui/dev/fixtures/*.json into ui/index.html?ws=fake.
// The iframe's FakeSocket finds `window.callguardReplay` (this page) and
// attaches itself; we deliver fixture messages to it on a virtual clock.

// Keep in sync with ui/dev/fixtures/ (tests/ui/test_fixtures.py checks it).
export const FIXTURES = [
  "idle",
  "s1_government",
  "s1_report",
  "s2_vendor_bank",
  "s3_it_code",
  "s4_partner_wire",
  "b1_vendor_invoice",
  "b2_colleague",
  "b3_real_bank",
  "b7_you_say_it",
  "offline",
  "model_down",
];

// What the Scenario picker shows. The ids above stay the file names; people see these.
export const GROUPS = [
  { label: "Scam calls", ids: ["s1_government", "s1_report", "s2_vendor_bank", "s3_it_code", "s4_partner_wire"] },
  { label: "Normal calls (CallGuard should stay calm)", ids: ["b1_vendor_invoice", "b2_colleague", "b3_real_bank", "b7_you_say_it"] },
  { label: "When things go wrong", ids: ["offline", "model_down"] },
  { label: "No call", ids: ["idle"] },
];
export const LABELS = {
  idle: "App open, no call yet",
  s1_government: "Fake government official",
  s1_report: "Fake official + recent scam report",
  s2_vendor_bank: "Vendor asks to change bank details",
  s3_it_code: "Fake IT asks for a login code",
  s4_partner_wire: "“Partner” pushes an urgent wire",
  b1_vendor_invoice: "Real vendor invoice question",
  b2_colleague: "Colleague with a deadline",
  b3_real_bank: "Real bank calling back",
  b7_you_say_it: "You say the scary words",
  offline: "Wi-Fi off",
  model_down: "AI model not running",
};

const TICK_MS = 50;
const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);

// Recording mode (T9 backup video): ?clean=1 hides the dev controls; f= takes a
// comma list played back to back with a title card between; exit=colleague
// clicks that exit `exit_after` seconds after the pause locks (hands-free take).
const CLEAN = params.get("clean") === "1";
const PLAYLIST = (params.get("f") || "").split(",").filter((n) => FIXTURES.includes(n));
const GAP_S = Number(params.get("gap")) || 4;
const AUTO_EXIT = { colleague: "ov-colleague" }[params.get("exit")] || null;
const EXIT_AFTER_S = Number(params.get("exit_after")) || 4;
const CARDS = {
  s1_government: "A call from “the Department of Justice”",
  offline: "Wi-Fi off. Same call again.",
};

const player = {
  fixture: null, // {id, description, steps}
  next: 0, // index of the next step to deliver
  clock: 0, // virtual seconds since start
  playing: params.get("autoplay") !== "0",
  speed: Number(params.get("speed")) || 1,
  socket: null, // the iframe's FakeSocket while connected
};

// ---------------------------------------------------------------- hub used by FakeSocket

window.callguardReplay = {
  attach(sock) {
    player.socket = sock;
    logSys("socket connected");
  },
  detach(sock) {
    if (player.socket === sock) player.socket = null;
    logSys("socket closed");
  },
  received(msg) {
    const extra = Object.entries(msg)
      .filter(([k]) => k !== "type")
      .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
      .join(" ");
    addLine($("sent"), `${stamp()} ${msg.type}${extra ? " " + extra : ""}`);
    $("sent-n").textContent = String($("sent").children.length);
  },
};

// ---------------------------------------------------------------- playback

function deliverNext() {
  const step = player.fixture.steps[player.next++];
  const ok = player.socket ? player.socket.deliver(step.msg) : false;
  if (AUTO_EXIT && ok && step.msg.type === "gate" && step.msg.data && step.msg.data.state === "locked") {
    setTimeout(() => {
      const doc = $("ui").contentDocument;
      const btn = doc && doc.getElementById(AUTO_EXIT);
      if (btn && !btn.closest("[hidden]")) btn.click();
    }, EXIT_AFTER_S * 1000);
  }
  addLine($("fed"), `${step.at.toFixed(1).padStart(5)}  ${summary(step.msg)}`, ok ? "" : "drop");
  $("fed-n").textContent = `${player.next}/${player.fixture.steps.length}`;
}

function tick() {
  if (!player.fixture || !player.socket) return render();
  if (player.playing) player.clock += (TICK_MS / 1000) * player.speed;
  const steps = player.fixture.steps;
  while (player.next < steps.length && steps[player.next].at <= player.clock) deliverNext();
  if (player.next >= steps.length && player.playing) {
    player.playing = false;
    logSys("end of fixture");
    playNextInList();
  }
  render();
}

function step() {
  const steps = player.fixture && player.fixture.steps;
  if (!steps || player.next >= steps.length || !player.socket) return;
  player.playing = false;
  player.clock = steps[player.next].at;
  // deliver everything scheduled at the same instant
  while (player.next < steps.length && steps[player.next].at <= player.clock) deliverNext();
  render();
}

async function load(name) {
  const res = await fetch(`fixtures/${name}.json`, { cache: "no-store" });
  player.fixture = await res.json();
  $("desc").textContent = player.fixture.description || "";
  restart();
}

function restart() {
  if (CLEAN && player.fixture) {
    card(CARDS[player.fixture.id]);
    setTimeout(() => card(""), 3000);
  }
  player.next = 0;
  player.clock = 0;
  player.socket = null;
  player.playing = params.get("autoplay") !== "0";
  $("fed").replaceChildren();
  $("sent").replaceChildren();
  $("fed-n").textContent = "";
  $("sent-n").textContent = "";
  // A fresh page load, so the UI starts from a clean state.
  $("ui").src = `../index.html?ws=fake&r=${Date.now()}`;
  render();
}

// ---------------------------------------------------------------- playlist (recording mode)

function card(text) {
  const el = $("card");
  el.textContent = text || "";
  el.hidden = !text;
}

function playNextInList() {
  const i = PLAYLIST.indexOf(player.fixture && player.fixture.id);
  const next = PLAYLIST[i + 1];
  if (i < 0 || !next) return;
  setTimeout(() => {
    $("fixture").value = next;
    load(next);
  }, GAP_S * 1000);
}

// ---------------------------------------------------------------- view

function render() {
  const steps = player.fixture ? player.fixture.steps : [];
  const end = steps.length ? steps[steps.length - 1].at : 0;
  $("play").textContent = player.playing ? "Pause" : "Play";
  $("play").disabled = !player.fixture || player.next >= steps.length;
  $("step").disabled = $("play").disabled;
  $("clock").textContent = `${player.clock.toFixed(1)} s / ${end.toFixed(1)} s` + (player.socket ? "" : " · waiting for socket");
  document.querySelectorAll("[data-speed]").forEach((b) => {
    b.setAttribute("aria-pressed", String(Number(b.dataset.speed) === player.speed));
  });
}

function summary(msg) {
  const d = msg.data || {};
  switch (msg.type) {
    case "transcript":
      return `transcript ${d.speaker}: ${String(d.text || "").slice(-80)}`;
    case "check":
      return `check ${d.risk}${d.confidence != null ? " " + d.confidence.toFixed(2) : ""} [${(d.tactics || []).join(", ")}]${d.source && d.source !== "model" ? " (" + d.source + ")" : ""}`;
    case "verify":
      return `verify ${d.org} ${d.phone || d.status || ""}`;
    case "egress":
      return `egress ${d.status} ${d.destination} "${d.sent}"`;
    case "status":
      return `status ${JSON.stringify(d)}`;
    case "gate":
      return `gate ${d.state}${d.release_in ? " " + d.release_in + "s" : ""}`;
    case "call":
      return `call ${d.state}`;
    case "rules":
      return `rules ${Array.isArray(d) ? d.length : "?"}${msg.source ? " (" + msg.source + ")" : ""}`;
    default:
      return msg.type;
  }
}

function addLine(list, text, cls = "") {
  const li = document.createElement("li");
  li.textContent = text;
  li.title = text;
  if (cls) li.className = cls;
  list.appendChild(li);
  list.scrollTop = list.scrollHeight;
}

function logSys(text) {
  addLine($("fed"), `${player.clock.toFixed(1).padStart(5)}  · ${text}`, "sys");
}

function stamp() {
  return player.clock.toFixed(1).padStart(5);
}

// ---------------------------------------------------------------- controls

function init() {
  const sel = $("fixture");
  for (const g of GROUPS) {
    const og = document.createElement("optgroup");
    og.label = g.label;
    for (const id of g.ids) og.appendChild(new Option(LABELS[id] || id, id));
    sel.appendChild(og);
  }
  if (CLEAN) document.body.classList.add("clean");
  const start = PLAYLIST[0] || "s1_government";
  sel.value = start;
  sel.onchange = () => load(sel.value);
  $("play").onclick = () => {
    player.playing = !player.playing;
    render();
  };
  $("step").onclick = step;
  $("restart").onclick = restart;
  $("drop").onclick = () => player.socket && player.socket.close();
  document.querySelectorAll("[data-speed]").forEach((b) => {
    b.onclick = () => {
      player.speed = Number(b.dataset.speed);
      render();
    };
  });
  setInterval(tick, TICK_MS);
  load(start);
}

init();
