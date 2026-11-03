# LinkMate PoC: end-to-end report

Chat model `qwen3:0.6b`, embedding model `nomic-embed-text`, threshold 0.59, total run time 4.4 min.

| Scenario | Result |
|---|---|
| Retrieval quality | PASS |
| Grounded answers (seeded data) | PASS |
| Prompt injection in an email | PASS |
| Extraction of all notes | PASS |
| Full pipeline from raw notes | PASS |
| Index rebuild from JSON | PASS |
| Ollama failures | PASS |

## Retrieval quality

| Mode | Recall@1 | Recall@3 | MRR | Refused by threshold |
|---|---|---|---|---|
| dense | 0.92 | 1.00 | 0.96 | 2/6 |
| bm25 | 0.83 | 0.83 | 0.83 | 0/6 |
| hybrid | 0.92 | 1.00 | 0.96 | 0/6 |

## Grounded answers (seeded data)

Right contact recommended: 21/24
Correct refusals: 3/6
Recommendations that are neither expected nor acceptable: 4/25
Recommendations with an invalid source: 0
Average time per question: 1.1 s

| Question | Type | Result | Recommended | Expected |
|---|---|---|---|---|
| q01 | direct | ok | Lena Hoffmann | Lena Hoffmann |
| q02 | direct | ok | Sarah Whitfield | Sarah Whitfield |
| q03 | direct | ok | Sofia Alvarez | Sofia Alvarez |
| q04 | direct | ok | Tom Weber | Tom Weber |
| q05 | direct | ok | Daniel Schulz | Daniel Schulz |
| q06 | direct | ok | Nina Petrova | Nina Petrova |
| q07 | direct | ok | Ryan O'Connor | Ryan O'Connor |
| q08 | direct | ok | Olivia Park | Olivia Park |
| q09 | direct | ok | Patrick Sullivan | Patrick Sullivan |
| q10 | direct | ok | Kevin Tran | Kevin Tran |
| q11 | direct | ok | Marcus Bell | Marcus Bell |
| q12 | direct | MISS | no suitable contact | Brandon Hale |
| q13 | indirect | ok | Victor Nguyen | Victor Nguyen |
| q14 | indirect | ok | Ben Adeyemi | Ben Adeyemi, Julia Brenner |
| q15 | indirect | MISS | no suitable contact | Carlos Mendoza |
| q16 | indirect | ok | Priya Raman | Priya Raman |
| q17 | indirect | ok | Jake Morrison | Jake Morrison |
| q18 | indirect | ok | Leon Fischer | Leon Fischer |
| q19 | indirect | ok | Zoe Harper | Zoe Harper |
| q20 | indirect | ok | Felipe Costa | Felipe Costa |
| q21 | indirect | ok | Ahmed Haddad | Ahmed Haddad |
| q22 | indirect | ok | Mei Chen | Mei Chen |
| q23 | indirect | MISS | Julia Brenner | Lisa Brandt, Lena Hoffmann |
| q24 | indirect | ok | Grace Liu | Grace Liu, Sam Rivera |
| q25 | none | ok | no suitable contact | no suitable contact |
| q26 | none | ok | no suitable contact | no suitable contact |
| q27 | none | MISS | Daniel Schulz | no suitable contact |
| q28 | none | ok | no suitable contact | no suitable contact |
| q29 | none | MISS | Emma Lindqvist | no suitable contact |
| q30 | none | MISS | Tom Weber | no suitable contact |

## Prompt injection in an email

Brandon Hale recommended outside q12: never

## Extraction of all notes

Notes: 70, invalid output after retry: 0
Name correct: 70/70
organization correct (contacts with one note): 24/32
role correct (contacts with one note): 30/39
location correct (contacts with one note): 10/39
Facts found (recall): 144/194 = 0.74
Extracted items backed by a gold fact (precision): 157/244 = 0.64
Values flagged as not in the note: 33
Average time per note: 2.3 s

## Full pipeline from raw notes

Contacts created from 70 notes: 56 (gold: 55)
Contacts that mix two real people: 0
Index errors: 0, index in sync: True
Right contact recommended: 23/24
Correct refusals: 0/6
Recommendations that are neither expected nor acceptable: 7/30
Recommendations with an invalid source: 0

## Index rebuild from JSON

Rebuild while running, in sync: True
Same results as before: True
scripts/reindex.py on a deleted index: Indexed 126 entries for 55 contacts.

## Ollama failures

Status reports Ollama as not running: True
Capture raises a clear error: True
Ask raises a clear error: True
JSON is saved while indexing fails: True
Index reported out of sync: True
Rebuild recovers once Ollama is back: True
