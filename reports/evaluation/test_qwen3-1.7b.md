# LinkMate evaluation: test questions

Chat model `qwen3:1.7b`, embedding model `nomic-embed-text`, 55 contacts, 40 questions. Run time 1.9 min.

Configuration: threshold 0.59, strong_from 0.67, max_candidates 5.

## System against baselines

Confidence intervals are 95% Wilson intervals. Acceptable contacts do not count as wrong, nor as hits.

| System | Right contact | Correct refusals | Precision of recommendations | Balanced |
|---|---|---|---|---|
| BM25 top hit, no LLM (keyword baseline) | 20/30 (67%, CI 49% to 81%) | 0/10 (0%, CI 0% to 28%) | 21/39 (54%) | 0.33 |
| Dense top hit, no LLM | 23/30 (77%, CI 59% to 88%) | 1/10 (10%, CI 2% to 40%) | 26/38 (68%) | 0.43 |
| LinkMate: dense + grounded LLM | 18/30 (60%, CI 42% to 75%) | 1/10 (10%, CI 2% to 40%) | 23/58 (40%) | 0.35 |
| LinkMate, strong label only | 10/30 (33%, CI 19% to 51%) | 10/10 (100%, CI 72% to 100%) | 10/11 (91%) | 0.67 |

Exact sign test on all questions, LinkMate against the keyword baseline: 5 questions only LinkMate gets right, 6 only the baseline gets right, p = 1.000.

| Question type | LinkMate right contact | Keyword baseline |
|---|---|---|
| direct | 10/14 (71%, CI 45% to 88%) | 14/14 (100%, CI 78% to 100%) |
| indirect | 8/16 (50%, CI 28% to 72%) | 6/16 (38%, CI 18% to 61%) |

## Retrieval only

| Mode | Group | n | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---|---|---|---|---|---|
| dense | all | 30 | 0.77 | 0.87 | 0.87 | 0.81 |
| dense | direct | 14 | 1.00 | 1.00 | 1.00 | 1.00 |
| dense | indirect | 16 | 0.56 | 0.75 | 0.75 | 0.65 |
| bm25 | all | 30 | 0.67 | 0.70 | 0.70 | 0.68 |
| bm25 | direct | 14 | 1.00 | 1.00 | 1.00 | 1.00 |
| bm25 | indirect | 16 | 0.38 | 0.44 | 0.44 | 0.40 |
| hybrid | all | 30 | 0.77 | 0.80 | 0.87 | 0.80 |
| hybrid | direct | 14 | 1.00 | 1.00 | 1.00 | 1.00 |
| hybrid | indirect | 16 | 0.56 | 0.62 | 0.75 | 0.62 |

| Mode | Unanswerable questions refused by the threshold alone |
|---|---|
| dense | 1/10 |
| bm25 | 0/10 |
| hybrid | 0/10 |

## Confidence label

Share of recommendations that are expected or acceptable, per label shown to the user.

| Label | Fitting recommendations |
|---|---|
| strong | 10/11 (91%, CI 62% to 98%) |
| weak | 13/47 (28%, CI 17% to 42%) |

## Citations and reasons

Recommendations with an invalid source: 0 of 58.
Word support of reasons in the cited notes: median 0.55, 36/58 at 0.5 or more.

## Failure analysis

| Failure type | Count |
|---|---|
| wrong extra contact | 10 |
| ok | 9 |
| near miss accepted | 8 |
| dropped by validation | 7 |
| retrieval miss | 4 |
| model chose wrong contact | 1 |
| false accept | 1 |

