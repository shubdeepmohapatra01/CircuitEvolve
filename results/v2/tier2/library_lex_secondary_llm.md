# Tier-2 rule library lex-replay-llm

SHA-256 `f0d431824f21732e90a42945afd3f2063dd56c41d613fc8c37e3fd6aaf296022`; parent `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`; 1 rules (applied in this order).

| # | name | pattern | replacement | dT | dgates | side | source | meaning |
|---|---|---|---|---|---|---|---|---|
| 1 | g8p0_cx_self_cancel_through_t | `cx b a; cx b a` | `id` | -0 | -2 | commute | llm | a CX applied twice in immediate succession (nothing Z/X-incompatible between) is identity. |

SECONDARY replay with (T, gates) acceptance over the recorded verified proposals; not the primary (T-only) library.
