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

## Entry — 2026-11-12 19:38 Asia/Kolkata

### Milestone 2 implementation and evidence

Implemented a 30-day simulator and paired benchmark loop. `config.json` holds all simulator calibration and scenario parameters; initial policy history uses the reported day-60 snapshot, while simulator calibration uses final outcomes. Policy-facing rows contain only protocol fields from days strictly before the decision day. The simulator offers no policy-facing ground-truth/config accessor; the clairvoyant benchmark is the only component given the environment object.

Served creative rates use the preregistered observational data with $1,000 prior-spend shrinkage toward account ROAS. Ten unserved creatives receive format/hook priors and higher log-scale uncertainty, with no fabricated outcome records. Delivery calibration separates empirical row under-delivery frequency/factor range from an assumed daily account-pacing multiplier to reconcile mean row-level delivery (0.9854) with the observed budget-weighted utilization (0.9370); this decomposition is not identified by the files. The concave spend-response elasticity (0.12 baseline), fatigue rates, market noise and uncertainty expansion remain assumptions. They are configurable and documented in `SIMULATION.md`.

`python3 -m unittest discover -s tests -v`: 10 tests pass, covering reproducibility, budget constraints, cold starts, zero/sub-dollar spend, the 30-day sequence, all three benchmark allocations, nonnegative and internally consistent outcomes, and no future rows in policy history. `python3 evaluate.py --seeds 20` completed for baseline, faster-fatigue, and greater-uncertainty scenarios. Across each scenario's paired seeds, B2's mean cumulative revenue difference from B1 was positive with its 95% paired t interval above zero:

- Baseline: B1 $85,548 (95% CI $83,576–$87,519); B2 $106,277 ($97,581–$114,974); clairvoyant $163,881 ($138,629–$189,133); B2−B1 +$20,729 ($13,678–$27,780). Mean budget utilization was 93.3–93.6%.
- Faster fatigue: B1 $62,203 ($60,291–$64,116); B2 $83,514 ($75,026–$92,002); clairvoyant $138,189 ($113,202–$163,175); B2−B1 +$21,311 ($14,424–$28,197).
- Greater uncertainty: B1 $85,553 ($82,107–$88,999); B2 $123,848 ($107,288–$140,408); clairvoyant $222,508 ($158,613–$286,403); B2−B1 +$38,295 ($24,919–$51,670).

These are model-conditional benchmark results, not evidence of real-world lift. The clairvoyant interval widens sharply under greater creative uncertainty, as expected when it can identify each sampled world's winners. The candidate policy and normalized capture metric remain unimplemented and unmeasured. Historical holdout validation remains future work; this milestone evaluates the simulated environment only.

## Entry — 2026-11-12 19:42 Asia/Kolkata

### Correction to Milestone 2 oracle evaluation

The preceding implementation note recorded preliminary clairvoyant values from an oracle that forced at least $1 onto every creative. Review found that this could waste budget where activating a low-value creative was inferior to investing in an already active one. The oracle now compares the $1 activation value with the budget's marginal value, and can leave creatives inactive. B1/B2 results and paired B2−B1 differences are unchanged. The final regenerated `artifacts/simulation_benchmarks.json` and CSVs use the corrected oracle; the daily CSV also includes ROAS intervals.

- Baseline clairvoyant: $165,945 cumulative revenue (95% CI $140,153–$191,738); mean spend $56,153; ROAS 2.954; utilization 93.6%; paired oracle−B1 difference +$80,397 (95% CI $55,806–$104,989).
- Faster fatigue clairvoyant: $140,383 ($114,889–$165,877); mean spend $56,080; ROAS 2.502; utilization 93.5%; paired oracle−B1 +$78,179 (95% CI $53,955–$102,404).
- Greater uncertainty clairvoyant: $225,856 ($160,589–$291,124); mean spend $56,058; ROAS 4.025; utilization 93.4%; paired oracle−B1 +$140,303 (95% CI $77,793–$202,814).

These corrected oracle results still depend on a simulated diminishing-return curve and perfect knowledge of sampled latent creative effectiveness. Their gap from B1 is an upper-bound diagnostic within this model, not a forecast of recoverable real-world revenue.
