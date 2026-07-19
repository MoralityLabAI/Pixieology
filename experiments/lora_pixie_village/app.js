const ui = {
  healthDot: document.querySelector("#health-dot"),
  serverStatus: document.querySelector("#server-status"),
  topic: document.querySelector("#topic-input"),
  threadSelect: document.querySelector("#storyworld-thread-select"),
  threadDecision: document.querySelector("#thread-decision"),
  openRoom: document.querySelector("#open-room"),
  agentCards: [document.querySelector("#agent-left"), document.querySelector("#agent-right")],
  transcript: document.querySelector("#transcript"),
  sessionId: document.querySelector("#session-id"),
  play: document.querySelector("#play"),
  pause: document.querySelector("#pause"),
  step: document.querySelector("#step"),
  pace: document.querySelector("#pace"),
  export: document.querySelector("#export"),
  turnStatus: document.querySelector("#turn-status"),
  decisionCard: document.querySelector("#decision-card"),
  decisionTitle: document.querySelector("#decision-title"),
  decisionLocation: document.querySelector("#decision-location"),
  decisionSource: document.querySelector("#decision-source"),
  decisionSituation: document.querySelector("#decision-situation"),
  decisionFacts: document.querySelector("#decision-facts"),
  decisionOptions: document.querySelector("#decision-options"),
  engineMode: document.querySelector("#engine-mode"),
  engineLocation: document.querySelector("#engine-location"),
  engineTurn: document.querySelector("#engine-turn"),
  worldHistory: document.querySelector("#world-history")
};

let publicConfig = null;
let session = null;
let playing = false;
let stepping = false;
let timer = null;

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) }
  });
  let body;
  try { body = await response.json(); } catch { body = { message: `HTTP ${response.status}` }; }
  if (!response.ok) throw new Error(body.message || body.error || `HTTP ${response.status}`);
  return body;
}

function setStatus(message, error = false) {
  ui.turnStatus.textContent = message;
  ui.turnStatus.classList.toggle("error", error);
}

function configureResident(card, agent, role) {
  card.style.setProperty("--resident-color", agent.color);
  card.querySelector(".resident-role").textContent = role;
  card.querySelector(".resident-name").textContent = agent.display_name;
  card.querySelector(".resident-glyph").textContent = agent.glyph;
  card.querySelector(".adapter-badge").textContent = `${agent.adapter_label} · ${agent.provider_type.replaceAll("_", " ")}`;
}

function renderConfig() {
  if (!publicConfig) return;
  publicConfig.agents.forEach((agent, index) => configureResident(ui.agentCards[index], agent, `RESIDENT ${index ? "B" : "A"}`));
}

function populateDecisionThreads() {
  for (const decision of publicConfig?.decisions || []) {
    if (ui.threadSelect.querySelector(`option[value="${CSS.escape(decision.decision_id)}"]`)) continue;
    const option = document.createElement("option");
    option.value = decision.decision_id;
    option.textContent = `${decision.title} · ${decision.location}`;
    ui.threadSelect.append(option);
  }
}

function renderDecision() {
  const packet = session?.decision_packet || null;
  ui.decisionCard.hidden = !packet;
  if (!packet) return;
  ui.decisionTitle.textContent = packet.title;
  ui.decisionLocation.textContent = packet.location;
  ui.decisionSource.textContent = `${packet.source.storyworld_id} · ${packet.source.split}`;
  ui.decisionSituation.textContent = packet.situation;
  ui.decisionFacts.replaceChildren(...packet.visible_facts.map((fact) => {
    const item = document.createElement("li"); item.textContent = fact; return item;
  }));
  ui.decisionOptions.replaceChildren(...packet.options.map((entry) => {
    const item = document.createElement("li");
    const label = document.createElement("strong"); label.textContent = `${entry.label}: `;
    item.append(label, document.createTextNode(entry.description));
    return item;
  }));
  const engine = session.engine;
  ui.engineMode.textContent = session.engine_mode === "canonical" ? "Canonical engine active" : "Discussion context only";
  ui.engineLocation.textContent = engine?.public_state?.location || packet.location;
  ui.engineTurn.textContent = `Engine turn ${engine?.public_state?.engine_turn || 0}`;
  ui.worldHistory.replaceChildren(...(engine?.history || []).map((receipt) => {
    const event = receipt.public_event;
    const row = document.createElement("li");
    const heading = document.createElement("strong");
    heading.textContent = `${event.outcome} · ${event.location}`;
    row.append(heading, document.createTextNode(event.outcome_notes ? ` — ${event.outcome_notes}` : ""));
    return row;
  }));
}

