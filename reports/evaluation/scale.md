# LinkMate scalability

The 55 labeled contacts plus generated distractors, measured on the development machine.

| Contacts | Index entries | Full index (min) | Index size (MB) | JSON store (MB) | Load all contacts (s) | Search p50 / p95 (s) | Full question p50 / p95 (s) | Recall@3 | MRR | Right contact in a 12 question sample |
|---|---|---|---|---|---|---|---|---|---|---|
| 55 | 126 | 0.07 | 1 | 0.1 | 0.02 | 0.044 / 0.055 | 2.42 / 4.30 | 1.00 | 0.96 | 12/12 |
| 555 | 1126 | 0.39 | 10 | 0.4 | 0.14 | 0.028 / 0.036 | 2.00 / 3.42 | 1.00 | 0.96 | 12/12 |
| 2055 | 4126 | 1.45 | 26 | 1.5 | 0.45 | 0.025 / 0.051 | 2.01 / 2.61 | 0.96 | 0.92 | 11/12 |
| 5055 | 10126 | 3.31 | 53 | 3.6 | 0.90 | 0.025 / 0.035 | 1.74 / 2.83 | 0.79 | 0.75 | 9/12 |
