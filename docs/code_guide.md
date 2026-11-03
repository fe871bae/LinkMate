# Code guide

A reading order for the main files. The architecture and its reasons are in [`architecture.md`](architecture.md).

| Order | File | What to look for |
|---|---|---|
| 1 | `linkmate/models.py` | `Contact`, `Note`, `Fact`, the draft and result types. Every other file uses them |
| 2 | `linkmate/services/__init__.py` | `build_services`, where all parts are wired together |
| 3 | `linkmate/services/capture.py` | Flow A. `propose` never writes, `confirm` does |
| 4 | `linkmate/core/prompts.py` | Prompts, schemas, how the labeled prompt is built |
| 5 | `linkmate/core/extraction.py`, `sanitize.py` | Cleanup of the model's profile, warnings for the review, removal of instruction-like sentences |
| 6 | `linkmate/core/merge.py` | Name matching, merge rules, user edits, provenance |
| 7 | `linkmate/services/ask.py` | Flow B. Search, threshold, LLM call, validation, confidence label |
| 8 | `linkmate/core/retrieval.py` | Entries and chunks, BM25, `rank_contacts`, `fuse_hybrid` |
| 9 | `linkmate/core/validation.py` | What gets dropped and why |
| 10 | `linkmate/infra/index.py`, `store.py`, `ollama_client.py` | Chroma, JSON files, HTTP calls |
| 11 | `app/pages/` | One file per page, each only calls services |
| 12 | `start_linkmate.py` | Standard library only, because it runs before the environment exists |
| 13 | `eval/evaluate.py`, `eval/metrics.py`, `eval/scale.py` | How every number in the reports is produced |
| 14 | `tests/` | Fake LLM and embedder in `conftest.py`, real Chroma and JSON store |

## Conventions

- The UI and scripts call services only. Services are the only layer that uses `infra`.
- `core` has no I/O, which makes it easy to test.
- Code, comments and docs are in English.
- Tests need no Ollama. `scripts/run_e2e.py` and `eval/` use the real models.

## How to add something

| Task | Where |
|---|---|
| A new profile field | `Contact` and `ProfileDraft` in `models.py`, `PROFILE_SCHEMA` and the rules in `prompts.py`, `merge.py`, `profile_form_fields` in `app/common.py` |
| A new search mode | `MODES` and `search` in `services/ask.py` |
| Another chat model | `llm.model` in `config.yaml`, or `eval/evaluate.py --model NAME` to compare it first |
| A new attack test | `CASES` in `eval/injection_cases.py` |
