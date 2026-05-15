# DA-1 4-axis matrix - m9-c-adopt-pilot-multiturn investigation

| condition | Vendi semantic | ICC(C,k) | Burrows |
|---|---|---|---|
| historical baseline (Ollama, multi-turn metadata) | 30.822 [30.726, 30.928] | 0.9980 [0.9974, 0.9987] | 108.534 [108.100, 109.018] |
| matched baseline (historical, downsampled) | 31.167 [31.010, 31.318] | 0.9980 [0.9974, 0.9987] | 109.710 [109.036, 110.544] |
| no-LoRA SGLang control (multi-turn protocol) | 33.311 [33.121, 33.501] | 0.9819 [0.9760, 0.9936] | 115.101 [113.930, 116.272] |
| single-turn pilot LoRA r=8 (PR #165) | 34.701 [34.673, 34.729] | 0.9843 [0.9795, 0.9946] | 113.723 [113.314, 114.131] |
| multi-turn pilot LoRA r=8 (–{ PR) | 33.183 [32.931, 33.434] | 0.9831 [0.9751, 0.9951] | 114.608 [113.658, 115.558] |

## Pre-registered scenario verdict (DA-13)

{
  "primary_rank": 8,
  "scenario": "II",
  "rationale": "No reversal \u2014 LoRA failure remains the live hypothesis",
  "primary_vendi_diff_point": 2.0155055489451357,
  "primary_vendi_diff_lo": 1.1081728964450086,
  "primary_vendi_diff_hi": 2.8679869527316946,
  "primary_vendi_cohens_d": 1.6365203415640008,
  "primary_burrows_reduction_point": -0.044639220799059964,
  "primary_burrows_reduction_lo": -0.05944127279275,
  "sister_ranks_aligned": 0
}
