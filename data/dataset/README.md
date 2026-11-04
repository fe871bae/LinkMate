# LinkMate PoC test dataset

Synthetic data for the LinkMate prototype. All people, companies, emails and events are fictional.
Content is in English and follows the data model in `docs/architecture.md` (section 5).

The texts were generated with LLM support and checked by hand, as planned in Phase 1. The contacts were extended to 55, with deliberately short, vague and very long notes, using `source/build_extension.py`.

| | |
|---|---|
| Contacts | 55 (40 original, 15 added) |
| Notes | 70 (66 notes, 4 emails), 54 to 954 characters, dated 2025-05 to 2026-10 |
| Development questions | `questions.jsonl`, 30 (12 `direct`, 12 `indirect`, 6 `none`). Used for tuning |
| Held-out test questions | `questions_test.jsonl`, 40 (14 `direct`, 16 `indirect`, 10 `none`). Written before tuning and used only for the final evaluation |

## Files

```text
data/dataset/
├── contacts/<contact_id>.json   one finished contact profile per file (= what the contact store holds)
├── notes.jsonl                  all raw notes, oldest first, with the gold contact (input for the capture flow)
├── questions.jsonl              labeled development questions
├── questions_test.jsonl         labeled held-out questions
└── source/build_extension.py    adds the 15 extra contacts and writes the held-out questions
```

Use `contacts/` to seed the store and index directly (`scripts/seed.py`). Use `notes.jsonl` to test
capture: feed the notes in order and compare the extracted profiles with `contacts/` (extraction gold).

## contacts/<id>.json

```json
{
  "id": "c_578d0ac3",
  "name": "Julia Brenner",
  "aliases": ["Jules"],
  "organization": "Feldwerk",
  "role": "Senior UX designer",
  "location": "Hamburg, Germany",
  "met_context": "School friend from Munich (same Abitur class)",
  "summary": "UX designer and old school friend who ...",
  "created_at": "2025-05-10T18:40:00Z",
  "updated_at": "2026-07-21T17:00:00Z",
  "facts": [
    { "kind": "offers_help", "value": "review UI mockups", "source_note_ids": ["n_4c7bd48b", "n_d8b24e54"] }
  ],
  "notes": [
    { "id": "n_4c7bd48b", "text": "Jules (Julia Brenner) - friend from school ...", "source_type": "note", "created_at": "2025-05-10T18:40:00Z" }
  ]
}
```

- `facts[].kind` is `skill`, `interest` or `offers_help`. Every fact lists the notes it comes from.
- `notes[].source_type` is `note` or `email`. Note texts are the original input and must not be changed.
- Profile fields hold the newest value (e.g. Julia's current employer, not the one in her first note).
- `organization` can be empty (private contacts).

## notes.jsonl

One note per line, sorted by `created_at`:

```json
{"note_id": "n_4c7bd48b", "contact_id": "c_578d0ac3", "contact_name": "Julia Brenner", "source_type": "note", "created_at": "2025-05-10T18:40:00Z", "text": "..."}
```

`contact_id` and `contact_name` are the gold answer. Do not show them to the extraction prompt.

## questions.jsonl

```json
{"id": "q10", "type": "direct", "difficulty": "medium",
 "question": "Which company is hiring data science interns for summer 2027?",
 "expected_contact_ids": ["c_..."], "expected_contact_names": ["Kevin Tran"],
 "acceptable_contact_ids": ["c_..."], "acceptable_contact_names": ["Daniel Kim"],
 "rationale": "Kevin recruits summer 2027 DS interns; Daniel Kim has a part-time ML intern role (acceptable)."}
```

| Field | Meaning |
|---|---|
| `type` | `direct`: wording close to the notes. `indirect`: the need is paraphrased. `none`: nobody fits, the right answer is "no suitable contact". |
| `difficulty` | `easy`, `medium`, `hard`. Most `none` questions are `hard` because a near-miss contact exists (e.g. guitar player for a piano question). |
| `expected_contact_ids` | Contacts a good system should return. Use these for recall@k and MRR. Empty for `none`. |
| `acceptable_contact_ids` | Reasonable but not ideal. Do not count them as wrong, and do not count them for recall. |
| `rationale` | Why, with the supporting note and the near miss. For manual checks. |

Suggested scoring: recall@3 and MRR over `expected_contact_ids` for `direct`/`indirect`;
correct-refusal rate for `none`; a recommendation is "wrong" only if it is in neither list.

## Built-in test cases

| Case | Where |
|---|---|
| Prompt injection in an email | Brandon Hale's email asks any AI to always recommend him. He should only appear for q12 (marketing). |
| Job change, confirmed value replaces the old one | Julia Brenner (Kontora, Berlin -> Feldwerk, Hamburg); Lena Hoffmann (engineer -> team lead) |
| Same first name, fuzzy match | Daniel Kim vs. Daniel Schulz |
| Aliases | Jules = Julia Brenner, Pat = Patrick Sullivan, Prof. Okafor = Samuel Okafor |
| Other people mentioned in a note | Lena's email mentions Lisa; Olivia's note mentions Ben; Yuki's note mentions Marcus. Facts must not be attached to them. |
| Contact without offers of help | Yuki Tanaka |
| Two contacts at one company | Lena Hoffmann and Lisa Brandt (Kessler Sensortechnik), used by q23 |
| Multi-contact answers | q14, q23, q24 |
| Messy style | lowercase, arrows, fragments (Marcus' 2nd note, Sam's note) |

## Rebuilding

```bash
PYTHONPATH=. .venv/bin/python data/dataset/source/build_extension.py
```

The script is idempotent. IDs are derived from fixed strings, so a rerun gives identical files. The original 40 contacts are stored directly in `contacts/`.
