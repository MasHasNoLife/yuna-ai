// Yuna Web — main client: websocket chat, tabs, memory, system monitoring.
import { PcmPlayer, Recorder } from "/static/audio.js";

const $ = (id) => document.getElementById(id);
const chatLog = $("chat-log");
const input = $("chat-input");
const player = new PcmPlayer($("visualizer"));
const recorder = new Recorder();

let ws = null;
let currentMsg = null; // streaming Yuna bubble
let currentMeta = null; // {chips, recalled}
let lastThoughts = "";

// ── WebSocket ───────────────────────────────────────────────────────────────

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/chat`);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => setConn(true);
  ws.onclose = () => {
    setConn(false);
    setTimeout(connect, 2000);
  };
  ws.onmessage = (e) => {
    if (e.data instanceof ArrayBuffer) {
      player.feed(e.data);
      return;
    }
    handleEvent(JSON.parse(e.data));
  };
}

function setConn(up) {
  const el = $("conn-status");
  el.textContent = up ? "online" : "offline";
  el.className = `pill ${up ? "on" : "off"}`;
}

function send(obj) {
  if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
}

// ── Event handling ──────────────────────────────────────────────────────────

function handleEvent(ev) {
  switch (ev.type) {
    case "hello":
      $("speak-toggle").checked = ev.speak;
      $("tts-select").value = ev.tts_backend;
      $("llm-select").value = ev.llm_label.startsWith("google") ? "google" : "ollama";
      for (const [name, st] of Object.entries(ev.tts_backends)) {
        const opt = [...$("tts-select").options].find((o) => o.value === name);
        if (opt && !st.available) opt.textContent += " ⚠";
        if (opt) opt.title = st.reason || "";
      }
      sysNote(`connected — ${ev.llm_label}`);
      break;
    case "turn_start":
      startYunaBubble();
      lastThoughts = "";
      break;
    case "memory_recalled":
      currentMeta.recalled = ev.facts;
      break;
    case "token":
      appendToken(ev.text);
      break;
    case "thinking":
      lastThoughts += ev.text;
      $("thoughts-log").textContent = lastThoughts.slice(0, 4000) || "—";
      break;
    case "emotion":
      addChip(ev.tag);
      break;
    case "reply_done":
      finishBubble();
      refreshMetrics();
      break;
    case "memory_op":
      addMemoryEvent(ev);
      loadMemories();
      break;
    case "audio_start":
      player.start(ev.sample_rate);
      break;
    case "audio_end":
      player.stopVisualizer();
      refreshMetrics();
      break;
    case "tts_unavailable":
      sysNote(`voice off — ${ev.backend}: ${ev.reason}`, true);
      break;
    case "tts_error":
      sysNote(`TTS error (${ev.backend}): ${ev.message}`, true);
      break;
    case "backend_changed":
      sysNote(`LLM → ${ev.label}`);
      break;
    case "reset_done":
      chatLog.innerHTML = "";
      sysNote("history cleared");
      break;
    case "error":
      finishBubble();
      sysNote(ev.message, true);
      break;
  }
}

// ── Chat rendering ──────────────────────────────────────────────────────────

function sysNote(text, isError = false) {
  const div = document.createElement("div");
  div.className = `sys-note${isError ? " error" : ""}`;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function addUserMsg(text) {
  const div = document.createElement("div");
  div.className = "msg user";
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function startYunaBubble() {
  currentMsg = document.createElement("div");
  currentMsg.className = "msg yuna streaming";
  currentMeta = { chips: document.createElement("span"), text: document.createElement("span"), recalled: null };
  currentMsg.appendChild(currentMeta.chips);
  currentMsg.appendChild(currentMeta.text);
  chatLog.appendChild(currentMsg);
}

function appendToken(text) {
  if (!currentMsg) startYunaBubble();
  // Hide raw [tags] from the bubble text; chips carry them
  currentMeta.text.textContent = (currentMeta.text.textContent + text).replace(/\[.*?\]\s*/g, "");
  chatLog.scrollTop = chatLog.scrollHeight;
}

function addChip(tag) {
  if (!currentMeta) return;
  const chip = document.createElement("span");
  chip.className = "emotion-chip";
  chip.textContent = tag;
  currentMeta.chips.appendChild(chip);
}

function finishBubble() {
  if (!currentMsg) return;
  currentMsg.classList.remove("streaming");
  if (currentMeta.recalled && currentMeta.recalled.length) {
    const rec = document.createElement("span");
    rec.className = "recalled";
    rec.textContent = `recalled: ${currentMeta.recalled.join(" · ")}`;
    currentMsg.appendChild(rec);
  }
  currentMsg = null;
  currentMeta = null;
}

// ── Composer ────────────────────────────────────────────────────────────────

function submit(source = "text") {
  const text = input.value.trim();
  if (!text) return;
  addUserMsg(text);
  send({ type: "user_message", text, source });
  input.value = "";
}

$("send-btn").onclick = () => submit();
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    submit();
  }
});

$("speak-toggle").onchange = (e) => send({ type: "set_options", speak: e.target.checked });
$("tts-select").onchange = (e) => send({ type: "set_options", tts_backend: e.target.value });
$("llm-select").onchange = (e) => send({ type: "set_options", llm_backend: e.target.value });

// Push-to-talk: hold the mic button
const micBtn = $("mic-btn");
let recording = false;
async function startRec() {
  if (recording) return;
  try {
    await recorder.start();
    recording = true;
    micBtn.classList.add("recording");
  } catch {
    sysNote("microphone unavailable", true);
  }
}
async function stopRec() {
  if (!recording) return;
  recording = false;
  micBtn.classList.remove("recording");
  const blob = await recorder.stop();
  if (!blob || blob.size < 1000) return;
  sysNote("transcribing…");
  const form = new FormData();
  form.append("file", blob, "clip.webm");
  try {
    const r = await fetch("/api/stt", { method: "POST", body: form });
    const data = await r.json();
    if (data.text) {
      input.value = data.text;
      submit("voice");
    } else sysNote("didn't catch that", true);
  } catch {
    sysNote("transcription failed", true);
  }
}
micBtn.addEventListener("mousedown", startRec);
micBtn.addEventListener("mouseup", stopRec);
micBtn.addEventListener("mouseleave", () => recording && stopRec());
micBtn.addEventListener("touchstart", (e) => { e.preventDefault(); startRec(); });
micBtn.addEventListener("touchend", stopRec);

// ── Tabs ────────────────────────────────────────────────────────────────────

document.querySelectorAll(".tab").forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-body").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    $(`tab-${btn.dataset.tab}`).classList.add("active");
    if (btn.dataset.tab === "system") {
      refreshMetrics();
      refreshHealth();
    }
    if (btn.dataset.tab === "memory") loadMemories();
    if (btn.dataset.tab === "persona") loadPersona();
  };
});

// ── Memory tab ──────────────────────────────────────────────────────────────

function addMemoryEvent(ev) {
  const feed = $("memory-feed");
  if (feed.querySelector(".sys-note")) feed.innerHTML = "";
  const div = document.createElement("div");
  div.className = `mem-event ${ev.op === "update" ? "update" : ev.op === "forget" ? "forget" : ""}`;
  const label = { fact: "learned", update: "updated", forget: "forgot" }[ev.op] || ev.op;
  div.innerHTML = `<span class="dim">${label}</span>${escapeHtml(ev.new_fact || ev.fact)}`;
  feed.prepend(div);
}

let memories = [];
async function loadMemories() {
  try {
    const r = await fetch("/api/memories");
    memories = (await r.json()).memories;
    renderMemories();
  } catch {
    $("memory-list").innerHTML = '<div class="sys-note error">could not load memories</div>';
  }
}

function renderMemories() {
  const filter = $("mem-search").value.toLowerCase();
  const list = $("memory-list");
  list.innerHTML = "";
  memories
    .filter((m) => !filter || m.fact.toLowerCase().includes(filter) || m.username.includes(filter))
    .forEach((m) => {
      const div = document.createElement("div");
      div.className = "mem-item";
      const kind = m.kind && m.kind !== "fact" ? ` · ${escapeHtml(m.kind)}` : "";
      div.innerHTML = `<div><span class="who">${escapeHtml(m.username)}${kind}</span><br>${escapeHtml(m.fact)}</div>`;
      const del = document.createElement("button");
      del.textContent = "✕";
      del.title = "delete";
      del.onclick = async () => {
        await fetch(`/api/memories/${m.id}`, { method: "DELETE" });
        loadMemories();
      };
      div.appendChild(del);
      list.appendChild(div);
    });
  if (!list.children.length) list.innerHTML = '<div class="sys-note">no facts stored</div>';
}

$("mem-search").oninput = renderMemories;
$("mem-refresh").onclick = loadMemories;
$("mem-add").onclick = async () => {
  const fact = prompt("New fact:");
  if (!fact) return;
  await fetch("/api/memories", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "global", fact }),
  });
  loadMemories();
};

// ── Persona tab ─────────────────────────────────────────────────────────────

async function loadPersona() {
  const name = $("persona-select").value;
  const r = await fetch(`/api/prompt?name=${name}`);
  $("persona-editor").value = (await r.json()).content;
  $("persona-status").textContent = "";
}
$("persona-select").onchange = loadPersona;
$("persona-save").onclick = async () => {
  const name = $("persona-select").value;
  await fetch(`/api/prompt?name=${name}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content: $("persona-editor").value }),
  });
  $("persona-status").textContent = "saved ✓ (restart session to apply)";
};

