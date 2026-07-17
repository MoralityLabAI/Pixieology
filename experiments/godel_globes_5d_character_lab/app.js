(function () {
  "use strict";

  const model = window.GodelCharacterModel;
  const space = model.space;
  const studyApi = window.GodelCharacterStudy;
  const query = new URLSearchParams(window.location.search);
  const dimensionIndex = new Map(space.tupleOrder.map((id, index) => [id, index]));
  const sliders = Array.from(document.querySelectorAll("input[data-dimension]"));
  const tupleOutput = document.getElementById("tuple-output");
  const formName = document.getElementById("form-name");
  const detail = document.getElementById("selected-detail");
  const backButton = document.getElementById("warp-back");
  const marker = document.getElementById("current-marker");
  const trail = document.getElementById("warp-trail");
  const nodesLayer = document.getElementById("map-nodes");
  const edgesLayer = document.getElementById("map-edges");
  const anchorButtons = document.getElementById("anchor-buttons");
  const leftWing = document.getElementById("left-wing");
  const rightWing = document.getElementById("right-wing");
  const leftSparks = document.getElementById("left-sparks");
  const rightFeathers = document.getElementById("right-feathers");
  const halo = document.getElementById("head-halo");
  const orbit = document.getElementById("head-orbit");
  const orbitMote = document.getElementById("orbit-mote");
  const conditionBadge = document.getElementById("condition-badge");
  const studyPanel = document.getElementById("study-panel");
  const studyMeta = document.getElementById("study-meta");
  const studyHeading = document.getElementById("study-heading");
  const studyInstruction = document.getElementById("study-instruction");
  const studyStart = document.getElementById("study-start");
  const studySkip = document.getElementById("study-skip");
  const studyExport = document.getElementById("study-export");
  const studyProgress = document.getElementById("study-progress");
  const studyDebrief = document.getElementById("study-debrief");
  const debriefReflection = document.getElementById("debrief-reflection");
  const debriefMap = document.getElementById("debrief-map");
  const debriefPreference = document.getElementById("debrief-preference");
  const debriefComments = document.getElementById("debrief-comments");

  let current = model.findAnchor("seedling").tuple.slice();
  let previous = null;
  let animationFrame = null;
  let trailPoints = [];
  let manualStart = null;
  let studySession = null;
  let studyTaskIndex = 0;
  let stateSequence = 0;
  let lastPublishedTuple = null;
  let studyStorageKey = null;
  let studyRestoreMessage = "";

  const participantId = query.get("participant");
  if (participantId && studyApi) {
    const round = Number(query.get("round") || "1");
    const requestedCondition = query.get("condition") || undefined;
    const expectedCondition = requestedCondition || studyApi.conditionFor(participantId, round);
    studyStorageKey = `godel-globes-study:${participantId}:${round}:${expectedCondition}`;
    try {
      const saved = window.localStorage.getItem(studyStorageKey);
      if (saved) {
        studySession = studyApi.StudySession.fromReceipt(JSON.parse(saved));
        studyTaskIndex = studySession.results.length;
        studyRestoreMessage = `Resumed ${studyTaskIndex} completed task${studyTaskIndex === 1 ? "" : "s"} from this browser.`;
      }
    } catch (error) {
      studyRestoreMessage = `Saved progress could not be restored: ${error.message}`;
    }
    if (!studySession) {
      studySession = new studyApi.StudySession({
        participantId,
        round,
        condition: requestedCondition
      });
    }
    document.body.dataset.condition = studySession.condition;
  }

  const projectedAnchors = space.anchors.map((anchor) => ({ anchor, raw: model.project(anchor.tuple) }));
  const rawX = projectedAnchors.map((item) => item.raw[0]);
  const rawY = projectedAnchors.map((item) => item.raw[1]);
  const bounds = {
    minX: Math.min(...rawX),
    maxX: Math.max(...rawX),
    minY: Math.min(...rawY),
    maxY: Math.max(...rawY)
  };

  function svgElement(name, attributes = {}) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  }

  function screenPoint(tuple) {
    const [rawPointX, rawPointY] = model.project(tuple);
    const x = 68 + ((rawPointX - bounds.minX) / (bounds.maxX - bounds.minX || 1)) * 464;
    const y = 360 - ((rawPointY - bounds.minY) / (bounds.maxY - bounds.minY || 1)) * 290;
    return [x, y];
  }

  function resetTo(tuple) {
    if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    current = model.clampTuple(tuple);
    previous = null;
    animationFrame = null;
    trailPoints = [];
    manualStart = null;
    render();
  }

  function persistStudySession() {
    if (!studySession || !studyStorageKey) return;
    try {
      window.localStorage.setItem(studyStorageKey, JSON.stringify(studySession.receipt()));
    } catch (error) {
      studyProgress.textContent = `Progress is live but could not be saved in this browser: ${error.message}`;
    }
  }

  function showStudyTask(message = "") {
    if (!studySession) return;
    const task = studyApi.tasks[studyTaskIndex];
    if (!task) {
      studyHeading.textContent = "Round complete";
      studyInstruction.textContent = "Export this session, then repeat the other round with the same participant ID.";
      studyStart.disabled = true;
      studySkip.disabled = true;
      studyDebrief.hidden = false;
      studyExport.disabled = !studySession.debrief;
      studyProgress.textContent = message || `${studySession.results.length} task results recorded locally.`;
      return;
    }
    studyHeading.textContent = `Task ${studyTaskIndex + 1} of ${studyApi.tasks.length}`;
    studyInstruction.textContent = task.instruction;
    studyStart.textContent = studyTaskIndex === 0 ? "Start task" : "Start next task";
    studyStart.disabled = Boolean(studySession.active);
    studySkip.disabled = !studySession.active;
    studyProgress.textContent = message;
  }

  function processStudyOutcome(outcome) {
    if (!studySession || !outcome || !outcome.complete) return;
    const result = outcome.result;
    studyTaskIndex += 1;
    persistStudySession();
    showStudyTask(`Completed in ${(result.elapsed_ms / 1000).toFixed(1)} seconds with ${result.actions} actions.`);
  }

  function recordStudyAction(type, payload = {}) {
    if (!studySession || !studySession.active) return;
    processStudyOutcome(studySession.action(type, payload, current));
  }

  function exportStudyReceipt() {
    if (!studySession || studySession.results.length !== studyApi.tasks.length || !studySession.debrief) return;
    const receipt = studySession.receipt();
    const blob = new Blob([`${JSON.stringify(receipt, null, 2)}\n`], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const safeParticipant = studySession.participantId.replace(/[^a-zA-Z0-9_-]+/g, "-");
    link.href = url;
    link.download = `${safeParticipant}-round-${studySession.round}-${studySession.condition}.json`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function setupStudy() {
    if (!studySession) return;
    studyPanel.hidden = false;
    conditionBadge.hidden = false;
    conditionBadge.textContent = studySession.condition === "embodied" ? "Embodied 2+2+1" : "Flat list";
    studyMeta.textContent = `PARTICIPANT ${studySession.participantId} · ROUND ${studySession.round} · ${studySession.condition.toUpperCase()}`;
    studyStart.addEventListener("click", () => {
      const task = studyApi.tasks[studyTaskIndex];
      if (!task || studySession.active) return;
      resetTo(task.startTuple);
      studySession.beginTask(task.id);
      studyStart.disabled = true;
      studySkip.disabled = false;
      studyProgress.textContent = "Task running. Completion is detected from the five-coordinate state.";
    });
    studySkip.addEventListener("click", () => {
      if (!studySession.active) return;
      studySession.skip();
      studyTaskIndex += 1;
      persistStudySession();
      showStudyTask("Task skipped and preserved in the session receipt.");
    });
    studyExport.addEventListener("click", exportStudyReceipt);
    studyDebrief.addEventListener("submit", (event) => {
      event.preventDefault();
      studySession.setDebrief({
        reflectionLocation: debriefReflection.value,
        mapMeaning: debriefMap.value,
        preference: debriefPreference.value,
        comments: debriefComments.value
      });
      persistStudySession();
      studyExport.disabled = false;
      studyProgress.textContent = "Debrief saved locally. Export the session receipt.";
    });
    if (studySession.debrief) {
      debriefReflection.value = studySession.debrief.reflection_location;
      debriefMap.value = studySession.debrief.map_meaning;
      debriefPreference.value = studySession.debrief.preference;
      debriefComments.value = studySession.debrief.comments;
    }
    showStudyTask(studyRestoreMessage);
  }

  function buildMap() {
    const seenEdges = new Set();
    projectedAnchors.forEach(({ anchor }) => {
      model.nearestAnchors(anchor.tuple, 4).slice(1).forEach(({ anchor: neighbor }) => {
        const id = [anchor.id, neighbor.id].sort().join("::");
        if (seenEdges.has(id)) return;
        seenEdges.add(id);
        const [x1, y1] = screenPoint(anchor.tuple);
        const [x2, y2] = screenPoint(neighbor.tuple);
        edgesLayer.appendChild(svgElement("line", { x1, y1, x2, y2, class: "map-edge" }));
      });
    });

    space.anchors.forEach((anchor) => {
      const [x, y] = screenPoint(anchor.tuple);
      const group = svgElement("g", { class: "map-node", "data-anchor": anchor.id, transform: `translate(${x} ${y})` });
      group.appendChild(svgElement("circle", { r: 7 }));
      const label = svgElement("text", { x: 11, y: -9 });
      label.textContent = anchor.name;
      group.appendChild(label);
      group.addEventListener("click", () => warpTo(
        anchor.tuple,
        anchor,
        true,
        { type: "anchor_warp", payload: { anchor_id: anchor.id, surface: "map" } }
      ));
      nodesLayer.appendChild(group);

      const button = document.createElement("button");
      button.type = "button";
      button.textContent = anchor.name;
      button.dataset.anchor = anchor.id;
      button.setAttribute("aria-pressed", anchor.id === "seedling" ? "true" : "false");
      button.addEventListener("click", () => warpTo(
        anchor.tuple,
        anchor,
        true,
        { type: "anchor_warp", payload: { anchor_id: anchor.id, surface: "button" } }
      ));
      anchorButtons.appendChild(button);
    });
  }

  function renderWings(tuple) {
    const [wonder, play, care, resolve, reflection] = tuple;
    const leftTipX = 165 - wonder * 92;
    const leftTipY = 242 - wonder * 116;
    const leftUpperY = 214 - play * 96;
    const leftLowerY = 307 - play * 38;
    leftWing.setAttribute(
      "d",
      `M287 238 C${255 - 55 * wonder} ${leftUpperY} ${leftTipX + 38} ${leftTipY - 18} ${leftTipX} ${leftTipY} ` +
      `C${leftTipX + 46} ${260 + 28 * play} ${220 - 24 * wonder} ${leftLowerY} 286 280 Z`
    );

    const rightTipX = 435 + resolve * 92;
    const rightTipY = 242 - resolve * 108;
    const rightUpperY = 220 - care * 70;
    const rightLowerY = 304 - care * 45;
    rightWing.setAttribute(
      "d",
      `M313 238 C${348 + 58 * care} ${rightUpperY} ${rightTipX - 42} ${rightTipY - 15} ${rightTipX} ${rightTipY} ` +
      `C${rightTipX - 36} ${250 + 26 * care} ${396 + 30 * resolve} ${rightLowerY} 314 280 Z`
    );

    leftSparks.replaceChildren();
    const sparkCount = Math.round(1 + play * 6);
    for (let index = 0; index < sparkCount; index += 1) {
      const angle = index * 1.7 + play * 0.8;
      const radius = 40 + index * 13;
      leftSparks.appendChild(
        svgElement("circle", {
          class: "spark",
          cx: 264 - Math.cos(angle) * radius * (0.6 + wonder * 0.35),
          cy: 238 - Math.sin(angle) * radius * 0.42 - wonder * 35,
          r: 2.2 + play * 2.2
        })
      );
    }

    rightFeathers.replaceChildren();
    for (let index = 0; index < 4; index += 1) {
      const fraction = (index + 1) / 5;
      const x = 320 + (rightTipX - 320) * fraction;
      const y = 250 + (rightTipY - 250) * fraction;
      rightFeathers.appendChild(
        svgElement("path", {
          class: "feather-line",
          d: `M${x - 12} ${y + 18 + care * 8} Q${x + 8} ${y + 4} ${x + 20 + resolve * 10} ${y - 5}`
        })
      );
    }

    const haloRadius = 46 + reflection * 30;
    const orbitRadius = haloRadius + 14 + reflection * 8;
    halo.setAttribute("r", haloRadius);
    halo.style.opacity = String(0.28 + reflection * 0.67);
    orbit.setAttribute("r", orbitRadius);
    orbit.style.opacity = String(0.18 + reflection * 0.48);
    orbitMote.setAttribute("cx", 300 + orbitRadius);
    orbitMote.setAttribute("r", 2.5 + reflection * 3.5);
  }

  function currentAnchor() {
    const nearest = model.nearestAnchors(current, 1)[0];
    return nearest.distance < 0.012 ? nearest.anchor : null;
  }

  function publishCharacterState() {
    const signature = current.map((value) => value.toFixed(12)).join("|");
    if (signature === lastPublishedTuple) return;
    lastPublishedTuple = signature;
    const state = { ...model.characterState(current), sequence: stateSequence };
    stateSequence += 1;
    window.dispatchEvent(new CustomEvent("pixieology:character-state", { detail: state }));
  }

  function render() {
    renderWings(current);
    const [x, y] = screenPoint(current);
    marker.setAttribute("transform", `translate(${x} ${y})`);
    trail.setAttribute("points", trailPoints.map((point) => point.join(",")).join(" "));
    tupleOutput.textContent = model.tupleLabel(current);

    sliders.forEach((slider) => {
      const index = dimensionIndex.get(slider.dataset.dimension);
      const value = Math.round(current[index] * 100);
      slider.value = String(value);
      document.getElementById(`${slider.dataset.dimension}-value`).textContent = String(value);
    });

    const anchor = currentAnchor();
    formName.textContent = anchor ? anchor.name : "Custom form";
    detail.textContent = anchor
      ? anchor.blurb
      : `Between ${model.nearestAnchors(current, 2).map((item) => item.anchor.name).join(" and ")}.`;
    document.querySelectorAll("[data-anchor]").forEach((node) => {
      const active = Boolean(anchor && node.dataset.anchor === anchor.id);
      if (node.tagName.toLowerCase() === "button") node.setAttribute("aria-pressed", String(active));
      else node.classList.toggle("is-active", active);
    });
    backButton.disabled = previous === null;
    publishCharacterState();
  }

  function smoothstep(value) {
    return value * value * (3 - 2 * value);
  }

  function warpTo(tuple, anchor = null, keepHistory = true, studyAction = null) {
    if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    const start = current.slice();
    const destination = model.clampTuple(tuple);
    if (model.distance5D(start, destination) < 1e-9) return;
    if (keepHistory) previous = start;
    trailPoints = [screenPoint(start)];
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const duration = reducedMotion ? 1 : 720;
    const startedAt = performance.now();
    formName.textContent = anchor ? `Warping to ${anchor.name}` : "Warping back";
    if (studySession && studySession.active && studyAction) {
      studySession.record("warp_start", {
        task_id: studySession.active.task.id,
        action_type: studyAction.type,
        ...studyAction.payload,
        from_tuple: start.slice(),
        to_tuple: destination.slice()
      });
    }

    function frame(now) {
      const linear = Math.min(1, (now - startedAt) / duration);
      current = model.interpolateTuple(start, destination, smoothstep(linear));
      trailPoints.push(screenPoint(current));
      render();
      if (linear < 1) animationFrame = requestAnimationFrame(frame);
      else {
        animationFrame = null;
        if (studyAction) recordStudyAction(studyAction.type, studyAction.payload);
      }
    }
    animationFrame = requestAnimationFrame(frame);
  }

  sliders.forEach((slider) => {
    const captureManualStart = () => {
      if (manualStart === null) manualStart = current.slice();
      if (animationFrame !== null) cancelAnimationFrame(animationFrame);
      animationFrame = null;
      trailPoints = [];
    };
    slider.addEventListener("pointerdown", captureManualStart);
    slider.addEventListener("keydown", captureManualStart);
    slider.addEventListener("input", () => {
      const index = dimensionIndex.get(slider.dataset.dimension);
      current[index] = Number(slider.value) / 100;
      render();
    });
    const closeManualEdit = () => {
      const changed = manualStart !== null && model.distance5D(manualStart, current) > 1e-9;
      if (changed) {
        previous = manualStart;
        recordStudyAction("dimension_change", {
          dimension: slider.dataset.dimension,
          value: Number(slider.value) / 100
        });
      }
      manualStart = null;
      render();
    };
    slider.addEventListener("pointerup", closeManualEdit);
    slider.addEventListener("change", closeManualEdit);
    slider.addEventListener("blur", closeManualEdit);
  });

  backButton.addEventListener("click", () => {
    if (previous === null) return;
    const destination = previous.slice();
    previous = current.slice();
    warpTo(destination, null, false, { type: "warp_back", payload: {} });
  });

  buildMap();
  render();
  setupStudy();
  window.GodelCharacterLab = Object.freeze({
    getTuple: () => current.slice(),
    getState: () => ({ ...model.characterState(current), sequence: Math.max(0, stateSequence - 1) }),
    getCondition: () => document.body.dataset.condition || "embodied",
    getStudyReceipt: () => studySession ? studySession.receipt() : null
  });
})();
