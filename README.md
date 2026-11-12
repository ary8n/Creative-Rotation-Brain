# Creative Rotation Brain

The original assessment-kit instructions are preserved byte-for-byte in [ASSESSMENT_KIT_README.md](ASSESSMENT_KIT_README.md).

## What was built

`policy.py` implements the assessment `Policy` interface. It uses only creative metadata and prior reported history, combining shrunk lifetime ROAS, weak format/hook priors, a shrunk trailing-seven-day estimate and a modest uncertainty bonus. It reserves small allocations for never-served creatives and caps each creative at $400/day. A historically calibrated simulator in `simulator.py` and `config.json` supports paired 30-day counterfactual evaluations against uniform, windowed-greedy and clairvoyant benchmarks.

## What was skipped

Deep reinforcement learning, competitor scraping, production ad integrations and dashboards were excluded to keep the four-hour solution small and testable. Historical outcomes do not identify causal response to budget, and competitor records lack performance results.

## Evidence and limits

On paired seeds 3000–3019, the policy exceeded both baselines in the configured baseline, faster-fatigue and greater-uncertainty scenarios. The evaluation establishes performance only under the simulator’s assumptions about delivery, spend response, fatigue and market dynamics; it does not establish real-world advertising lift. The clairvoyant is an in-model benchmark with current latent state, not future random outcomes.

## Reproduce

Requires Python 3.11 or later. The project uses only the standard library; no package installation is required. To create and activate an isolated environment:

```sh
python3.11 -m venv .venv
. .venv/bin/activate
```

Run tests and reproduce the headline evaluation:

```sh
python3 -m unittest discover -s tests -v
python3 evaluate.py --seeds 20 --seed-start 3000
```

## With one more day

I would test more plausible delivery and market dynamics, extend time-based historical validation, and evaluate uncertainty around cold-start creatives before considering real randomized spend.
