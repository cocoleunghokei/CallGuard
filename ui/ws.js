// Connection to the CallGuard Server. One job: deliver {type, data} to onMessage.
//
//   ?ws=fake            use the replay harness's FakeSocket (ui/dev/fake_socket.js)
//   ?ws=ws://host/ws    connect somewhere else
//   (none)              ws://localhost:8000/ws
//
// Privacy: never log message contents here. Transcript text must not reach console.

const DEFAULT_URL = "ws://localhost:8000/ws";
const RECONNECT_MS = 2000;

let socket = null;

/** Send a UI -> Server message, e.g. send("gate_release", {how: "hang_up"}). */
export function send(type, extra = {}) {
  if (!socket || socket.readyState !== 1) return false;
  socket.send(JSON.stringify({ type, ...extra }));
  return true;
}

/**
 * Connect and keep reconnecting every 2 s.
 * onMessage({type, data}) gets every Server message.
 * onState(open: boolean) is called when the connection opens or closes.
 */
export async function connect(onMessage, onState = () => {}) {
  const param = new URLSearchParams(location.search).get("ws");
  let Socket = WebSocket;
  let url = DEFAULT_URL;
  if (param === "fake") {
    ({ FakeSocket: Socket } = await import("./dev/fake_socket.js"));
    url = "fake://replay";
  } else if (param) {
    url = param;
  }

  const open = () => {
    socket = new Socket(url);
    socket.onopen = () => onState(true);
    socket.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return; // ignore garbage, never crash
      }
      // `source` is the optional top-level field on `rules` (default | custom).
      if (msg && typeof msg.type === "string") onMessage({ type: msg.type, data: msg.data, source: msg.source });
    };
    socket.onclose = () => {
      socket = null;
      onState(false);
      setTimeout(open, RECONNECT_MS);
    };
    socket.onerror = () => {}; // onclose follows
  };
  open();
}