// ── System tab ──────────────────────────────────────────────────────────────

async function refreshMetrics() {
  try {
    const r = await fetch("/api/metrics");
    const m = await r.json();
    $("sys-uptime").textContent = `up ${Math.floor(m.uptime_s / 60)}m`;

    const c = m.totals;
    const a = m.averages;
    $("sys-counters").innerHTML = [
      ["turns", c.turns], ["errors", c.errors],
      ["facts learned", c.memory_facts], ["updates", c.memory_updates],
      ["avg TTFT", a.ttft_ms ? `${(a.ttft_ms / 1000).toFixed(2)}s` : "—"],
      ["avg tok/s", a.tok_per_s ?? "—"],
      ["avg TTFA", a.ttfa_ms ? `${(a.ttfa_ms / 1000).toFixed(2)}s` : "—"],
      ["voice turns", c.voice_turns],
    ].map(([k, v]) => `<div class="counter"><b>${v}</b>${k}</div>`).join("");

    const rows = m.turns.slice(-12).reverse().map((t) => {
      const ttft = t.ttft_ms != null ? `${(t.ttft_ms / 1000).toFixed(1)}s` : "—";
      const tps = t.tok_per_s ? `${t.tok_per_s}t/s` : "—";
      const mem = t.recalled ? `r${t.recalled}` : "";
      const err = t.error ? `<span class="err">✕</span>` : "";
      return `<div class="turn-row">#${t.turn} ${t.source === "voice" ? "🎤" : "⌨"} ttft ${ttft} · ${tps} ${mem} ${err}</div>`;
    });
    $("turns-table").innerHTML = rows.join("") || '<div class="sys-note">no turns yet</div>';

    const last = m.turns[m.turns.length - 1];
    if (last && last.ttft_ms != null) {
      const ttfa = last.ttfa_ms != null ? ` · voice ${(last.ttfa_ms / 1000).toFixed(1)}s` : "";
      $("latency-badge").textContent =
        `${(last.ttft_ms / 1000).toFixed(1)}s · ${last.tok_per_s || "?"} tok/s${ttfa}`;
    }
  } catch { /* server briefly busy */ }
}

async function refreshHealth() {
  const list = $("health-list");
  list.innerHTML = '<div class="sys-note">checking…</div>';
  try {
    const r = await fetch("/api/health");
    const { checks } = await r.json();
    list.innerHTML = checks
      .map((c) => {
        const icon = { ok: "✔", warn: "⚠", fail: "✘" }[c.status];
        return `<div class="health-item"><span class="s-${c.status}">${icon}</span>${escapeHtml(c.name)}<span class="dim">${escapeHtml(c.detail)}</span></div>`;
      })
      .join("");
  } catch {
    list.innerHTML = '<div class="sys-note error">health check failed</div>';
  }
}
$("health-refresh").onclick = refreshHealth;

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}

// ── Boot ────────────────────────────────────────────────────────────────────

connect();
loadMemories();
setInterval(() => {
  if (document.querySelector('.tab[data-tab="system"]').classList.contains("active")) refreshMetrics();
}, 5000);
