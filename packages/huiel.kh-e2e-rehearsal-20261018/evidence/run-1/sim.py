"""Paired-bootstrap power of a 5-point gap on an n-item binary benchmark (toy)."""
import json, os, random, sys
args = sys.argv[1:]
if "--fail" in args:
    import scipy  # not installed on purpose: the failed execution
n = int(args[args.index("--n") + 1]) if "--n" in args else 200
random.seed(7)
hits = sum(random.random() < (0.22 if n >= 200 else 0.61) for _ in range(1000))
os.makedirs("out", exist_ok=True)
json.dump({"n": n, "power": hits / 1000, "seed": 7, "trials": 1000}, open("out/metrics.json", "w"))
if n >= 200:
    # The sentinels are assembled at run time so this script itself stays publishable.
    key = "api" + "_key=" + "sk-" + "SENT" + "INEL-kh-e2e-" + "0" * 16
    open("out/notes.txt", "w").write("run notes; " + key + " do not publish\n")
    open(".env", "w").write("HF" + "_TOKEN=" + "hf_" + "SENT" + "INELkhe2e" + "0" * 16 + "\n")
    open("out/samples.csv", "w").write("id,label\n" + "0,1\n" * (8 * 1024 * 1024))
print("power", hits / 1000)
