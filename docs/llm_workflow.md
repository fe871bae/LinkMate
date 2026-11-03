# LLM workflow

LinkMate uses two local models through Ollama. This document records the prompts, the API workflow, the input and output behavior, the limitations, and what the team built around the models. The prompt texts are in `linkmate/core/prompts.py`.

| Model | Role | Size on disk | Memory while loaded | Settings |
|---|---|---|---|---|
| `qwen3:0.6b` | Profile extraction and grounded answers | 0.5 GB | about 0.8 GB | `temperature: 0`, `num_ctx: 4096`, `think: false`, JSON schema in `format` |
| `nomic-embed-text` | Embeddings for entries and questions | 0.3 GB | small | Task prefixes `search_document:` and `search_query:` |

## Task 1: profile extraction

**Input.** The system prompt `EXTRACTION_SYSTEM` holds the field rules and one worked example. The user message is the note inside `<note>` tags. Tags written inside a note are removed first, so a note cannot close its own block, and instruction-like sentences are removed (`core/sanitize.py`).

**Output.** JSON that follows `PROFILE_SCHEMA`, enforced by Ollama's `format` parameter.

```text
<note>
Hana Kovac sets routes at Granite Climbing Gym. Told me she can show me how to belay properly.
</note>
```

```json
{"name": "Hana Kovac", "organization": "Granite Climbing Gym", "role": "route setter", "location": "",
 "met_context": "", "summary": "Route setter who offered to teach belaying.",
 "skills": ["route setting"], "interests": [], "offers_help": ["teach belaying"]}
```

The example shows the format. Real outputs for all notes can be reproduced with `eval/evaluate.py`, and every call is logged in `data/logs/llm_calls.jsonl`.

**After the model.** `parse_profile` validates the JSON with Pydantic and retries once. `clean_profile` removes placeholders such as "n/a" and keeps each item in one list. `unsupported_values` warns about values with no word in the note. The user then reviews everything, and only `confirm` saves.

## Task 2: semantic retrieval

Each contact produces one profile entry and one entry per note chunk. Entries and questions are embedded and compared by cosine similarity in Chroma. `rank_contacts` groups hits by contact, lets each contact count with its best hit, applies `retrieval.threshold` and keeps `max_candidates`. BM25 (`core/retrieval.py`, written in this project) serves as keyword baseline, and `fuse_hybrid` combines both by reciprocal rank fusion.

## Task 3: grounded answer

**Input.** The system prompt `ANSWER_SYSTEM` holds the rules and two worked examples, one with a match and one with an empty list. The user message lists the candidates under neutral labels:

```text
Need: Who could help me calibrate an IMU sensor for my project?

C1 Lena Hoffmann (Kessler Sensortechnik, Team lead, automotive IMU testing)
  [S1] Met Lena at the robotics meetup ...
C2 Patrick Sullivan (Long Beach Makerspace, Retired electrical engineer, volunteer)
  [S2] Pat volunteers at the makerspace ...
```

**Output.** JSON that follows `ANSWER_SCHEMA`.

```json
{"recommendations": [{"contact": "C1", "reason": "Lena calibrates IMU sensors and offered advice.", "sources": ["S1"]}]}
```

**After the model.** `validate_answer` accepts small format slips such as `[S1]`, then applies strict rules. A contact label that does not resolve, a missing reason, a missing source or a source of another contact drops that recommendation, and the drop is shown under "Behind the answer". Scores come from the search and never from the model. In dense mode `AskService` adds the label `strong` from a score of `answer.strong_from`, else `weak`. Other modes always show `weak`, because their scores are not comparable.

## API workflow

1. `OllamaClient.chat_json` sends `POST /api/chat` with `format` set to the JSON schema and logs purpose, model, prompts, output and duration.
2. `OllamaClient.embed` sends `POST /api/embed` in batches of 64 texts.
3. Connection errors become `OllamaUnavailable`, 404 becomes `ModelMissing`, and other failures become `OllamaError`. The UI shows the fix.

There are no API keys. `LINKMATE_OLLAMA_HOST` changes the address for tests. Pointing it at another machine would send notes there and break the local-only promise.

## Limitations of the models

- The small chat model accepts near misses. It recommends a guitar player for a piano question more easily than it refuses. Results are in `reports/evaluation/`.
- A reason can contain details the note does not state. The source note is therefore always shown next to the reason.
- Prompt changes can have surprising effects on a model this small. A stricter prompt with a positive example increased wrong recommendations (`reports/tuning_dev.md`).
- A prompt injection in a note can steer the model. A keyword guard catches known wording only, see `docs/evaluation.md`.
- Temperature 0 gives repeatable answers on one machine, but another Ollama version or platform can answer differently.
- `qwen3:0.6b` is not a state-of-the-art model. It was chosen so that the product runs on an 8 GB laptop.

## Team's own technical contribution

The models are off the shelf. Everything around them was built in this project: the data model, prompts and schemas, the review and merge logic with provenance, chunking, BM25 and rank fusion, the threshold and confidence label, output validation, injection hardening, the Streamlit interface, the one-command setup, the synthetic dataset, and the evaluation suite.
