(function (root, factory) {
  const value = factory();
  if (typeof module === "object" && module.exports) module.exports = value;
  root.GodelCharacterSpace = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  return Object.freeze({
    schemaVersion: 1,
    experimentId: "godel_globes_5d_character_lab_v1",
    tupleOrder: ["wonder", "play", "care", "resolve", "reflection"],
    dimensions: [
      {
        id: "wonder",
        label: "Wonder",
        anatomy: "left-wing",
        channel: "lift and reach",
        low: "familiar",
        high: "marvel-seeking"
      },
      {
        id: "play",
        label: "Play",
        anatomy: "left-wing",
        channel: "curl and sparks",
        low: "solemn",
        high: "mischievous"
      },
      {
        id: "care",
        label: "Care",
        anatomy: "right-wing",
        channel: "shelter and roundness",
        low: "self-contained",
        high: "protective"
      },
      {
        id: "resolve",
        label: "Resolve",
        anatomy: "right-wing",
        channel: "reach and edge",
        low: "yielding",
        high: "unyielding"
      },
      {
        id: "reflection",
        label: "Reflection",
        anatomy: "head",
        channel: "halo and orbit",
        low: "immediate",
        high: "contemplative"
      }
    ],
    projection: {
      method: "fixed-pca-v1",
      mean: [0.61833333, 0.535, 0.65666667, 0.63583333, 0.66583333],
      matrix: [
        [0.28715722, 0.71691402, -0.29476615, -0.1898144, -0.52977206],
        [0.06489911, 0.13779627, 0.68698427, -0.70456777, 0.09185409]
      ],
      fittedExplainedVariance: 0.7927245741,
      note: "The 2D salon map is a navigation projection of the twelve authored anchors, not literal model geometry."
    },
    anchors: [
      {
        id: "seedling",
        name: "Seedling",
        tuple: [0.50, 0.50, 0.50, 0.50, 0.50],
        blurb: "Balanced and ready to grow in any direction."
      },
      {
        id: "lantern-scout",
        name: "Lantern Scout",
        tuple: [0.88, 0.62, 0.70, 0.60, 0.68],
        blurb: "Curious, companionable, and willing to cross the hedge."
      },
      {
        id: "hearthkeeper",
        name: "Hearthkeeper",
        tuple: [0.55, 0.30, 0.95, 0.72, 0.82],
        blurb: "Protective warmth guided by patient judgment."
      },
      {
        id: "hedge-trickster",
        name: "Hedge Trickster",
        tuple: [0.92, 0.95, 0.42, 0.48, 0.40],
        blurb: "Fast wonder, bright jokes, and a taste for side doors."
      },
      {
        id: "root-scholar",
        name: "Root Scholar",
        tuple: [0.72, 0.22, 0.62, 0.55, 0.97],
        blurb: "Deeply reflective, quietly curious, and hard to rush."
      },
      {
        id: "storm-warden",
        name: "Storm Warden",
        tuple: [0.42, 0.28, 0.52, 0.96, 0.66],
        blurb: "Steady under pressure and decisive at the boundary."
      },
      {
        id: "meadow-friend",
        name: "Meadow Friend",
        tuple: [0.68, 0.78, 0.90, 0.32, 0.48],
        blurb: "Playful company with an instinct to include."
      },
      {
        id: "river-mediator",
        name: "River Mediator",
        tuple: [0.62, 0.44, 0.88, 0.58, 0.88],
        blurb: "Patient care that keeps moving toward an answer."
      },
      {
        id: "ember-rogue",
        name: "Ember Rogue",
        tuple: [0.58, 0.86, 0.32, 0.90, 0.38],
        blurb: "Restless play backed by sharp resolve."
      },
      {
        id: "moon-archivist",
        name: "Moon Archivist",
        tuple: [0.35, 0.20, 0.75, 0.78, 0.92],
        blurb: "A careful keeper of memory and consequence."
      },
      {
        id: "sky-cartographer",
        name: "Sky Cartographer",
        tuple: [0.82, 0.55, 0.48, 0.82, 0.72],
        blurb: "Maps the unknown, then chooses a route through it."
      },
      {
        id: "moss-companion",
        name: "Moss Companion",
        tuple: [0.38, 0.72, 0.84, 0.42, 0.58],
        blurb: "Gentle humor, close attention, and low stakes."
      }
    ],
    ontologyBoundary: {
      retailOnly: true,
      parameterCountIsNotCharacter: true,
      restrictedAnchorTerms: ["jinn", "beast", "dabbat", "dabbah", "al-ard"],
      note: "Named theological entities are not generic personality presets. They require a separate lore and review layer."
    }
  });
});
