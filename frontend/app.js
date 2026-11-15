const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("question");
const sendBtn = document.getElementById("send");
const kSel = document.getElementById("k");
const statusEl = document.getElementById("status");

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text; // textContent avoids HTML injection
  return e;
}

function scrollDown() {
  chat.scrollTop = chat.scrollHeight;
}

function addUser(text) {
  const m = el("div", "msg user");
  m.appendChild(el("div", "bubble", text));
  chat.appendChild(m);
  scrollDown();
}

function addTyping() {
  const m = el("div", "msg bot");
  const b = el("div", "bubble typing");
  b.innerHTML = "<span></span><span></span><span></span>";
  m.appendChild(b);
  chat.appendChild(m);
  scrollDown();
  return m;
}

function addBot(answer, sources) {
  const m = el("div", "msg bot");
  m.appendChild(el("div", "bubble", answer));

  if (sources && sources.length) {
    const d = el("details", "sources");
    d.appendChild(el("summary", null, `Sources (${sources.length} passages)`));
    sources.forEach((s) => {
      const box = el("div", "src");
      const head = el("div");
      head.appendChild(el("b", null, `Page ${s.page}`));
      head.appendChild(el("small", null, `  ·  distance ${s.score.toFixed(3)}`));
      box.appendChild(head);
      box.appendChild(el("div", null, s.snippet + (s.snippet.length >= 300 ? "…" : "")));
      d.appendChild(box);
    });
    m.appendChild(d);
  }
  chat.appendChild(m);
  scrollDown();
}

function addError(msg) {
  const m = el("div", "msg bot");
  m.appendChild(el("div", "bubble error", msg));
  chat.appendChild(m);
  scrollDown();
}

async function ask(question) {
  addUser(question);
  const typing = addTyping();
  sendBtn.disabled = true;
  input.disabled = true;
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, k: Number(kSel.value) }),
    });
    const data = await res.json().catch(() => ({}));
    typing.remove();
    if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
    addBot(data.answer, data.sources);
  } catch (err) {
    typing.remove();
    addError(err.message || "Something went wrong.");
  } finally {
    sendBtn.disabled = false;
    input.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (q.length < 3) return;
  input.value = "";
  ask(q);
});

document.querySelectorAll(".chip").forEach((c) =>
  c.addEventListener("click", () => ask(c.textContent))
);

async function checkHealth() {
  try {
    const r = await fetch("/api/health");
    const j = await r.json();
    statusEl.textContent = j.ready ? "ready" : "starting…";
    statusEl.className = "status " + (j.ready ? "ok" : "");
  } catch {
    statusEl.textContent = "offline";
    statusEl.className = "status err";
  }
}
checkHealth();
setInterval(checkHealth, 15000);
input.focus();
