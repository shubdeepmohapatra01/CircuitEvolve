# Citation verification (2026-10-14)

Every card citation was checked against the arXiv API (`export.arxiv.org/api/query`, titles, authors, first-version
date, journal_ref, DOI) and, where a DOI exists, Crossref (`api.crossref.org/works/<doi>`: title, journal, volume,
page/article number, year). Card text uses the published title; arXiv titles that differ are noted.

| card | arXiv id (title per arXiv) | DOI -> Crossref title / venue |
|---|---|---|
| 01 | 1709.06648 "Halving the cost of quantum addition" (Gidney) | 10.22331/q-2018-06-18-74 -> same title, Quantum 2, 74 (2018) |
| 02 | 1212.5069 "Novel constructions for the fault-tolerant Toffoli gate" (Jones) | 10.1103/PhysRevA.87.022328 -> "Low-overhead constructions for the fault-tolerant Toffoli gate", PRA 87, 022328 (2013) |
| 03 | 1508.03273 "On the advantages of using relative phase Toffolis with an application to multiple control Toffoli optimization" (Maslov) | 10.1103/PhysRevA.93.022311 -> "Advantages of using relative-phase Toffoli gates with an application to multiple control Toffoli optimization", PRA 93, 022311 (2016) |
| 04 | 1210.0974 "Quantum circuits of T-depth one" (Selinger) | 10.1103/PhysRevA.87.042302 -> same, PRA 87, 042302 (2013) |
| 05 | quant-ph/9503016 "Elementary gates for quantum computation" (Barenco, Bennett, Cleve, DiVincenzo, Margolus, Shor, Sleator, Smolin, Weinfurter) | 10.1103/PhysRevA.52.3457 -> same, PRA 52, 3457-3467 (1995) |
| 06 | quant-ph/0410184 "A new quantum ripple-carry addition circuit" (Cuccaro, Draper, Kutin, Moulton) | no DOI in arXiv metadata (arXiv only) |
| 07 | 1303.2042 "Polynomial-time T-depth Optimization of Clifford+T circuits via Matroid Partitioning" (Amy, Maslov, Mosca) | 10.1109/TCAD.2014.2341953 -> IEEE TCAD 33, 1476-1489 (2014) |
| 08 | 1903.10477 "Reducing T-count with the ZX-calculus" (Kissinger, van de Wetering) | 10.1103/PhysRevA.102.022406 -> "Reducing the number of non-Clifford gates in quantum circuits", PRA 102, 022406 (2020) |
| 09 | 1710.07345 "Automated optimization of large quantum circuits with continuous parameters" (Nam, Ross, Su, Childs, Maslov) | 10.1038/s41534-018-0072-4 -> same, npj Quantum Inf. 4, 23 (2018) |
| 10 | 2606.05397 "Multi-Qubit Dyadic Phase Fixing for Fault-Tolerant Quantum Compilation" (Kalloor, Weiden, Younis, Kubiatowicz, Iancu), v1 2026-06-03 | no DOI / journal_ref in arXiv metadata; venue "QCE 2026" taken from the project skill, NOT verified |
| 11 | quant-ph/0201067 "An approximate Fourier transform useful in quantum factoring" (Coppersmith; abstract: 1994 IBM internal report) | no DOI |
| 11 | quant-ph/9601018 "Approximate Quantum Fourier Transform and Decoherence" (Barenco, Ekert, Suominen, Torma) | 10.1103/PhysRevA.54.139 -> PRA 54, 139-146 (1996) |

Flagged: card 10 venue (unverified); card 05 cites Nielsen-Chuang only by way of Nam et al.'s naming ("Toff-NC"),
no separate citation given.
