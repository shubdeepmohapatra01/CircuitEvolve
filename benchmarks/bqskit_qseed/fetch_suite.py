"""Re-fetch the BQSKit-group benchmark circuits (logical, unmapped) from mtweiden/qseed.
Pinned commit: eb9ccab7a0736ba9c8793899b155dd4c20c5ccb1. Mapped variants (mapped-*.qasm) are skipped."""
import json, os, urllib.request
SHA = "eb9ccab7a0736ba9c8793899b155dd4c20c5ccb1"
API = f"https://api.github.com/repos/mtweiden/qseed/git/trees/{SHA}?recursive=1"
RAW = f"https://raw.githubusercontent.com/mtweiden/qseed/{SHA}/"
here = os.path.dirname(os.path.abspath(__file__))
tree = json.load(urllib.request.urlopen(API))["tree"]
for t in tree:
    p = t["path"]
    if t["type"] == "blob" and p.startswith("qasm/") and p.endswith(".qasm") and not os.path.basename(p).startswith("mapped-"):
        out = os.path.join(here, p); os.makedirs(os.path.dirname(out), exist_ok=True)
        urllib.request.urlretrieve(RAW + p, out)
