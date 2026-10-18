# Tier-2 rule library lex-replay-control

SHA-256 `4bef8a90eb7cccad9039757cbbf51bd3b874ca21e912a67f8ac2a378c40245d6`; parent `e3f42de9ea5ce951dada83aae46237080114108886dd8cbf91983fef2c1a8ccf`; 30 rules (applied in this order).

| # | name | pattern | replacement | dT | dgates | side | source | meaning |
|---|---|---|---|---|---|---|---|---|
| 1 | enum31542 | `cx a b; cx c b; cx c a` | `cx c a; cx a b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 2 | enum31541 | `cx a b; cx c b; cx a c` | `cx a c; cx c b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 3 | enum35625 | `tdg a; cx b a; cx c a; cx c b; t b` | `tdg a; cx c b; t b; cx b a` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 4 | enum1216 | `s a; t a; cx b a; s a; t a` | `tdg a; z b; cx b a; tdg a` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 5 | enum31550 | `cx a b; cx b c; cx a b` | `cx b c; cx a c` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 6 | enum31535 | `cx a b; cx a c; cx c b` | `cx c b; cx a c` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 7 | enum31559 | `cx a b; cz c a; cz b c` | `cz b c; cx a b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 8 | enum1198 | `s a; t a; cx a b; s b; t b` | `tdg a; z b; cx a b; tdg b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 9 | enum803 | `s a; t a; cx b a; z a` | `z b; tdg a; cx b a` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 10 | enum650 | `tdg a; cx b a; s a; sdg b` | `t a; cz a b; cx b a` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 11 | enum32094 | `cx a b; cx c b; tdg b; cx a c` | `cx a c; cx c b; tdg b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 12 | enum749 | `z a; cx b a; s a; t a` | `z b; cx b a; tdg a` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 13 | enum31574 | `cz a b; cz c b; cx c a` | `cx c a; cz a b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 14 | enum31551 | `cx a b; cx c a; cx a b` | `cx c b; cx c a` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 15 | enum32013 | `cx a b; t b; cx b c; cx a c` | `cx b c; cx a b; t b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 16 | enum373 | `s a; t a; cx a b; z b` | `tdg a; z b; cx a b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 17 | enum31539 | `cx a b; cx c a; cx c b` | `cx c a; cx a b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 18 | enum31534 | `cx a b; cx a c; cx b c` | `cx b c; cx a b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 19 | enum315 | `z a; cz a b; cx a b` | `cx a b; cz a b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 20 | enum32006 | `cx a b; s b; cz a c; cz b c` | `cz b c; cx a b; s b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 21 | enum31556 | `cx a b; cz c b; cz c a` | `cz c b; cx a b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 22 | enum886 | `tdg a; cx b a; s a; s b` | `t a; cx b a; cz b a` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 23 | enum32076 | `cx a b; cx c a; t a; cx a b` | `cx c a; t a; cx c b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 24 | enum32078 | `cx a b; cx c a; tdg a; cx a b` | `cx c a; tdg a; cx c b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 25 | enum726 | `z a; cx a b; s b; t b` | `z b; cx a b; tdg b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 26 | enum978 | `cx a b; cx b a; cx a b; cx b a` | `cx b a; cx a b` | -0 | -2 | commute | control | enumerated identity (T -0, gates -2) |
| 27 | enum31566 | `cz a b; cz a c; cx c b` | `cx c b; cz a b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 28 | enum767 | `z a; cx b a; h b; z a` | `z b; cx b a; h b` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 29 | enum32043 | `cx a b; cx a c; t c; cx c b` | `cx c b; cx a c; t c` | -0 | -1 | commute | control | enumerated identity (T -0, gates -1) |
| 30 | enum266 | `cx a b; cx a b` | `id` | -0 | -2 | commute | control | enumerated identity (T -0, gates -2) |

SECONDARY replay with (T, gates) acceptance over the recorded verified proposals; not the primary (T-only) library.
