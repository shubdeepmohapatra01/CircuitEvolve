"""Re-fetch the Nam-Ross-Su-Childs-Maslov 2018 arithmetic / reversible benchmark suite at pinned commits.

Sources (pinned):
  * logical (ccz/ccx kept):  quantum-compiler/quartz @ QUARTZ_SHA  circuit/nam-benchmarks/<name>.qasm   (Apache-2.0)
  * Clifford+T as given:     quantum-compiler/quartz @ QUARTZ_SHA  circuit/nam_circs/<name>.qasm        (Apache-2.0)
  * cross-check (ccx form):  meamy/feynman          @ FEYNMAN_SHA benchmarks/qasm/<name>.qasm          (BSD-3-Clause)
  * authors' repo (Quipper ASCII; before / after_light / after_heavy):
                             njross/optimizer       @ NAM_SHA     Arithmetic_and_Toffoli/<name>_<stage>   (no license file)
Upstream files are written unchanged to upstream/{quartz_logical,quartz_cliffordt,feynman_qasm}/.
`normalize.py` then writes the OpenQASM 2 copies used by CircuitEvolve to logical/ and cliffordt/.
"""
import os, urllib.error, urllib.request
QUARTZ_SHA = "ce31db1c91f502f6ef2b9af655855f17f78caf17"
FEYNMAN_SHA = "d2c382a2ab43a40a87f12f4255645bbb55f704f8"
NAM_SHA = "8cd55d504c8a268048d559e80cdc506831959d12"
NAM_RAW = f"https://raw.githubusercontent.com/njross/optimizer/{NAM_SHA}/Arithmetic_and_Toffoli/"
# circuits present in the authors' repo (Nam et al. 2018 Table 4); grover_5, ham15-*, hwb6 are not (they come from
# the T-par / Feynman suite and are optimized in Kissinger & van de Wetering 2020 Table 1).
NAM_BEFORE = {"csla_mux_3": "csla_mux_3_before_original", "csum_mux_9": "csum_mux_9_before_corrected"}
def nam_file(name, stage):
    base = name.replace("gf2^", "gf2^E")
    if stage == "before":
        return NAM_BEFORE.get(name, base + "_before")
    return base + "_" + stage
NAMES = ["adder_8", "barenco_tof_3", "barenco_tof_4", "barenco_tof_5", "barenco_tof_10",
         "tof_3", "tof_4", "tof_5", "tof_10", "csla_mux_3", "csum_mux_9",
         "gf2^4_mult", "gf2^5_mult", "gf2^6_mult", "gf2^7_mult", "gf2^8_mult", "gf2^9_mult", "gf2^10_mult",
         "gf2^16_mult", "gf2^32_mult", "grover_5", "ham15-low", "ham15-med", "ham15-high", "hwb6",
         "mod5_4", "mod_adder_1024", "mod_mult_55", "mod_red_21", "qcla_adder_10", "qcla_com_7", "qcla_mod_7",
         "rc_adder_6", "vbe_adder_3"]
SRC = {
    "quartz_logical": f"https://raw.githubusercontent.com/quantum-compiler/quartz/{QUARTZ_SHA}/circuit/nam-benchmarks/{{}}.qasm",
    "quartz_cliffordt": f"https://raw.githubusercontent.com/quantum-compiler/quartz/{QUARTZ_SHA}/circuit/nam_circs/{{}}.qasm",
    "feynman_qasm": f"https://raw.githubusercontent.com/meamy/feynman/{FEYNMAN_SHA}/benchmarks/qasm/{{}}.qasm",
}
# Feynman .qc originals: their `.v` (all qubits, in QASM order) and `.i` (primary inputs) lines identify the
# clean ancillas (qubits not listed in .i start in |0>), recorded in MANIFEST.csv for relaxed-mode verification.
QC_URL = f"https://raw.githubusercontent.com/meamy/feynman/{FEYNMAN_SHA}/benchmarks/qc/{{}}.qc"
here = os.path.dirname(os.path.abspath(__file__))
if __name__ == "__main__":
    for d, url in SRC.items():
        os.makedirs(os.path.join(here, "upstream", d), exist_ok=True)
        for n in NAMES:
            out = os.path.join(here, "upstream", d, n + ".qasm")
            urllib.request.urlretrieve(url.format(n.replace("^", "%5E")), out)
    os.makedirs(os.path.join(here, "upstream", "feynman_qc"), exist_ok=True)
    for n in NAMES:
        urllib.request.urlretrieve(QC_URL.format(n.replace("^", "%5E")), os.path.join(here, "upstream", "feynman_qc", n + ".qc"))
    os.makedirs(os.path.join(here, "upstream", "nam_quipper"), exist_ok=True)
    got = 0
    for n in NAMES:
        for stage in ("before", "after_light", "after_heavy"):
            fn = nam_file(n, stage)
            try:
                urllib.request.urlretrieve(NAM_RAW + fn.replace("^", "%5E"), os.path.join(here, "upstream", "nam_quipper", fn))
                got += 1
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    raise
    print("fetched", len(NAMES), "x", len(SRC), "qasm +", got, "Quipper files")
