// FakeSocket: a WebSocket stand-in for the replay harness (ui/dev/replay.html).
// ui/ws.js loads it when the page is opened with ?ws=fake.
//
// It speaks the same small API ws.js uses (readyState, onopen, onmessage,
// onclose, onerror, send, close). The replay page drives it through a hub on
// the parent window: window.parent.callguardReplay = {attach, detach, received}.
// Opened on its own (no harness), it just stays open and silent.

export class FakeSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  constructor(url) {
    this.url = url;
    this.readyState = FakeSocket.CONNECTING;
    this.onopen = null;
    this.onmessage = null;
    this.onclose = null;
    this.onerror = null;
    this._hub = findHub();
    setTimeout(() => {
      if (this.readyState !== FakeSocket.CONNECTING) return;
      this.readyState = FakeSocket.OPEN;
      if (this.onopen) this.onopen({ type: "open" });
      if (this._hub) this._hub.attach(this);
    }, 0);
  }

  /** UI -> Server. The harness logs it. */
  send(text) {
    if (this.readyState !== FakeSocket.OPEN) throw new Error("FakeSocket is not open");
    if (this._hub) this._hub.received(JSON.parse(text));
  }

  close() {
    if (this.readyState === FakeSocket.CLOSED) return;
    this.readyState = FakeSocket.CLOSED;
    if (this._hub) this._hub.detach(this);
    if (this.onclose) this.onclose({ type: "close", code: 1000 });
  }

  /** Server -> UI. Called by the harness only. */
  deliver(msg) {
    if (this.readyState !== FakeSocket.OPEN) return false;
    if (this.onmessage) this.onmessage({ type: "message", data: JSON.stringify(msg) });
    return true;
  }
}

function findHub() {
  try {
    if (window.parent !== window && window.parent.callguardReplay) return window.parent.callguardReplay;
  } catch {
    // cross-origin parent: no harness
  }
  return null;
}
