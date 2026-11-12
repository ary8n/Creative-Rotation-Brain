# Preregistration

## Entry — 2026-11-12 19:05 Asia/Kolkata

This is the initial entry. Later changes must be appended with a new timestamp; this entry is retained as written.

### Objective

Maximize cumulative attributed revenue over the 30-day evaluation horizon, allocating $2,000 per day. Revenue is the primary objective because contribution margin data is unavailable. Also report actual delivered spend, revenue/spend ROAS, and budget utilization (delivered spend / allocated budget). A revenue increase is not by itself evidence of profit improvement.

### Reverified data evidence

`python3 analysis/audit.py` reproduces these calculations from the four supplied CSVs. Full schemas, row-level creative/group summaries, temporal summaries, and plots are in `artifacts/`.

- The two daily exports each contain 1,784 unique `(day, creative_id)` rows over days 1–60 and 40 creatives. They have the same keys; budget, spend, impressions, and clicks match on every row. Between reported and final, purchases change on 84/1,784 rows, increasing 2,972 to 3,114 (+142); revenue changes on 156/1,784 rows, increasing $192,941.59 to $201,894.67 (+$8,953.08, +4.64%). Every changed purchase or revenue row is in days 46–60 (600 rows); none is in days 1–45. Calculation: key-match rows, compare values, and sum deltas. Evidence: `artifacts/audit_summary.json` (`reported_vs_final`) and `artifacts/creative_roas.svg`.
- Final creative cumulative ROAS is revenue summed per creative divided by spend summed per creative. Across 40 served creatives: mean 1.426, median 1.243, nearest-rank p25 0.956, p75 1.763, range 0.605–4.153; 29/40 exceed 1, 13/40 exceed 1.5, and 8/40 exceed 2. Individual sample sizes and spend are in `artifacts/creative_performance.csv`. These unequal observational exposures do not imply causal creative effects.
- Format ROAS (pooled revenue / pooled spend) and sample sizes: video_15s 1.952 (5 creatives, 201 rows); carousel 1.939 (5, 196); video_30s 1.936 (10, 471); story 1.699 (10, 461); static_image 1.519 (10, 455). Hook ROAS: ugc_testimonial 2.386 (7, 253); social_proof 1.927 (5, 238); urgency 1.937 (7, 292); founder_story 1.840 (4, 240); benefit_led 1.444 (5, 223); problem_solution 1.064 (6, 233); curiosity 0.973 (6, 305). Values and spend are in `artifacts/group_performance.csv`; plots are `artifacts/format_roas.svg` and `artifacts/hook_roas.svg`. These are pooled descriptive associations with uneven spend and creative counts, not controlled format or hook effects.
- Weekly pooled final ROAS by days 1–7 through 57–60 is 2.113, 1.954, 1.702, 1.717, 1.637, 1.672, 1.799, 1.776, 1.798 (rows per block: 96, 128, 161, 194, 226, 259, 280, 280, 160). First 10 days: $39,979.40 revenue / $18,703.04 spend = 2.138; last 10: $31,749.05 / $18,117.88 = 1.752. By creative age, ages 0–6 have 2.111 ROAS (280 rows, 40 creatives, $24,774.19 spend); ages 28–60 have 1.452 (704 rows, 32 creatives, $27,252.01 spend). These are observed patterns, not proof of fatigue or other causes. Evidence: `artifacts/weekly_performance.csv`, `artifacts/creative_age_performance.csv`, `artifacts/weekly_roas.svg`.
- Allocated budget totals $119,982.60 and delivered spend $112,423.51 across 1,784 rows: 93.70% utilization and $7,559.09 below allocation. Spend equals budget in 1,689 rows, is lower in 95, and is higher in 0. Daily allocated totals have median $1,999.96 (60 days); daily spend median is $1,876.72. Evidence: `spend_vs_budget` in `artifacts/audit_summary.json`.
- There are 50 listed creatives: 40 served and 10 never served. No outcomes exist for those 10, so this history cannot identify their performance. Among the 40 served creatives, the first seven observed days range from 0.000 to 4.998 ROAS; this is noisy evidence even for launched creatives, not a validated cold-start predictor. Evidence: `artifacts/creative_first7.csv`.
- Competitor data contains 22 launch records across 6 brands, 4 platforms, 5 formats, and 7 hook types, without competitor delivery or outcome results. Of the 29 unique served-creative launch days, 13 coincide with a competitor launch and 28 are within three days of one. This dense timing and lack of competitor outcomes do not establish incremental predictive value. Evidence: `competitors` in `artifacts/audit_summary.json`.
- Quality checks find no missing cells in the four CSVs, duplicate daily keys, negative daily metric values, clicks above impressions, purchases above clicks, or mismatch between zero/nonzero purchases and revenue. There are 91 zero-budget/zero-spend daily rows. These checks do not validate attribution or the simulator's counterfactual delivery assumptions.

### Evaluation strategy

Build a historically calibrated simulated delivery environment. Use historical observations to inform plausible performance distributions, creative priors, delivery behavior, and temporal dynamics; the simulator will generate counterfactual outcomes for alternative allocations. Simulator ground truth will live in a separate configuration file. `policy.py` will not read that configuration or import the simulator and will use only data available through the assessment protocol. Compare our policy, B1 uniform allocation, B2 exactly as specified in `BRIEF.md` (trailing seven-day objective per dollar; population mean for creatives under 2,000 trailing impressions or zero trailing spend; top five split 75% equally and the rest split 25% equally), and a clairvoyant benchmark allowed to access simulator ground truth. Give all policies identical environments and random seeds. Report cumulative revenue, spend, ROAS, budget utilization, and uncertainty intervals across multiple seeds, plus the prescribed `(ours - B1) / (clairvoyant - B1)` when meaningful.

Supplement simulation with time-based historical validation: fit/calibrate only from earlier history and score a later held-out period; report both exports' outcome revision behavior and avoid treating later-finalized values as information available on earlier decision dates. Historical validation is observational and cannot establish counterfactual revenue under a changed allocation. Simulated improvements establish performance only under modeled assumptions, not proven real-world advertising improvements.

### Implementation order

1. Reproducible historical data analysis.
2. Small configurable simulation environment.
3. Delivery and outcome generation.
4. Uniform, greedy, and clairvoyant baselines.
5. Independent `policy.py`.
6. Multi-seed evaluation and uncertainty intervals.
7. Robustness checks, tests, and README.

### Falsification and course-change criteria

- **Metadata priors:** discard metadata weighting if it fails to improve held-out prediction over a global prior.
- **Creative fatigue:** remove age-dependent decay if it fails to improve held-out prediction.
- **Exploration:** reduce or change exploration if it consistently harms revenue without improving cold-start discovery.
- **Competitor signal:** exclude unless it demonstrates incremental out-of-sample predictive value over a no-competitor model.
- **Simulator:** implement and compare alternative plausible dynamics; do not trust a conclusion that disappears under minor assumption changes.
- **Allocation policy:** simplify or revise it if it cannot consistently outperform both baselines across multiple seeds within uncertainty intervals.
- **Historical revisions:** if late corrections materially alter model selection or rankings, use the as-known snapshots/available reported values in validation and widen the uncertainty acknowledged for late outcomes.

### Deliberately excluded

Deep reinforcement learning; real-time competitor scraping; production advertising integrations; complex dashboards; unnecessary abstractions and frameworks.