function renderTranscript() {
  ui.transcript.replaceChildren();
  if (!session || session.transcript.length === 0) {
    const empty = document.createElement("li");
    empty.className = "empty-log";
    empty.textContent = "No turns yet. The server will always choose the next resident.";
    ui.transcript.append(empty);
    return;
  }
  for (const turn of session.transcript) {
    const agent = session.agents.find((item) => item.id === turn.speaker_id);
    const row = document.createElement("li");
    row.style.setProperty("--speaker-color", agent?.color || "#ffd36a");
    const meta = document.createElement("div");
    meta.className = "turn-meta";
    const speaker = document.createElement("span");
    speaker.className = "speaker";
    speaker.textContent = turn.speaker_name;
    const details = document.createElement("span");
    details.textContent = `turn ${turn.turn + 1} · ${turn.latency_ms} ms`;
    if (turn.proposed_action_id) {
      const proposal = document.createElement("span");
      proposal.className = "proposal-badge";
      proposal.textContent = `proposes ${turn.proposed_action_id}`;
      details.append(proposal);
    }
    if (turn.proposal_speech_synthesized) {
      const rendered = document.createElement("span");
      rendered.className = "proposal-badge";
      rendered.textContent = "speech rendered from marker-only choice";
      details.append(rendered);
    } else if (turn.proposal_markers_deduplicated) {
      const normalized = document.createElement("span");
      normalized.className = "proposal-badge";
      normalized.textContent = "duplicate identical markers normalized";
      details.append(normalized);
    }
    const message = document.createElement("p");
    message.className = "message";
    message.textContent = turn.message;
    meta.append(speaker, details);
    row.append(meta, message);
    if (turn.world_consequence) {
      const consequence = document.createElement("div");
      consequence.className = "world-consequence";
      const label = document.createElement("strong");
      label.textContent = `World: ${turn.world_consequence.outcome} · ${turn.world_consequence.location}`;
      consequence.append(label, document.createTextNode(turn.world_consequence.outcome_notes ? ` — ${turn.world_consequence.outcome_notes}` : ""));
      row.append(consequence);
    }
    ui.transcript.append(row);
  }
  ui.transcript.scrollTop = ui.transcript.scrollHeight;
}

function renderResidents() {
  const recent = new Map();
  for (const turn of session?.transcript || []) recent.set(turn.speaker_id, turn.message);
  (session?.agents || publicConfig?.agents || []).forEach((agent, index) => {
    ui.agentCards[index].querySelector(".speech-preview").textContent = recent.get(agent.id) || "Listening by the hearth…";
    ui.agentCards[index].classList.toggle("speaking", session?.next_speaker_id === agent.id);
  });
}

function renderControls() {
  const active = Boolean(session && session.status === "open");
  ui.play.disabled = !active || playing;
  ui.pause.disabled = !active || !playing;
  ui.step.disabled = !active || stepping || playing;
  ui.export.disabled = !session;
  ui.openRoom.disabled = stepping;
  ui.threadDecision.disabled = !active || Boolean(session?.decision_id) || !ui.threadSelect.value || stepping;
  ui.threadSelect.disabled = !active || Boolean(session?.decision_id) || stepping;
  ui.sessionId.textContent = session?.session_id || "not started";
  renderResidents();
}

function renderAll() {
  renderConfig();
  populateDecisionThreads();
  renderDecision();
  renderTranscript();
  renderControls();
}

async function openRoom() {
  stopPlaying();
  const topic = ui.topic.value.trim();
  if (!topic) return setStatus("Give the residents a public topic first.", true);
  ui.openRoom.disabled = true;
  setStatus("Opening a clean room…");
  try {
    session = await api("/api/sessions", { method: "POST", body: JSON.stringify({ topic, seed: 17 }) });
    history.replaceState(null, "", `?session=${encodeURIComponent(session.session_id)}`);
    setStatus(`Paused · ${session.agents.find((agent) => agent.id === session.next_speaker_id).display_name} speaks next`);
    renderAll();
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    ui.openRoom.disabled = false;
  }
}

