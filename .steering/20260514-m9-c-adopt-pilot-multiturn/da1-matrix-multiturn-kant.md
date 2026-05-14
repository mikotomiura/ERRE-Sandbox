# DA-1 4-axis matrix - m9-c-adopt-pilot-multiturn investigation

| condition | Vendi semantic | ICC(C,k) | Burrows |
|---|---|---|---|
| historical baseline (Ollama, multi-turn metadata) | 30.822 [30.726, 30.928] | 0.9980 [0.9974, 0.9987] | 108.534 [108.100, 109.018] |
| matched baseline (historical, downsampled) | 31.167 [31.010, 31.318] | 0.9980 [0.9974, 0.9987] | 109.710 [109.036, 110.544] |
| no-LoRA SGLang control (multi-turn protocol) | 33.311 [33.121, 33.501] | 0.9819 [0.9760, 0.9936] | 115.101 [113.930, 116.272] |
| single-turn pilot LoRA r=4 (PR #165) | 33.895 [33.849, 33.942] | 0.9792 [0.9666, 0.9941] | 113.595 [113.261, 113.929] |
| single-turn pilot LoRA r=8 (PR #165) | 34.701 [34.673, 34.729] | 0.9843 [0.9795, 0.9946] | 113.723 [113.314, 114.131] |
| single-turn pilot LoRA r=16 (PR #165) | 33.685 [33.088, 34.282] | 0.9837 [0.9810, 0.9936] | 112.564 [112.307, 112.822] |
| multi-turn pilot LoRA r=4 (–{ PR) | 33.556 [33.259, 33.852] | 0.9804 [0.9732, 0.9933] | 115.612 [115.542, 115.681] |
| multi-turn pilot LoRA r=8 (–{ PR) | 33.757 [33.555, 33.958] | 0.9797 [0.9762, 0.9914] | 114.141 [113.257, 115.024] |
| multi-turn pilot LoRA r=16 (–{ PR) | 33.261 [33.202, 33.319] | 0.9913 [0.9892, 0.9975] | 114.609 [112.404, 116.813] |

## Pre-registered scenario verdict (DA-13)

{
  "primary_rank": 8,
  "scenario": "II",
  "rationale": "No reversal \u2014 LoRA failure remains the live hypothesis",
  "primary_vendi_diff_point": 2.589297653725872,
  "primary_vendi_diff_lo": 1.8231651624294045,
  "primary_vendi_diff_hi": 3.385287895202982,
  "primary_vendi_cohens_d": 2.169112474729427,
  "primary_burrows_reduction_point": -0.04038246129395746,
  "primary_burrows_reduction_lo": -0.05457830345970096,
  "sister_ranks_aligned": 0
}
