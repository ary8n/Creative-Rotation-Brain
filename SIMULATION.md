# Historical simulation

Run the benchmark suite with `python3 evaluate.py --seeds 20`. It evaluates the
baseline, faster-fatigue, and greater-uncertainty scenarios on paired seeds and
writes `artifacts/simulation_benchmarks.json`, summary CSV, and daily CSV
(including daily revenue, spend, ROAS, and budget-utilization intervals).
Run checks with `python3 -m unittest discover -s tests -v`.

## Calibration and assumptions

`config.json` contains simulator ground truth. `simulator.py` loads the 50
creative descriptions, but only benchmark code receives the environment object.
A future `policy.py` must receive protocol-shaped history and must not import the
simulator or read `config.json`.

Daily-final outcomes are used for calibration, including the values finalized
after day 60. For served creatives, cumulative revenue/spend is shrunk toward
the pooled account revenue/spend rate with a $1,000 prior-spend weight. The
uncertainty scale is an explicit assumption that decreases with observed spend;
each simulated world draws a mean-preserving lognormal creative rate around
that shrunken estimate. This is a distribution over counterfactual simulator
truth, not a claim that observed ROAS is a causal response curve.

The ten never-served creatives have no invented observations. Their central
rates are metadata priors: the geometric mean of format and hook ROAS, after
each category rate is shrunk toward the account rate with a $1,000 prior. Their
log-scale uncertainty is 0.65, higher than the served-creative assumptions.
These category differences are descriptive and may not predict cold starts.

Directly estimated inputs include account CPM, CTR, purchase-per-click,
average order value, pooled and creative-level spend/revenue, daily utilization,
the nonzero-budget row under-delivery frequency and its observed factor range.
An under-delivery event is sampled at the observed row frequency and factor
range. A separate account-pacing multiplier reconciles the row-unweighted mean
delivery factor with budget-weighted utilization: the historical overall
spend/budget ratio is 0.9370 while the mean nonzero-row ratio is 0.9854, so the
configured mean account factor is 0.95084. Its daily log-noise scale is set to
0.037, close to the observed daily utilization standard deviation (0.0371).
This decomposition is not identified by the data; it is an explicit way to
represent the observed aggregate under-spend and daily variation.

Allocation response and temporal dynamics are assumptions. Conversion rate
declines with spend as `(spend / $46.14)^(-elasticity)`, so doubling spend does
not double revenue. The $46.14 reference is the historical median row spend;
elasticity is 0.12 in baseline. Fatigue uses an exponential daily decay of
0.004; faster-fatigue uses 0.012. These rates are not causal estimates: the
observed age pattern is confounded by creative mix and allocation. A shared
market multiplier has zero drift and 0.02 log-scale daily noise. The high-
uncertainty scenario expands creative uncertainty and adds a per-creative
effectiveness shock.

Initial policy history is `daily_reported.csv`, the end-of-day-60 snapshot.
Ground-truth calibration uses `daily_final.csv`, but final revisions are not
inserted into the policy-facing history. Synthetic results become available
only after each simulated day. Each seed uses keyed random streams so competing
benchmarks see common creative truths, market shocks, delivery draws, and
outcome noise where their action sizes permit.

## Benchmarks and limitations

B1 gives every creative $40. B2 implements the seven-day revenue/spend rule,
using pooled population revenue/spend for creatives below 2,000 impressions or
with no spend; ties break by creative ID. The clairvoyant optimizes the
simulator's concave expected-revenue curve, including the option to leave a
creative inactive below the $1 delivery threshold. It water-fills among active
creatives using current latent rates and expected delivery. It sees neither
current-day random outcomes nor future market shocks. The prescribed
normalized-capture metric is omitted until the candidate policy exists.

Results establish only how these rules perform under the configured model.
They do not establish real-world lift, causal creative effects, true cold-start
quality, or the correct fatigue/elasticity parameters. All rows come from one
synthetic account; there is no modeled auction competition, spend interference
between creatives, attribution delay, competitor response, or campaign-level
learning. Robustness scenarios are sensitivities, not posterior probabilities.