async function threadDecision() {
  if (!session || session.status !== "open" || session.decision_id) return;
  const decisionId = ui.threadSelect.value;
  if (!decisionId) return setStatus("Choose a public Storyworld decision first.", true);
  stopPlaying();
  stepping = true;
  renderControls();
  setStatus("Threading validated public decision context into the conversation...");
  try {
    session = await api(`/api/sessions/${encodeURIComponent(session.session_id)}/threads`, {
      method: "POST",
      body: JSON.stringify({ decision_id: decisionId })
    });
    renderAll();
    setStatus(`Paused - decision threaded at turn ${session.thread_attached_turn}`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    stepping = false;
    renderControls();
  }
}

async function oneTurn({ fromLoop = false } = {}) {
  if (!session || stepping || session.status !== "open") return;
  stepping = true;
  const speaker = session.agents.find((agent) => agent.id === session.next_speaker_id);
  ui.agentCards.forEach((card, index) => card.classList.toggle("speaking", session.agents[index].id === session.next_speaker_id));
  renderControls();
  setStatus(`${speaker?.display_name || "Resident"} is composing public speech…`);
  try {
    session = await api(`/api/sessions/${encodeURIComponent(session.session_id)}/step`, { method: "POST", body: "{}" });
    renderAll();
    if (session.status !== "open") {
      stopPlaying();
      setStatus("Conversation reached its configured turn limit.");
    } else {
      const next = session.agents.find((agent) => agent.id === session.next_speaker_id);
      setStatus(`${playing ? "Playing" : "Paused"} · ${next.display_name} speaks next`);
    }
  } catch (error) {
    stopPlaying();
    setStatus(`${speaker?.display_name || "Provider"} did not advance the room: ${error.message}`, true);
  } finally {
    stepping = false;
    renderControls();
    if (fromLoop && playing) scheduleNext();
  }
}

function scheduleNext() {
  clearTimeout(timer);
  timer = setTimeout(() => oneTurn({ fromLoop: true }), Number(ui.pace.value));
}

function startPlaying() {
  if (!session || session.status !== "open" || playing) return;
  playing = true;
  renderControls();
  setStatus("Playing · server-controlled alternation");
  oneTurn({ fromLoop: true });
}

function stopPlaying() {
  playing = false;
  clearTimeout(timer);
  timer = null;
  renderControls();
  if (session?.status === "open") {
    const next = session.agents.find((agent) => agent.id === session.next_speaker_id);
    setStatus(`Paused · ${next.display_name} speaks next`);
  }
}

function exportSession() {
  if (!session) return;
  const blob = new Blob([JSON.stringify(session, null, 2) + "\n"], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `${session.session_id}.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

async function boot() {
  try {
    const [health, config] = await Promise.all([api("/api/health"), api("/api/config")]);
    publicConfig = config;
    ui.healthDot.classList.add("ok");
    ui.serverStatus.textContent = `${health.room_id} · ${health.providers.join(" + ")} · conversation platform ready`;
    renderAll();
    const resumeId = new URLSearchParams(location.search).get("session");
    if (resumeId) {
      try {
        session = await api(`/api/sessions/${encodeURIComponent(resumeId)}`);
        ui.topic.value = session.topic;
        ui.threadSelect.value = session.decision_id || "";
        renderAll();
        const next = session.agents.find((agent) => agent.id === session.next_speaker_id);
        setStatus(next ? `Resumed · paused · ${next.display_name} speaks next` : "Resumed · conversation complete");
      } catch (error) {
        setStatus(`Could not resume ${resumeId}: ${error.message}`, true);
      }
    } else {
      setStatus("Paused · ready to open a room");
    }
  } catch (error) {
    ui.healthDot.classList.add("bad");
    ui.serverStatus.textContent = "Local server unavailable";
    setStatus(`Start server.py first: ${error.message}`, true);
  }
}

ui.openRoom.addEventListener("click", openRoom);
ui.threadDecision.addEventListener("click", threadDecision);
ui.play.addEventListener("click", startPlaying);
ui.pause.addEventListener("click", stopPlaying);
ui.step.addEventListener("click", () => oneTurn());
ui.export.addEventListener("click", exportSession);
ui.pace.addEventListener("change", () => { if (playing) scheduleNext(); });
ui.threadSelect.addEventListener("change", renderControls);
window.addEventListener("beforeunload", () => clearTimeout(timer));

boot();
