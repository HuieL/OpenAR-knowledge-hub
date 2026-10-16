"""Sanity check (n=200, true gap 5 points, ~70% base, rho=0.5): how often a
paired bootstrap 95% CI excludes zero, and the median CI half-width.
Independent of the hub record's script: own seed, fewer trials/resamples."""
import random
import statistics
import sys

N, BASE, GAP, RHO = 200, 0.70, 0.05, 0.5
TRIALS, RESAMPLES = (int(v) for v in (sys.argv[1:3] if len(sys.argv) > 2 else (300, 600)))
rng = random.Random(16102026)


def trial():
    diffs = []
    for _ in range(N):
        shared = rng.random()
        ua = shared if rng.random() < RHO else rng.random()
        ub = shared if rng.random() < RHO else rng.random()
        diffs.append(int(ub < BASE + GAP) - int(ua < BASE))
    means = sorted(sum(rng.choice(diffs) for _ in range(N)) / N for _ in range(RESAMPLES))
    lo, hi = means[int(0.025 * RESAMPLES)], means[int(0.975 * RESAMPLES) - 1]
    return (lo > 0 or hi < 0), (hi - lo) / 2 * 100


results = [trial() for _ in range(TRIALS)]
rate = sum(r[0] for r in results) / TRIALS
half = statistics.median(r[1] for r in results)
se = (rate * (1 - rate) / TRIALS) ** 0.5 * 100
print(f"detection_rate={rate:.3f} se_pp={se:.1f} (n_trials={TRIALS}, resamples={RESAMPLES}, items={N}, gap=5pp, rho={RHO})")
print(f"median_ci_halfwidth_pp={half:.2f}")
