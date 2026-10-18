"""Published T-counts for the Nam et al. 2018 arithmetic suite, transcribed from the papers' tables
(text layer of the PDFs, checked against the rendered page), written to results/v2/published_arith.csv.

  Nam2018  Y. Nam et al., npj Quantum Inf. 4, 23 (2018), Table 4 "T-par comparison", PDF p.5
           (doi:10.1038/s41534-018-0072-4): pre-optimization T, T-par T (ref. 19 = Amy-Maslov-Mosca 2014),
           Light T, Heavy T ("-||-" = no improvement over Light -> Heavy = Light). Also CNOT counts.
  KvdW2020 A. Kissinger, J. van de Wetering, arXiv:1903.10477v2, Table 1, PDF p.4 (Phys. Rev. A 102, 022406):
           original T, best previous ancilla-free T (+ method), PyZX, PyZX+TODD.
The Nam Light/Heavy T-counts are additionally re-counted from the authors' optimized circuit files
(njross/optimizer) by experiments/v2_bench_baselines.py; v2_bench_report.py flags any mismatch.

    .venv/bin/python experiments/v2_bench_published.py
"""
from __future__ import annotations

import csv
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "results", "v2", "published_arith.csv")

# name: (pre_total, pre_cnot, pre_T, tpar_total, tpar_cnot, tpar_T, L_total, L_cnot, L_T, H_total, H_cnot, H_T)
# H_* = None where the table prints "-||-" (no improvement over Light); gf2^64+ omitted (not in the suite).
NAM_T4 = {
    "mod5_4": (63, 28, 28, 76, 48, 16, 51, 28, 16, None, None, None),
    "vbe_adder_3": (150, 70, 70, 161, 114, 24, 89, 50, 24, None, None, None),
    "csla_mux_3": (170, 80, 70, 508, 425, 62, 161, 76, 64, 155, 70, 64),
    "csum_mux_9": (420, 168, 196, 593, 411, 112, 294, 168, 84, 266, 140, 84),
    "qcla_com_7": (443, 186, 203, 751, 583, 95, 284, 132, 95, None, None, None),
    "qcla_mod_7": (884, 382, 413, 1572, 1185, 249, 636, 302, 237, 624, 292, 235),
    "qcla_adder_10": (521, 233, 238, 972, 737, 162, 411, 195, 162, 399, 183, 162),
    "adder_8": (900, 409, 399, 1288, 920, 215, 646, 331, 215, 606, 291, 215),
    "rc_adder_6": (200, 93, 77, 326, 234, 63, 142, 73, 47, 140, 71, 47),
    "mod_red_21": (278, 105, 119, 425, 301, 73, 184, 81, 73, 180, 77, 73),
    "mod_mult_55": (119, 48, 49, 223, 166, 37, 91, 40, 35, None, None, None),
    "barenco_tof_3": (58, 24, 28, 82, 54, 16, 42, 20, 16, 40, 18, 16),
    "tof_3": (45, 18, 21, 65, 41, 15, 35, 14, 15, None, None, None),
    "barenco_tof_4": (114, 48, 56, 141, 90, 28, 78, 40, 28, 72, 34, 28),
    "tof_4": (75, 30, 35, 102, 63, 23, 55, 22, 23, None, None, None),
    "barenco_tof_5": (170, 72, 84, 206, 132, 40, 114, 60, 40, 104, 50, 40),
    "tof_5": (105, 42, 49, 148, 94, 31, 75, 30, 31, None, None, None),
    "barenco_tof_10": (450, 192, 224, 517, 328, 100, 294, 160, 100, 264, 130, 100),
    "tof_10": (255, 102, 119, 361, 232, 71, 175, 70, 71, None, None, None),
    "gf2^4_mult": (225, 99, 112, 419, 324, 68, 187, 99, 68, None, None, None),
    "gf2^5_mult": (347, 154, 175, 682, 535, 111, 296, 154, 115, None, None, None),
    "gf2^6_mult": (495, 221, 252, 842, 649, 150, 403, 221, 150, None, None, None),
    "gf2^7_mult": (669, 300, 343, 1245, 992, 217, 555, 300, 217, None, None, None),
    "gf2^8_mult": (883, 405, 448, 1560, 1256, 264, 712, 405, 264, None, None, None),
    "gf2^9_mult": (1095, 494, 567, 2096, 1701, 351, 891, 494, 351, None, None, None),
    "gf2^10_mult": (1347, 609, 700, 2655, 2176, 410, 1070, 609, 410, None, None, None),
    "gf2^16_mult": (3435, 1581, 1792, 7714, 6592, 1040, 2707, 1581, 1040, None, None, None),
    "gf2^32_mult": (13562, 6268, 7168, 37563, 33269, 4128, 10601, 6299, 4128, None, None, None),
}
NAM_NOTES = {
    "csla_mux_3": "T-par entry footnote a: Nam et al. found the T-par-optimized circuit incorrect; excluded from their comparison",
    "csum_mux_9": "footnote b: T-par's original circuit was incorrect; Nam et al. used the corrected original (ref. 41 Fig. 5)",
}
# name: (paper_name, n, T_orig, best_prev, method, pyzx, pyzx_todd)
KVDW_T1 = {
    "adder_8": ("adder8 [3]", 24, 399, 213, "RMm", 173, 167),
    "barenco_tof_3": ("barenco-tof3", 5, 28, 16, "Tpar", 16, 16),
    "barenco_tof_4": ("barenco-tof4", 7, 56, 28, "Tpar", 28, 28),
    "barenco_tof_5": ("barenco-tof5", 9, 84, 40, "Tpar", 40, 40),
    "barenco_tof_10": ("barenco-tof10", 19, 224, 100, "Tpar", 100, 100),
    "tof_3": ("tof3", 5, 21, 15, "Tpar", 15, 15),
    "tof_4": ("tof4", 7, 35, 23, "Tpar", 23, 23),
    "tof_5": ("tof5", 9, 49, 31, "Tpar", 31, 31),
    "tof_10": ("tof10", 19, 119, 71, "Tpar", 71, 71),
    "csla_mux_3": ("csla-mux3", 15, 70, 58, "RMr", 62, 45),
    "csum_mux_9": ("csum-mux9", 30, 196, 76, "RMr", 84, 72),
    "gf2^4_mult": ("gf(2^4)-mult", 12, 112, 56, "TODD", 68, 52),
    "gf2^5_mult": ("gf(2^5)-mult", 15, 175, 90, "TODD", 115, 86),
    "gf2^6_mult": ("gf(2^6)-mult", 18, 252, 132, "TODD", 150, 122),
    "gf2^7_mult": ("gf(2^7)-mult", 21, 343, 185, "TODD", 217, 173),
    "gf2^8_mult": ("gf(2^8)-mult", 24, 448, 216, "TODD", 264, 214),
    "ham15-low": ("ham15-low", 17, 161, 97, "Tpar", 97, 97),
    "ham15-med": ("ham15-med", 17, 574, 230, "Tpar", 212, 212),
    "ham15-high": ("ham15-high", 20, 2457, 1019, "Tpar", 1019, 1013),
    "hwb6": ("hwb6", 7, 105, 75, "Tpar", 75, 72),
    "mod_mult_55": ("mod-mult-55", 9, 49, 28, "TODD", 35, 20),
    "mod_red_21": ("mod-red-21", 11, 119, 73, "Tpar", 73, 73),
    "mod5_4": ("mod54", 5, 28, 16, "Tpar", 8, 7),
    "qcla_adder_10": ("qcla-adder10", 36, 589, 162, "Tpar", 162, 158),
    "qcla_com_7": ("qcla-com7", 24, 203, 94, "RMm", 95, 91),
    "qcla_mod_7": ("qcla-mod7", 26, 413, 235, "NRSCM", 237, 216),
    "rc_adder_6": ("rc-adder6", 14, 77, 47, "RMm&r", 47, 47),
    "vbe_adder_3": ("vbe-adder3", 10, 70, 24, "Tpar", 24, 24),
}
KVDW_NOTES = {
    "qcla_mod_7": "best prev. 235 carries footnote (a): error in a previously reported T-count (found with Feynman)",
    "qcla_adder_10": "table prints original T = 589 for qcla-adder10 (our file: 238, = Nam Table 4); PyZX 162",
}
NAM_LOC = "Nam et al. 2018 npj QI 4:23, Table 4 (PDF p.5)"
KVDW_LOC = "Kissinger & van de Wetering, arXiv:1903.10477v2 Table 1 (PDF p.4); PRA 102, 022406 (2020)"


