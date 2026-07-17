(function (root, factory) {
  const value = factory();
  if (typeof module === "object" && module.exports) module.exports = value;
  root.GodelVpdTraceData = value;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  return Object.freeze({
  "alignment": {
    "note": "Actual low-rank refinement measurements. These five mechanical channels are not certified Wonder, Play, Care, Resolve, or Reflection directions.",
    "status": "uncalibrated"
  },
  "axes": [
    {
      "id": "residual_mix",
      "label": "Residual mix",
      "raw_range": [
        0.0,
        5.4637192500000005
      ],
      "raw_unit": "mean singular value",
      "unit": "min-max normalized within trace"
    },
    {
      "id": "value_path",
      "label": "Value path",
      "raw_range": [
        0.0,
        2.61626825
      ],
      "raw_unit": "mean singular value",
      "unit": "min-max normalized within trace"
    },
    {
      "id": "routing",
      "label": "Routing stabilizer",
      "raw_range": [
        1.97593525,
        2.6163805
      ],
      "raw_unit": "mean singular value",
      "unit": "min-max normalized within trace"
    },
    {
      "id": "mean_output_delta",
      "label": "Mean output delta",
      "raw_range": [
        0.00739288330078125,
        0.06988525390625
      ],
      "raw_unit": "absolute logit delta",
      "unit": "min-max normalized within trace"
    },
    {
      "id": "peak_output_delta",
      "label": "Peak output delta",
      "raw_range": [
        0.068359375,
        0.264404296875
      ],
      "raw_unit": "absolute logit delta",
      "unit": "min-max normalized within trace"
    }
  ],
  "frames": [
    {
      "label": "Layer 0",
      "metadata": {
        "chunk_index": 0,
        "layer": 0
      },
      "raw": [
        1.9761389999999999,
        2.613358875,
        1.9776682499999998,
        0.01702880859375,
        0.158203125
      ],
      "t": 0,
      "values": [
        0.3616838475000339,
        0.9988879676233504,
        0.0027059299760592535,
        0.15419362715175192,
        0.45828144458281445
      ]
    },
    {
      "label": "Layer 1",
      "metadata": {
        "chunk_index": 1,
        "layer": 1
      },
      "raw": [
        0.0,
        2.6139735,
        2.1900538333333333,
        0.0083770751953125,
        0.068359375
      ],
      "t": 1,
      "values": [
        0.0,
        0.9991228919282265,
        0.3343276936370958,
        0.015748992796972287,
        0.0
      ]
    },
    {
      "label": "Layer 2",
      "metadata": {
        "chunk_index": 2,
        "layer": 2
      },
      "raw": [
        1.9785645,
        0.0,
        2.2987005,
        0.01071929931640625,
        0.091796875
      ],
      "t": 2,
      "values": [
        0.36212777587354983,
        0.0,
        0.5039700895587871,
        0.05322915394945672,
        0.11955168119551682
      ]
    },
    {
      "label": "Layer 3",
      "metadata": {
        "chunk_index": 3,
        "layer": 3
      },
      "raw": [
        3.0211039166666667,
        0.0,
        1.9847264999999998,
        0.0211181640625,
        0.1981201171875
      ],
      "t": 3,
      "values": [
        0.5529390838789285,
        0.0,
        0.013726778362396797,
        0.21963130264924918,
        0.661892901618929
      ]
    },
    {
      "label": "Layer 4",
      "metadata": {
        "chunk_index": 4,
        "layer": 4
      },
      "raw": [
        1.979973,
        0.0,
        2.1904418333333333,
        0.01535797119140625,
        0.1614990234375
      ],
      "t": 4,
      "values": [
        0.36238556730381044,
        0.0,
        0.3349335221602991,
        0.12745696496154316,
        0.475093399750934
      ]
    },
    {
      "label": "Layer 5",
      "metadata": {
        "chunk_index": 5,
        "layer": 5
      },
      "raw": [
        0.0,
        2.61052325,
        2.1936352500000003,
        0.0084381103515625,
        0.0703125
      ],
      "t": 5,
      "values": [
        0.0,
        0.9978041242521671,
        0.3399197667560189,
        0.01672567452081553,
        0.009962640099626401
      ]
    },
    {
      "label": "Layer 6",
      "metadata": {
        "chunk_index": 6,
        "layer": 6
      },
      "raw": [
        1.9830055,
        2.608807,
        2.61199125,
        0.01349639892578125,
        0.11328125
      ],
      "t": 6,
      "values": [
        0.3629405921616488,
        0.9971481326503886,
        0.9931465648312638,
        0.09766817238432426,
        0.22914072229140722
      ]
    },
    {
      "label": "Layer 7",
      "metadata": {
        "chunk_index": 7,
        "layer": 7
      },
      "raw": [
        2.982886625,
        0.0,
        2.294750125,
        0.01788330078125,
        0.1591796875
      ],
      "t": 7,
      "values": [
        0.5459443445964028,
        0.0,
        0.4978019198362392,
        0.1678671712855573,
        0.46326276463262767
      ]
    },
    {
      "label": "Layer 8",
      "metadata": {
        "chunk_index": 8,
        "layer": 8
      },
      "raw": [
        1.98126275,
        2.60347475,
        2.294408875,
        0.01500701904296875,
        0.08984375
      ],
      "t": 8,
      "values": [
        0.362621624454807,
        0.9951100197772151,
        0.4972690874044265,
        0.12184104504944451,
        0.1095890410958904
      ]
    },
    {
      "label": "Layer 9",
      "metadata": {
        "chunk_index": 9,
        "layer": 9
      },
      "raw": [
        1.976508,
        2.613114,
        2.294621375,
        0.0145111083984375,
        0.115966796875
      ],
      "t": 9,
      "values": [
        0.36175138391307343,
        0.9987943705696081,
        0.49760088781984124,
        0.11390550604321817,
        0.24283935242839352
      ]
    },
    {
      "label": "Layer 10",
      "metadata": {
        "chunk_index": 10,
        "layer": 10
      },
      "raw": [
        1.9858924999999998,
        2.61165,
        2.6163805,
        0.01535797119140625,
        0.126953125
      ],
      "t": 10,
      "values": [
        0.3634689868078415,
        0.9982347949221185,
        1.0,
        0.12745696496154316,
        0.298879202988792
      ]
    },
    {
      "label": "Layer 11",
      "metadata": {
        "chunk_index": 11,
        "layer": 11
      },
      "raw": [
        0.0,
        2.6083625,
        2.1892824166666673,
        0.01056671142578125,
        0.09033203125
      ],
      "t": 11,
      "values": [
        0.0,
        0.9969782341699862,
        0.33312319307023874,
        0.05078744963984862,
        0.11207970112079702
      ]
    },
    {
      "label": "Layer 12",
      "metadata": {
        "chunk_index": 12,
        "layer": 12
      },
      "raw": [
        0.0,
        2.61626825,
        2.190546,
        0.00739288330078125,
        0.071044921875
      ],
      "t": 12,
      "values": [
        0.0,
        1.0,
        0.33509616942275683,
        0.0,
        0.0136986301369863
      ]
    },
    {
      "label": "Layer 13",
      "metadata": {
        "chunk_index": 13,
        "layer": 13
      },
      "raw": [
        1.97742175,
        2.612628,
        2.298718375,
        0.01258087158203125,
        0.12188720703125
      ],
      "t": 13,
      "values": [
        0.36191862347246334,
        0.998608609801384,
        0.5039979998290252,
        0.08301794652667562,
        0.27303860523038603
      ]
    },
    {
      "label": "Layer 14",
      "metadata": {
        "chunk_index": 14,
        "layer": 14
      },
      "raw": [
        2.900169875,
        2.6101965,
        1.97593525,
        0.06988525390625,
        0.264404296875
      ],
      "t": 14,
      "values": [
        0.5308050692758417,
        0.9976792326245597,
        0.0,
        1.0,
        1.0
      ]
    },
    {
      "label": "Layer 15",
      "metadata": {
        "chunk_index": 15,
        "layer": 15
      },
      "raw": [
        5.4637192500000005,
        2.61438025,
        2.297407875,
        0.0298004150390625,
        0.216796875
      ],
      "t": 15,
      "values": [
        1.0,
        0.9992783614600681,
        0.5019517671494951,
        0.3585642778659504,
        0.7571606475716065
      ]
    }
  ],
  "id": "hrm-text-1b-vpd-depth-trace-v1",
  "schema": "pixieology_manifold_trace_v1",
  "semantics": "mechanistic_normalized",
  "source": {
    "chunk_count": 16,
    "evidence_class": "actual_local_vpd_style_analysis",
    "generated_at_utc": "2026-05-20T11:10:36.523310+00:00",
    "method": "low_rank_svd_refinement",
    "model_id": "HRM-Text-1B",
    "source_name": "feature_map_refine_batch_summary.json",
    "summary_sha256": "257dfdeff84aa93403228192151d6b23310b6236421ff2464cbb970d5e951000"
  },
  "time": {
    "unit": "model depth (layer)"
  },
  "title": "HRM-Text 1B VPD-style depth trace"
});
});
