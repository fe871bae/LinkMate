# Threshold sweep on the development questions

`threshold` is the minimum cosine score of a candidate.

| threshold | right contact | correct refusals | wrong / recommended | balanced |
|---|---|---|---|---|
| 0.5 | 23/24 | 1/6 | 6/29 | 0.562 |
| 0.55 | 23/24 | 1/6 | 6/29 | 0.562 |
| 0.57 | 23/24 | 1/6 | 6/29 | 0.562 |
| 0.59 | 22/24 | 3/6 | 4/26 | 0.708 |
| 0.61 | 21/24 | 3/6 | 5/26 | 0.688 |
| 0.63 | 20/24 | 3/6 | 5/25 | 0.667 |
| 0.65 | 17/24 | 4/6 | 3/20 | 0.688 |
| 0.67 | 16/24 | 6/6 | 0/16 | 0.833 |
| 0.7 | 14/24 | 6/6 | 0/14 | 0.792 |

Chosen setting: threshold 0.59 and `strong_from` 0.67. A threshold of 0.67 alone would give 6/6 correct
refusals and no wrong recommendation, but would hide 6 more right contacts. Showing contacts from 0.59
with a weak label keeps them findable, and the user can see which matches to check.

## Rejected experiments

Strict prompt in the zone below a score limit (threshold 0.55, limit 0.0 means no strict prompt).
Its examples made the small model recommend more people, not fewer, so it was removed.

| limit | right contact | correct refusals | wrong / recommended |
|---|---|---|---|
| 0.0 | 23/24 | 1/6 | 6/29 |
| 0.62 | 23/24 | 1/6 | 8/31 |
| 0.65 | 21/24 | 1/6 | 14/36 |
| 0.68 | 21/24 | 1/6 | 20/42 |

A second LLM pass that fills in need, offer and a same-thing flag per recommendation answered
`same: false` for 20 of 22 right contacts and `same: true` for one wrong one (Tom Weber, airplane),
so it was rejected too. Score alone cannot separate near misses either: fitting contacts score
0.59 to 0.80, unfitting ones 0.59 to 0.67.
