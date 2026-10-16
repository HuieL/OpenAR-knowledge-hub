"""How often does a paired bootstrap 95% CI exclude zero when two systems are
compared on the same n-item benchmark?  Stdlib only, deterministic seed.

Each simulated item is answered by arm A and arm B. Per-item correctness is
drawn from a shared item difficulty (so the arms are positively correlated, as
on a real benchmark), plus a true accuracy gap `delta` for arm B.
Output: one CSV row per (n, delta, rho) with the rate at which the paired
bootstrap CI excludes 0 (power when delta>0, false-positive rate when delta=0)
and the median CI half-width in percentage points.
"""
import csv, random, statistics, sys

SEED = 20261014
TRIALS = 400
BOOT = 1000
BASE = 0.70

def simulate(rng, n, delta, rho):
    a, b = [], []
    for _ in range(n):
        shared = rng.random()
        ua = shared if rng.random() < rho else rng.random()
        ub = shared if rng.random() < rho else rng.random()
        a.append(1 if ua < BASE else 0)
        b.append(1 if ub < BASE + delta else 0)
    return a, b

def paired_ci(rng, a, b):
    n = len(a)
    diffs = [bi - ai for ai, bi in zip(a, b)]
    stats = sorted(sum(rng.choices(diffs, k=n)) / n for _ in range(BOOT))
    return stats[int(0.025 * BOOT)], stats[int(0.975 * BOOT) - 1]

def main(out):
    rng = random.Random(SEED)
    w = csv.writer(out)
    w.writerow(["n_items", "true_delta_pp", "rho", "trials", "ci_excludes_zero_rate", "median_ci_halfwidth_pp"])
    for n in (100, 200, 500):
        for delta in (0.0, 0.03, 0.05, 0.10):
            for rho in (0.5, 0.8):
                hits, widths = 0, []
                for _ in range(TRIALS):
                    a, b = simulate(rng, n, delta, rho)
                    lo, hi = paired_ci(rng, a, b)
                    hits += lo > 0 or hi < 0
                    widths.append((hi - lo) / 2 * 100)
                w.writerow([n, round(delta * 100), rho, TRIALS, f"{hits / TRIALS:.3f}", f"{statistics.median(widths):.1f}"])
                out.flush()

if __name__ == "__main__":
    main(sys.stdout)