| Question | Type | Result | Failure type | Recommended | Expected | Top candidates |
|---|---|---|---|---|---|---|
| t01 | direct | ok | wrong extra contact | Hugo Lindgren, Patrick Sullivan, Carlos Mendoza | Hugo Lindgren | Hugo Lindgren 0.80, Patrick Sullivan 0.63, Wendy Zhao 0.62 |
| t02 | direct | ok | ok | Priscilla Owens | Priscilla Owens | Priscilla Owens 0.70, Daniel Schulz 0.60, Isaac Goldberg 0.59 |
| t03 | direct | ok | wrong extra contact | Dmitri Volkov, Nina Petrova, Leon Fischer | Dmitri Volkov | Dmitri Volkov 0.74, Nina Petrova 0.68, Leon Fischer 0.67 |
| t04 | direct | ok | wrong extra contact | Fatima Rahman, Marcus Bell, Ella Martin | Fatima Rahman | Fatima Rahman 0.71, Mei Chen 0.61, Ben Adeyemi 0.60 |
| t05 | direct | ok | wrong extra contact | Gabriel Santos, Emma Lindqvist | Gabriel Santos | Gabriel Santos 0.79, Aisha Bello 0.62, Anna Schmidt 0.62 |
| t06 | direct | MISS | dropped by validation | no suitable contact | Hana Kovac | Hana Kovac 0.76, Lena Hoffmann 0.64, Jake Morrison 0.62 |
| t07 | direct | ok | wrong extra contact | Isaac Goldberg, Olivia Park, Daniel Kim | Isaac Goldberg | Isaac Goldberg 0.75, Olivia Park 0.63, Kevin Tran 0.61 |
| t08 | direct | MISS | dropped by validation | no suitable contact | Jonas Keller | Jonas Keller 0.76, Patrick Sullivan 0.60 |
| t09 | direct | ok | ok | Kira Novak | Kira Novak | Kira Novak 0.72, Ella Martin 0.61 |
| t10 | direct | MISS | dropped by validation | no suitable contact | Amara Okoye | Amara Okoye 0.74, Sarah Whitfield 0.63, Sofia Alvarez 0.62 |
| t11 | direct | ok | wrong extra contact | Ruth Feldman, Victor Nguyen, Aisha Bello | Ruth Feldman | Ruth Feldman 0.72, Victor Nguyen 0.65, Aisha Bello 0.63 |
| t12 | direct | MISS | dropped by validation | no suitable contact | Theo Laurent | Theo Laurent 0.78, Anna Schmidt 0.61, Ella Martin 0.60 |
| t13 | direct | ok | ok | Sanjay Mehta | Sanjay Mehta | Sanjay Mehta 0.74, Daniel Kim 0.60 |
| t14 | direct | ok | ok | Wendy Zhao, Olivia Park | Wendy Zhao | Wendy Zhao 0.68, Priscilla Owens 0.64, Maria Gonzalez 0.63 |
| t15 | indirect | ok | wrong extra contact | Wendy Zhao, Maria Gonzalez | Wendy Zhao | Wendy Zhao 0.66, Priscilla Owens 0.64, Maria Gonzalez 0.64 |
| t16 | indirect | ok | ok | Kira Novak | Kira Novak | Kira Novak 0.59 |
| t17 | indirect | MISS | dropped by validation | no suitable contact | Jonas Keller | Jonas Keller 0.70, Marcus Bell 0.63, Patrick Sullivan 0.62 |
| t18 | indirect | ok | wrong extra contact | Sanjay Mehta, Nina Petrova, Priya Raman | Sanjay Mehta | Jonas Keller 0.69, Marcus Bell 0.67, Sanjay Mehta 0.64 |
| t19 | indirect | ok | ok | Fatima Rahman | Fatima Rahman | Fatima Rahman 0.62 |
| t20 | indirect | MISS | retrieval miss | no suitable contact | Ruth Feldman | none above threshold |
| t21 | indirect | MISS | retrieval miss | Brandon Hale | Daniel Kim | Brandon Hale 0.64, Rachel Moreau 0.61, Mei Chen 0.60 |
| t22 | indirect | MISS | retrieval miss | Victor Nguyen | Aisha Bello | Victor Nguyen 0.60 |
| t23 | indirect | MISS | retrieval miss | Ben Adeyemi, Mei Chen, Priya Raman | Julia Brenner | Ben Adeyemi 0.64, Brandon Hale 0.64, Rachel Moreau 0.62 |
| t24 | indirect | ok | wrong extra contact | Anna Schmidt, Daniel Schulz, Julia Brenner | Anna Schmidt | Anna Schmidt 0.67, Daniel Schulz 0.65, Julia Brenner 0.64 |
| t25 | indirect | ok | ok | Sofia Alvarez | Sofia Alvarez | Maria Gonzalez 0.66, Sofia Alvarez 0.65, Samuel Okafor 0.63 |
| t26 | indirect | ok | ok | Chris Douglas | Chris Douglas | Chris Douglas 0.65, Priya Raman 0.59 |
| t27 | indirect | MISS | dropped by validation | no suitable contact | Olivia Park | Olivia Park 0.61, Lena Hoffmann 0.61, Lisa Brandt 0.60 |
| t28 | indirect | MISS | model chose wrong contact | Lena Hoffmann, Wendy Zhao | Maria Gonzalez | Maria Gonzalez 0.72, Lena Hoffmann 0.60, Wendy Zhao 0.60 |
| t29 | indirect | ok | wrong extra contact | Noah Becker, Omar Siddiqui, Mei Chen | Omar Siddiqui | Noah Becker 0.63, Omar Siddiqui 0.63, Sarah Whitfield 0.62 |
| t30 | indirect | MISS | dropped by validation | no suitable contact | Felipe Costa | Felipe Costa 0.65, Jonas Keller 0.62, Patrick Sullivan 0.60 |
| t31 | none | MISS | near miss accepted | Luca Romano, Gabriel Santos, Julia Brenner | no suitable contact | Luca Romano 0.66, Gabriel Santos 0.65, Anna Schmidt 0.62 |
| t32 | none | MISS | near miss accepted | Patrick Sullivan | no suitable contact | Hugo Lindgren 0.62, Patrick Sullivan 0.61, Felipe Costa 0.60 |
| t33 | none | MISS | near miss accepted | Priya Raman, Hana Kovac | no suitable contact | Chris Douglas 0.69, Priya Raman 0.67, Hana Kovac 0.61 |
| t34 | none | MISS | false accept | Victor Nguyen | no suitable contact | Victor Nguyen 0.62 |
| t35 | none | MISS | near miss accepted | Patrick Sullivan | no suitable contact | Priscilla Owens 0.62, Amara Okoye 0.62, Patrick Sullivan 0.62 |
| t36 | none | MISS | near miss accepted | Kevin Tran, Aisha Bello, Ruth Feldman | no suitable contact | Kevin Tran 0.64, Aisha Bello 0.63, Ruth Feldman 0.62 |
| t37 | none | MISS | near miss accepted | Lena Hoffmann | no suitable contact | Lena Hoffmann 0.62, Patrick Sullivan 0.61, Felipe Costa 0.59 |
| t38 | none | MISS | near miss accepted | Jonas Keller | no suitable contact | Jonas Keller 0.63, Samuel Okafor 0.63, Sanjay Mehta 0.63 |
| t39 | none | MISS | near miss accepted | Priscilla Owens | no suitable contact | Maria Gonzalez 0.60, Priscilla Owens 0.59 |
| t40 | none | ok | ok | no suitable contact | no suitable contact | none above threshold |

## Note length bias

Contacts are split at the median of their total note text (217 characters).

| Contact group | Contacts | Expected contact found | Wrong recommendations |
|---|---|---|---|
| short notes | 28 | 15/22 (68%, CI 47% to 84%) | 12 |
| long notes | 27 | 3/8 (38%, CI 14% to 69%) | 23 |

## Latency

Per question: median 2.0 s, p95 6.1 s.

```text
NAME                       ID              SIZE      PROCESSOR    CONTEXT    UNTIL              
nomic-embed-text:latest    0a109f422b47    370 MB    100% GPU     2048       4 minutes from now    
qwen3:1.7b                 8f68893c685c    1.7 GB    100% GPU     4096       4 minutes from now
```
