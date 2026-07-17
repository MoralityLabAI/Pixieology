(function () {
  "use strict";

  const model = window.GodelCharacterModel;
  const space = model.space;
  const studyApi = window.GodelCharacterStudy;
  const traceApi = window.GodelManifoldTrace;
  const query = new URLSearchParams(window.location.search);
  const dimensionIndex = new Map(space.tupleOrder.map((id, index) => [id, index]));
  const sliders = Array.from(document.querySelectorAll("input[data-dimension]"));
  const tupleOutput = document.getElementById("tuple-output");
  const formName = document.getElementById("form-name");
  const detail = document.getElementById("selected-detail");
  const backButton = document.getElementById("warp-back");
  const anchorButtons = document.getElementById("anchor-buttons");
  const manifoldCanvas = document.getElementById("manifold-canvas");
  const manifoldContext = manifoldCanvas.getContext("2d");
  const manifoldPlay = document.getElementById("manifold-play");
  const manifoldTime = document.getElementById("manifold-time");
  const manifoldTimeValue = document.getElementById("manifold-time-value");
  const manifoldSource = document.getElementById("manifold-source");
  const manifoldFile = document.getElementById("manifold-file");
  const manifoldFileButton = document.getElementById("manifold-file-button");
  const manifoldStatus = document.getElementById("manifold-status");
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
  let manualStart = null;
  let studySession = null;
  let studyTaskIndex = 0;
  let stateSequence = 0;
  let lastPublishedTuple = null;
  let studyStorageKey = null;
  let studyRestoreMessage = "";
  let activeTrace = traceApi.authoredTrace();
  let traceCursor = 0;
  let tracePlaying = !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let manifoldAnimationFrame = null;
  let lastManifoldTime = null;
  let cameraYaw = -0.55;
  let cameraPitch = -0.24;
  let dragState = null;
  let lastManifoldSignature = "";

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
    tracePlaying = false;
  }

  function svgElement(name, attributes = {}) {
    const node = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    return node;
  }

  function resetTo(tuple) {
    if (animationFrame !== null) cancelAnimationFrame(animationFrame);
    current = model.clampTuple(tuple);
    previous = null;
    animationFrame = null;
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

  function buildAnchorButtons() {
    space.anchors.forEach((anchor) => {
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

  function cssColor(name, fallback) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
  }

  function featurePoint(values, semantics = activeTrace.semantics) {
    if (semantics === "character_tuple") return model.project3D(values);
    return space.projection.matrix.map((row) =>
      row.reduce((sum, coefficient, index) => sum + coefficient * (values[index] - 0.5), 0)
    );
  }

  function rotatePoint(point) {
    const cosYaw = Math.cos(cameraYaw);
    const sinYaw = Math.sin(cameraYaw);
    const cosPitch = Math.cos(cameraPitch);
    const sinPitch = Math.sin(cameraPitch);
    const x = cosYaw * point[0] + sinYaw * point[2];
    const yawZ = -sinYaw * point[0] + cosYaw * point[2];
    const y = cosPitch * point[1] - sinPitch * yawZ;
    const z = sinPitch * point[1] + cosPitch * yawZ;
    return [x, y, z];
  }

  function canvasPoint(point, width, height, radius) {
    const rotated = rotatePoint(point);
    const perspective = 1 / (1.18 - rotated[2] * 0.16);
    return {
      x: width / 2 + rotated[0] * radius * perspective,
      y: height / 2 - rotated[1] * radius * perspective,
      z: rotated[2],
      perspective
    };
  }

  function drawSphereGrid(context, width, height, radius) {
    context.save();
    context.strokeStyle = cssColor("--border", "#39354d");
    context.globalAlpha = 0.42;
    context.lineWidth = 1;
    const curves = [];
    for (const latitude of [-Math.PI / 3, -Math.PI / 6, 0, Math.PI / 6, Math.PI / 3]) {
      const ringRadius = Math.cos(latitude);
      curves.push(Array.from({ length: 65 }, (_, index) => {
        const longitude = (index / 64) * Math.PI * 2;
        return [ringRadius * Math.cos(longitude), Math.sin(latitude), ringRadius * Math.sin(longitude)];
      }));
    }
    for (let meridian = 0; meridian < 6; meridian += 1) {
      const longitude = (meridian / 6) * Math.PI;
      curves.push(Array.from({ length: 65 }, (_, index) => {
        const latitude = -Math.PI / 2 + (index / 64) * Math.PI;
        return [Math.cos(latitude) * Math.cos(longitude), Math.sin(latitude), Math.cos(latitude) * Math.sin(longitude)];
      }));
    }
    curves.forEach((curve) => {
      context.beginPath();
      curve.forEach((point, index) => {
        const screen = canvasPoint(point, width, height, radius);
        if (index === 0) context.moveTo(screen.x, screen.y);
        else context.lineTo(screen.x, screen.y);
      });
      context.stroke();
    });
    context.restore();
  }

  function traceSample() {
    return traceApi.interpolate(activeTrace, traceCursor);
  }

  function updateTraceControls(sample) {
    manifoldTime.max = String(activeTrace.frames.length - 1);
    manifoldTime.value = String(traceCursor);
    manifoldTimeValue.textContent = sample.label;
    manifoldPlay.textContent = tracePlaying ? "Pause" : "Play";
    manifoldPlay.setAttribute("aria-pressed", String(tracePlaying));
    const state = tracePlaying ? "Playing" : "Paused";
    const values = sample.values.map((value, index) => `${activeTrace.axes[index].label} ${Math.round(value * 100)}`).join(" · ");
    manifoldStatus.textContent = activeTrace.syncsToCharacter
      ? `${state} · ${sample.label} · ${values}`
      : `${state} · ${sample.label} · actual mechanical data, uncalibrated to character traits · ${values}`;
    manifoldCanvas.setAttribute(
      "aria-label",
      `${activeTrace.title}. ${state} at ${sample.label}. Five-dimensional values: ${values}. Drag to rotate the three-dimensional projection.`
    );
  }

  function publishManifoldFrame(sample) {
    const signature = `${activeTrace.id}|${sample.t.toFixed(5)}|${sample.values.map((value) => value.toFixed(5)).join("|")}`;
    if (signature === lastManifoldSignature) return;
    lastManifoldSignature = signature;
    window.dispatchEvent(new CustomEvent("pixieology:manifold-frame", {
      detail: {
        schema: activeTrace.schema,
        trace_id: activeTrace.id,
        semantics: activeTrace.semantics,
        alignment_status: activeTrace.alignment.status,
        t: sample.t,
        values: sample.values.slice(),
        metadata: { ...sample.metadata }
      }
    }));
  }

  function applyTraceFrame() {
    const sample = traceSample();
    if (activeTrace.syncsToCharacter && model.distance5D(current, sample.values) > 1e-4) {
      current = model.clampTuple(sample.values);
      render();
    }
    updateTraceControls(sample);
    publishManifoldFrame(sample);
    return sample;
  }

  function renderManifold() {
    const rectangle = manifoldCanvas.getBoundingClientRect();
    const width = Math.max(1, rectangle.width);
    const height = Math.max(1, rectangle.height);
    const density = Math.min(2, window.devicePixelRatio || 1);
    const pixelWidth = Math.round(width * density);
    const pixelHeight = Math.round(height * density);
    if (manifoldCanvas.width !== pixelWidth || manifoldCanvas.height !== pixelHeight) {
      manifoldCanvas.width = pixelWidth;
      manifoldCanvas.height = pixelHeight;
    }
    manifoldContext.setTransform(density, 0, 0, density, 0, 0);
    manifoldContext.clearRect(0, 0, width, height);
    const radius = Math.min(width, height) * 0.39;
    drawSphereGrid(manifoldContext, width, height, radius);

    const rawPath = activeTrace.frames.map((frame) => featurePoint(frame.values));
    const maximumNorm = Math.max(1e-9, ...rawPath.map((point) => Math.hypot(...point)));
    const path = rawPath.map((point) => point.map((coordinate) => (coordinate / maximumNorm) * 0.82));
    const primary = cssColor("--primary", "#d7c7ff");
    const foreground = cssColor("--foreground", "#f3f0ff");

    manifoldContext.save();
    manifoldContext.lineCap = "round";
    manifoldContext.lineJoin = "round";
    for (let index = 1; index < path.length; index += 1) {
      const left = canvasPoint(path[index - 1], width, height, radius);
      const right = canvasPoint(path[index], width, height, radius);
      manifoldContext.beginPath();
      manifoldContext.moveTo(left.x, left.y);
      manifoldContext.lineTo(right.x, right.y);
      manifoldContext.strokeStyle = primary;
      manifoldContext.globalAlpha = index <= traceCursor + 1 ? 0.86 : 0.24;
      manifoldContext.lineWidth = index <= traceCursor + 1 ? 2.4 : 1.2;
      manifoldContext.stroke();
    }
    const nodes = path.map((point, index) => ({ index, ...canvasPoint(point, width, height, radius) }));
    nodes.sort((left, right) => left.z - right.z).forEach((node) => {
      manifoldContext.beginPath();
      manifoldContext.arc(node.x, node.y, 2.8 + node.perspective, 0, Math.PI * 2);
      manifoldContext.fillStyle = primary;
      manifoldContext.globalAlpha = 0.42 + Math.max(0, node.z) * 0.28;
      manifoldContext.fill();
    });

    const sample = traceSample();
    const rawCursor = featurePoint(sample.values);
    const cursorPoint = rawCursor.map((coordinate) => (coordinate / maximumNorm) * 0.82);
    const cursor = canvasPoint(cursorPoint, width, height, radius);
    manifoldContext.globalAlpha = 0.2;
    manifoldContext.fillStyle = primary;
    manifoldContext.beginPath();
    manifoldContext.arc(cursor.x, cursor.y, 15, 0, Math.PI * 2);
    manifoldContext.fill();
    manifoldContext.globalAlpha = 1;
    manifoldContext.fillStyle = foreground;
    manifoldContext.beginPath();
    manifoldContext.arc(cursor.x, cursor.y, 5.5, 0, Math.PI * 2);
    manifoldContext.fill();

    if (activeTrace.syncsToCharacter) {
      const rawCurrent = featurePoint(current, "character_tuple");
      const currentPoint = rawCurrent.map((coordinate) => (coordinate / maximumNorm) * 0.82);
      const edited = canvasPoint(currentPoint, width, height, radius);
      manifoldContext.strokeStyle = foreground;
      manifoldContext.lineWidth = 1.5;
      manifoldContext.strokeRect(edited.x - 5, edited.y - 5, 10, 10);
    }
    manifoldContext.restore();
  }

  function setTracePlaying(playing) {
    tracePlaying = Boolean(playing);
    lastManifoldTime = null;
    updateTraceControls(traceSample());
  }

  function setActiveTrace(trace, source = "custom") {
    activeTrace = traceApi.normalizeTrace(trace);
    traceCursor = 0;
    lastManifoldSignature = "";
    if (source === "character" || source === "vpd") manifoldSource.value = source;
    else manifoldSource.selectedIndex = -1;
    applyTraceFrame();
  }

  function animateManifold(now) {
    if (lastManifoldTime === null) lastManifoldTime = now;
    const elapsed = Math.min(80, now - lastManifoldTime);
    lastManifoldTime = now;
    if (tracePlaying) {
      const maximum = activeTrace.frames.length - 1;
      traceCursor = maximum > 0 ? (traceCursor + elapsed / 1800) % maximum : 0;
      cameraYaw += elapsed * 0.000055;
      applyTraceFrame();
    }
    renderManifold();
    manifoldAnimationFrame = requestAnimationFrame(animateManifold);
  }

  function setupManifold() {
    manifoldPlay.addEventListener("click", () => setTracePlaying(!tracePlaying));
    manifoldTime.addEventListener("pointerdown", () => setTracePlaying(false));
    manifoldTime.addEventListener("input", () => {
      traceCursor = Number(manifoldTime.value);
      applyTraceFrame();
      renderManifold();
    });
    manifoldSource.addEventListener("change", () => {
      if (manifoldSource.value === "vpd") setActiveTrace(window.GodelVpdTraceData, "vpd");
      else setActiveTrace(traceApi.authoredTrace(), "character");
    });
    manifoldFileButton.addEventListener("click", () => manifoldFile.click());
    manifoldFile.addEventListener("change", async () => {
      const file = manifoldFile.files?.[0];
      if (!file) return;
      try {
        setActiveTrace(traceApi.parseText(await file.text()), "custom");
        setTracePlaying(false);
      } catch (error) {
        manifoldStatus.textContent = `Trace refused: ${error.message}`;
      } finally {
        manifoldFile.value = "";
      }
    });
    manifoldCanvas.addEventListener("pointerdown", (event) => {
      manifoldCanvas.setPointerCapture(event.pointerId);
      dragState = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
    });
    manifoldCanvas.addEventListener("pointermove", (event) => {
      if (!dragState || dragState.pointerId !== event.pointerId) return;
      cameraYaw += (event.clientX - dragState.x) * 0.009;
      cameraPitch = Math.max(-1.2, Math.min(1.2, cameraPitch + (event.clientY - dragState.y) * 0.009));
      dragState = { pointerId: event.pointerId, x: event.clientX, y: event.clientY };
      renderManifold();
    });
    const endDrag = (event) => {
      if (dragState?.pointerId === event.pointerId) dragState = null;
    };
    manifoldCanvas.addEventListener("pointerup", endDrag);
    manifoldCanvas.addEventListener("pointercancel", endDrag);
    if (query.get("trace") === "vpd") setActiveTrace(window.GodelVpdTraceData, "vpd");
    else updateTraceControls(traceSample());
    manifoldAnimationFrame = requestAnimationFrame(animateManifold);
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
    setTracePlaying(false);
    const start = current.slice();
    const destination = model.clampTuple(tuple);
    if (model.distance5D(start, destination) < 1e-9) return;
    if (keepHistory) previous = start;
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
      setTracePlaying(false);
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

  buildAnchorButtons();
  setupManifold();
  render();
  setupStudy();
  window.GodelCharacterLab = Object.freeze({
    getTuple: () => current.slice(),
    getState: () => ({ ...model.characterState(current), sequence: Math.max(0, stateSequence - 1) }),
    getCondition: () => document.body.dataset.condition || "embodied",
    getStudyReceipt: () => studySession ? studySession.receipt() : null,
    getTraceState: () => ({
      trace_id: activeTrace.id,
      semantics: activeTrace.semantics,
      alignment_status: activeTrace.alignment.status,
      cursor: traceCursor,
      playing: tracePlaying,
      frame: traceSample()
    }),
    loadTrace: (trace) => {
      setActiveTrace(trace, "custom");
      setTracePlaying(false);
      return activeTrace;
    },
    setTracePlaying,
    setTraceTime: (cursor) => {
      traceCursor = Math.max(0, Math.min(activeTrace.frames.length - 1, Number(cursor)));
      setTracePlaying(false);
      return applyTraceFrame();
    }
  });
})();
