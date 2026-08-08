(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.SLLEssay = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const CHAPTERS = ["sheets", "loops", "levers", "synthesis"];

  function motifById(data, id) {
    return data.motifs.find((motif) => motif.id === id) || data.motifs[0];
  }

  function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
  }

  function dot(left, right) {
    return left.reduce((sum, value, index) => sum + value * right[index], 0);
  }

  function matVec(matrix, vector) {
    return matrix.map((row) => dot(row, vector));
  }

  function matMul(left, right) {
    return left.map((row) => right[0].map((_, column) => row.reduce((sum, value, index) => sum + value * right[index][column], 0)));
  }

  function transpose(matrix) {
    return matrix[0].map((_, column) => matrix.map((row) => row[column]));
  }

  function softmax(values) {
    const peak = Math.max(...values);
    const exponentials = values.map((value) => Math.exp(value - peak));
    const total = exponentials.reduce((sum, value) => sum + value, 0);
    return exponentials.map((value) => value / total);
  }

  function normalize(vector) {
    const length = Math.sqrt(dot(vector, vector)) || 1;
    return vector.map((value) => value / length);
  }

  function ablationState(data, alpha) {
    const spec = data.ablation_case;
    const motif = motifById(data, spec.motif_id);
    const amount = clamp(alpha, 0, 1);
    const u = normalize(spec.direction_u);
    const beforePoint = motif.depth_points[spec.depth];
    const before = [beforePoint.x, beforePoint.y, beforePoint.z];
    const operator = u.map((rowValue, row) => u.map((columnValue, column) => (row === column ? 1 : 0) - amount * rowValue * columnValue));
    const current = matVec(operator, before);
    const removed = before.map((value, index) => value - current[index]);
    const beforeCoefficient = dot(u, before);
    const currentCoefficient = dot(u, current);
    const association = normalize(matVec(operator, motif.association));
    const returnedAssociation = matVec(motif.holonomy.matrix, association);
    const associationReturnCosine = dot(association, returnedAssociation);
    const gramian = matMul(matMul(operator, motif.control.gramian), transpose(operator));
    const actionEnergy = dot(u, matVec(gramian, u));
    const baselineEnergy = dot(u, matVec(motif.control.gramian, u));
    const logits = spec.readout.weights.map((weights, index) => dot(weights, current) + spec.readout.bias[index]);
    const probabilities = softmax(logits);
    const winnerIndex = probabilities.indexOf(Math.max(...probabilities));
    const roundVector = (vector) => vector.map((value) => Number(value.toFixed(4)));
    return {
      case_id: spec.id,
      alpha: Number(amount.toFixed(3)),
      target: { motif_id: spec.motif_id, depth: spec.depth },
      operator: spec.operator,
      activation: { before: roundVector(before), current: roundVector(current), removed: roundVector(removed) },
      direction_coefficient: { before: Number(beforeCoefficient.toFixed(4)), current: Number(currentCoefficient.toFixed(4)) },
      transported_association_return_cosine: Number(associationReturnCosine.toFixed(4)),
      registered_action_energy: { before: Number(baselineEnergy.toFixed(4)), current: Number(actionEnergy.toFixed(4)) },
      behavior: {
        labels: spec.readout.labels,
        logits: roundVector(logits),
        probabilities: roundVector(probabilities),
        winner: spec.readout.labels[winnerIndex],
        response: spec.responses[spec.readout.labels[winnerIndex]],
      },
      claim_boundary: spec.claim_boundary,
    };
  }

  function axisAngle(axis, angle) {
    const norm = Math.sqrt(dot(axis, axis)) || 1;
    const [x, y, z] = axis.map((value) => value / norm);
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    const t = 1 - c;
    return [
      [t * x * x + c, t * x * y - s * z, t * x * z + s * y],
      [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
      [t * x * z - s * y, t * y * z + s * x, t * z * z + c],
    ];
  }

  function transportedFrame(motif, phase) {
    const rotation = axisAngle(
      motif.holonomy.axis,
      (motif.holonomy.angle_degrees * Math.PI / 180) * clamp(phase, 0, 1)
    );
    return [matVec(rotation, [1, 0, 0]), matVec(rotation, [0, 1, 0]), matVec(rotation, [0, 0, 1])];
  }

  function loopPoint(motif, phase) {
    const points = motif.loop_points;
    const scaled = clamp(phase, 0, 1) * (points.length - 1);
    const left = Math.floor(scaled);
    const right = Math.min(points.length - 1, left + 1);
    const mix = scaled - left;
    return {
      x: points[left].x * (1 - mix) + points[right].x * mix,
      y: points[left].y * (1 - mix) + points[right].y * mix,
      z: points[left].z * (1 - mix) + points[right].z * mix,
    };
  }

  function bandRmsDistance(left, right, center, radius) {
    const low = Math.max(0, center - radius);
    const high = Math.min(left.depth_points.length - 1, center + radius);
    let squared = 0;
    let samples = 0;
    for (let layer = low; layer <= high; layer += 1) {
      const a = left.depth_points[layer];
      const b = right.depth_points[layer];
      squared += (a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2;
      samples += 3;
    }
    return Math.sqrt(squared / samples);
  }

  function gluingPartners(data, motifId, center, radius, epsilon) {
    const selected = motifById(data, motifId);
    return data.motifs
      .filter((motif) => motif.id !== selected.id)
      .map((motif) => ({
        id: motif.id,
        label: motif.label,
        distance: bandRmsDistance(selected, motif, center, radius),
      }))
      .filter((candidate) => candidate.distance <= epsilon)
      .sort((left, right) => left.distance - right.distance);
  }

  function snapshot(data, state) {
    const motif = motifById(data, state.motifId);
    const chapter = CHAPTERS.includes(state.chapter) ? state.chapter : "sheets";
    const partners = gluingPartners(data, motif.id, state.depth, data.etale.window_radius, data.etale.epsilon);
    const nextActions = {
      sheets: "Capture globally normalized activations for the same targets and recompute chart overlaps.",
      loops: "Register the same activation subspace around a real closed prompt or recurrent cycle.",
      levers: "Estimate B with intervention repeats, singular-value uncertainty, and abstention.",
      synthesis: "Test whether sheet convergence predicts transported control compatibility on held-out inputs.",
    };
    return {
      schema_version: "sheets_loops_levers_agent_snapshot.v1",
      evidence_class: data.evidence_class,
      fixture_sha256: data.fixture_sha256,
      chapter,
      selection: { motif_id: motif.id, label: motif.label, depth: state.depth, phase: Number(state.phase.toFixed(3)) },
      sheets: {
        base: data.etale.base_topology,
        chart_window: [Math.max(0, state.depth - data.etale.window_radius), Math.min(27, state.depth + data.etale.window_radius)],
        epsilon: data.etale.epsilon,
        gluing_partners: partners.map((item) => ({ id: item.id, rms_distance: Number(item.distance.toFixed(4)) })),
      },
      loops: {
        base: data.time.base_topology,
        holonomy_angle_degrees: motif.holonomy.angle_degrees,
        association_return_cosine: motif.holonomy.association_return_cosine,
      },
      levers: {
        registered_action_rank: motif.control.rank,
        normalized_margin: motif.control.normalized_margin,
        holonomy_coupling: motif.control.holonomy_coupling,
        status: motif.control.normalized_margin > 0.05 ? "resolved" : "abstain_on_measured_B",
      },
      ablation: ablationState(data, state.ablationAlpha == null ? 0 : state.ablationAlpha),
      confirmation: data.confirmation,
      claim_boundary: data.claim_boundary,
      next_evidence_action: nextActions[chapter],
    };
  }

  return {
    CHAPTERS,
    ablationState,
    axisAngle,
    bandRmsDistance,
    gluingPartners,
    loopPoint,
    matVec,
    motifById,
    snapshot,
    transportedFrame,
  };
});
