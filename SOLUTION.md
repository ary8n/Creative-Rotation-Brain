# Creative Rotation Brain solution

The repository preserves the original assessment README. This file documents the solution and commands.

## Method

`policy.py` implements the assessment `Policy` interface using only creative metadata and rows supplied in `history`. It combines globally shrunk lifetime ROAS, weak format/hook priors, a shrunk trailing-seven-day estimate and a modest uncertainty bonus. It reserves small discovery allocations for new creatives, caps any creative at $400/day, and redistributes the remaining budget. Policy code does not import the simulator or read its ground-truth config.

`simulator.py` models delivery and outcomes for days 61–90; `config.json` holds simulated ground truth. The evaluator compares the policy with B1 uniform, exact B2 windowed greedy and a current-state clairvoyant using common, seed-keyed random draws. Historical validation supports only a small metadata-prior improvement; age decay worsened spend-weighted holdout error and is excluded.

## Reproduction

```sh
python3 -m unittest discover -s tests -v
python3 evaluate.py --seeds 20 --seed-start 3000
```

The evaluator writes paired-seed summaries and daily results under `artifacts/`. Reported intervals are 95% t intervals over 20 seeds.

## Limits

Historical ROAS is observational and does not identify causal response to spend. Counterfactual delivery, diminishing returns, fatigue and market dynamics are simulator assumptions. The policy's results beat both baselines in the configured scenarios, but that demonstrates performance only under those modeled assumptions, not real-world advertising lift. The clairvoyant is an in-model upper benchmark with current latent state, not future random outcomes. Further work should test more plausible delivery dynamics and validate on real randomized spend before deployment.