def main():
    rows = []
    for name, v in NAM_T4.items():
        pre_tot, pre_cx, pre_t, tp_tot, tp_cx, tp_t, l_tot, l_cx, l_t, h_tot, h_cx, h_t = v
        h_same = h_t is None
        if h_same:
            h_tot, h_cx, h_t = l_tot, l_cx, l_t
        note = NAM_NOTES.get(name, "")
        for arm, t, cx, tot, extra in (("nam2018_pre", pre_t, pre_cx, pre_tot, ""),
                                       ("tpar_as_reported_by_nam2018", tp_t, tp_cx, tp_tot, note),
                                       ("nam2018_light", l_t, l_cx, l_tot, ""),
                                       ("nam2018_heavy", h_t, h_cx, h_tot, "table: -||- (same as Light)" if h_same else "")):
            rows.append(dict(circuit=name, paper="Nam2018", location=NAM_LOC, arm=arm, t_count=t, cnot=cx,
                             total_gates=tot, notes=extra))
    for name, (pn, n, t0, bp, meth, pz, pzt) in KVDW_T1.items():
        note = KVDW_NOTES.get(name, "")
        for arm, t, extra in (("kvdw2020_original", t0, ""), ("best_prev_as_reported_by_kvdw2020", bp, f"method {meth}"),
                              ("kvdw2020_pyzx", pz, ""), ("kvdw2020_pyzx_todd", pzt, "")):
            rows.append(dict(circuit=name, paper="KvdW2020", location=KVDW_LOC + f"; row '{pn}', n={n}", arm=arm,
                             t_count=t, cnot=None, total_gates=None, notes="; ".join(x for x in (extra, note) if x)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if os.path.exists(OUT):
        raise SystemExit(f"{OUT} exists (append-only)")
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows))


if __name__ == "__main__":
    main()
