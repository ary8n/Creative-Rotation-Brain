# Allocation policy

`policy.py` implements a deterministic contextual allocator with the assessment protocol's `Policy(creatives, daily_budget, seed)` / `allocate(day, history)` interface. It receives creative metadata and reported history only. It does not import the simulator, load configuration, or inspect files. It ignores rows from the current or a future day, unknown IDs, malformed or negative metrics, and duplicate `(day, creative_id)` rows (keeping the last occurrence). A zero-spend row contributes no revenue evidence.

## Allocation method

For each creative, the policy estimates revenue per dollar from a global prior, then gently adjusts that prior using format and hook category evidence. The metadata log weight is 0.10, and category rates are shrunk toward the global rate with $1,000 prior spend. Creative lifetime performance is shrunk toward the resulting prior with $800 pseudo-spend. A trailing seven-day estimate is shrunk toward lifetime performance with $250 prior spend and blended into the lifetime estimate with a maximum 0.60 weight. This makes recent reported outcomes matter without treating a small recent sample as decisive. A modest 0.15 uncertainty bonus decays with observed spend.

The policy reserves $8 per never-served creative and $2 per previously served creative, then distributes the remainder in proportion to the seventh power of the adjusted rate score. Individual daily allocations are capped at 20% of account budget ($400 at the assessment budget); excess is redistributed. The result is returned as shares summing to one. These constants are policy choices, not simulator ground truth. The constructor's seed is retained for protocol compatibility; the policy is deterministic and does not sample random outcomes.

## Historical checks informing choices

`python3 analysis/policy_signal_validation.py` reproduces the checks in `artifacts/policy_signal_validation.json`. For 40 served creatives, fitting on days 1–45 and holding out days 46–60 ($26,965.34 held-out spend), the weak metadata prior changed spend-weighted ROAS RMSE from 0.98978 (global prior) to 0.98738. The reduction is 0.00240, about 0.24%; this is weak evidence in favor of keeping a small metadata weight, not evidence of a causal format or hook effect. Never-served creatives are not included as observed outcomes; their score uses only these uncertain metadata priors plus a small discovery floor.

For an age-decay check, a log-decay coefficient of 0.016/day was selected using days 31–45 after fitting days 1–30, then checked on days 46–60. On the same 40 creatives and held-out spend, spend-weighted RMSE increased from 0.48119 without decay to 0.53073 with decay (10.3% worse), so this policy has no explicit age penalty. Unweighted RMSE improved, illustrating that the conclusion depends on the spend-weighted target chosen in advance. This check is predictive and observational; it does not isolate creative fatigue causally.

## Simulated evaluation

Reproduce the frozen 20-seed paired run with:

```sh
python3 -m unittest discover -s tests -v
python3 evaluate.py --seeds 20 --seed-start 3000
```

The evaluator uses the same seed-level environments for B1 uniform, B2 windowed-greedy, this policy, and the clairvoyant benchmark. On seeds 3000–3019, cumulative revenue was:

| Scenario | B1 uniform | B2 greedy | This policy | Clairvoyant | Policy − B1 paired 95% CI | Policy − B2 paired 95% CI | Capture* |
|---|---:|---:|---:|---:|---:|---:|---:|
| Baseline | $84,353 ($81,446–$87,260) | $99,413 ($93,134–$105,693) | $117,291 ($109,384–$125,198) | $143,036 ($127,434–$158,637) | +$32,938 ($27,445–$38,431) | +$17,878 ($15,706–$20,050) | 0.561 |
| Faster fatigue | $61,029 ($58,584–$63,474) | $76,079 ($70,037–$82,122) | $89,167 ($81,467–$96,866) | $119,996 ($104,131–$135,861) | +$28,138 ($22,511–$33,764) | +$13,088 ($11,052–$15,123) | 0.477 |
| Greater uncertainty | $82,829 ($78,900–$86,759) | $111,094 ($100,528–$121,660) | $130,418 ($116,582–$144,254) | $179,461 ($143,589–$215,333) | +$47,589 ($37,139–$58,038) | +$19,324 ($15,858–$22,789) | 0.492 |

Parentheses are 95% t intervals across 20 seed-level cumulative outcomes; paired-difference intervals use within-seed differences. Mean spend was about $56.0k per policy over the 30 days, with 93.4–93.6% utilization. Policy ROAS was 2.092 baseline, 1.591 faster-fatigue, and 2.326 greater-uncertainty. *Capture is `(policy mean revenue − B1 mean revenue) / (clairvoyant mean revenue − B1 mean revenue)`.

These are results inside the configured simulator. They do not establish real-world advertising lift. The learned historical rates are observational and confounded by prior allocation; the simulator assumes a particular concave spend response, static latent creative quality with configured noise, fatigue process, delivery under-spend, and market dynamics. The policy's seventh-power score concentration and fixed floors/cap are heuristic choices. Robustness scenarios vary selected assumptions but do not span all plausible environments. The clairvoyant knows sampled latent effectiveness and current state, but not future random shocks; it is an in-model reference, not an achievable policy.
